"""
SettingService Module.

This service is responsible for managing user-specific application settings and
API key configurations. It provides an interface for CRUD operations on API keys
and for retrieving, updating, and resetting user preferences, all within the
context of an authenticated user. It also includes functionality to test the
validity and connectivity of a user's configured API keys.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union

from db.repositories.api_key_repository import ApiKeyRepository
from db.repositories.user_preference_repository import UserPreferenceRepository
from models import (
    ApiKey,
    ApiKeyCreate,
    UserPreference,
    UserPreferenceBase,
    User,
)

from core.llm.client import AsyncLLMClient

logger = logging.getLogger(__name__)


class SettingService:
    """
    Service layer for managing user-specific settings, including API keys
    and general application preferences.
    """

    def __init__(
        self,
        api_key_repo: ApiKeyRepository,
        user_preference_repo: UserPreferenceRepository,
    ):
        """Initializes the SettingService with necessary repositories.

        Args:
            api_key_repo: Repository for API key data operations.
            user_preference_repo: Repository for user preference data operations.

        Side Effects:
            Initializes internal repository attributes (`_api_key_repo`,
            `_user_preference_repo`).
        """
        self._api_key_repo = api_key_repo
        self._user_preference_repo = user_preference_repo

    # --- API Key Management (User-Aware) ---

    async def get_api_key_by_id(self, api_id: int, user_id: int) -> Optional[ApiKey]:
        """Retrieves a specific API key by its ID for a given user.

        Args:
            api_id: The ID of the API key to retrieve.
            user_id: The ID of the user who owns the API key.

        Returns:
            An `ApiKey` model instance if the key is found and belongs to the user,
            otherwise None.

        Side Effects:
            Reads API key data from the database.
        """
        api_key_record = await self._api_key_repo.get_by_id(api_id, user_id)
        if not api_key_record:
            return None
        return ApiKey.model_validate(dict(api_key_record))

    async def get_all_api_keys(self, user_id: int) -> List[ApiKey]:
        """Retrieves all API keys associated with a specific user.

        Args:
            user_id: The ID of the user whose API keys are to be retrieved.

        Returns:
            A list of `ApiKey` model instances. Returns an empty list if the
            user has no API keys.

        Side Effects:
            Reads API key data from the database.
        """
        api_keys_data = await self._api_key_repo.get_all(user_id)
        return [ApiKey.model_validate(dict(item)) for item in api_keys_data]

    async def save_api_key(self, api_key_data: ApiKeyCreate, user_id: int) -> ApiKey:
        """Saves a new API key for a specific user after validation.

        Validates that:
        - Required fields (model, base_url, api_key) are present.
        - `context` and `max_output_tokens` are integers.
        - `context` is greater than `max_output_tokens`.
        The user_id for the ApiKey is taken from the authenticated user context.

        Args:
            api_key_data: An `ApiKeyCreate` Pydantic model instance containing the
                          details of the API key to be saved. Expected fields:
                          `model` (str), `base_url` (AnyHttpUrl), `api_key` (str),
                          `context` (int), `max_output_tokens` (int),
                          `description` (Optional[str]).
            user_id: The ID of the authenticated user saving the API key.

        Returns:
            The newly created `ApiKey` model instance.

        Raises:
            ValueError: If validation fails (e.g., missing required fields,
                        invalid token/context values).
            RuntimeError: If the API key is successfully added to the database
                          but cannot be retrieved immediately afterwards.

        Side Effects:
            Adds a new API key record to the database for the user.
        """
        # user_id in ApiKeyCreate model is not used/expected.
        # The authoritative user_id is the one passed as a parameter.

        if (
            not api_key_data.model
            or not api_key_data.base_url
            or not api_key_data.api_key
        ):
            raise ValueError("Model, base URL, and API key string are required.")

        if not isinstance(api_key_data.context, int) or not isinstance(
            api_key_data.max_output_tokens, int
        ):
            raise ValueError(
                "Context window size and max output tokens must be integers."
            )

        if api_key_data.context <= api_key_data.max_output_tokens:
            raise ValueError(
                "Context window size must be greater than max output tokens."
            )

        key_id = await self._api_key_repo.add(
            model=api_key_data.model,
            base_url=str(api_key_data.base_url),
            api_key=api_key_data.api_key,
            context=api_key_data.context,
            max_output_tokens=api_key_data.max_output_tokens,
            description=api_key_data.description,
            user_id=user_id,
        )

        if key_id:
            created_key = await self.get_api_key_by_id(key_id, user_id)
            if created_key:
                logger.info(
                    f"Successfully saved API key ID {key_id} for user {user_id}."
                )
                return created_key
            else:
                logger.error(
                    f"Failed to retrieve newly created API key {key_id} for user {user_id} after successful add."
                )
                raise RuntimeError(
                    f"Failed to retrieve newly created API key {key_id} for user {user_id}."
                )

        logger.error(
            f"Failed to save API key for model {api_key_data.model} for user {user_id}. Repository did not return an ID."
        )
        raise ValueError(
            f"Failed to save API key for model {api_key_data.model} for user {user_id}."
        )

    async def update_api_key(
        self,
        api_id: int,
        user_id: int,
        api_key_data: ApiKeyCreate,
    ) -> Optional[ApiKey]:
        """Updates an existing API key for a specific user after validation.

        Validates similarly to `save_api_key`. The repository's update method
        is expected to handle ownership verification (matching `api_id` and `user_id`).
        The user_id for the ApiKey is taken from the authenticated user context.

        Args:
            api_id: The ID of the API key to update.
            user_id: The ID of the authenticated user who owns the API key.
            api_key_data: An `ApiKeyCreate` Pydantic model instance containing the
                          updated details.

        Returns:
            The updated `ApiKey` model instance if successful, otherwise None
            (e.g., if the API key is not found, not owned by the user, or if
            validation fails).

        Raises:
            ValueError: If validation fails (e.g., missing required fields,
                        invalid token/context values).

        Side Effects:
            Modifies an existing API key record in the database.
        """
        # user_id in ApiKeyCreate model is not used/expected.
        # The authoritative user_id is the one passed as a parameter.

        if not api_key_data.model or not api_key_data.base_url:
            raise ValueError("Model and base URL are required for API key update.")
        if not isinstance(api_key_data.context, int) or not isinstance(
            api_key_data.max_output_tokens, int
        ):
            raise ValueError(
                "Context window size and max output tokens must be integers for update."
            )
        if api_key_data.context <= api_key_data.max_output_tokens:
            raise ValueError(
                "Context window size must be greater than max output tokens for update."
            )

        updated_successfully = await self._api_key_repo.update(
            api_id=api_id,
            user_id=user_id,
            model=api_key_data.model,
            base_url=str(api_key_data.base_url),
            api_key=api_key_data.api_key,
            context=api_key_data.context,
            max_output_tokens=api_key_data.max_output_tokens,
            description=api_key_data.description,
        )

        if not updated_successfully:
            logger.warning(
                f"Failed to update API key ID {api_id} for user {user_id}. Key not found, not owned, or update failed in repo."
            )
            return None

        logger.info(f"Successfully updated API key ID {api_id} for user {user_id}.")
        return await self.get_api_key_by_id(api_id, user_id)

    async def delete_api_key(self, api_id: int, user_id: int) -> bool:
        """Deletes an API key by its ID for a specific user.

        Args:
            api_id: The ID of the API key to delete.
            user_id: The ID of the user who owns the API key.

        Returns:
            True if the API key was successfully deleted, False otherwise
            (e.g., key not found or not owned by the user).

        Side Effects:
            Removes an API key record from the database.
        """
        deleted = await self._api_key_repo.delete(api_id, user_id)
        if deleted:
            logger.info(f"Successfully deleted API key ID {api_id} for user {user_id}.")
        else:
            logger.warning(
                f"Failed to delete API key ID {api_id} for user {user_id}. Key not found or not owned."
            )
        return deleted

    # --- User Preference Management (User-Aware) ---

    async def get_all_settings(self, user_id: int) -> Dict[str, Any]:
        """Retrieves all application settings (user preferences) for a specific user.

        Args:
            user_id: The ID of the user whose settings are to be retrieved.

        Returns:
            A dictionary where keys are setting names (str) and values are
            setting values (Any, typically str as stored in DB).

        Side Effects:
            Reads user preference data from the database.
        """
        user_settings_records = await self._user_preference_repo.get_all(user_id)
        logger.debug(
            f"Retrieved {len(user_settings_records)} settings for user {user_id}."
        )
        return user_settings_records

    async def update_settings(
        self, settings_payload: Dict[str, Any], user_id: int
    ) -> Dict[str, Any]:
        """Updates application settings for a specific user.

        Args:
            settings_payload: A dictionary of settings to update.
            user_id: The ID of the user whose settings are being updated.

        Returns:
            A dictionary representing all current settings for the user after
            the update attempt.

        Side Effects:
            Modifies or adds user preference records in the database.
        """
        if not settings_payload:
            logger.info(
                f"No settings provided to update for user {user_id}. Returning current settings."
            )
            return await self.get_all_settings(user_id)

        logger.info(f"Updating {len(settings_payload)} settings for user {user_id}.")
        all_success = True
        for key, value in settings_payload.items():
            str_value = str(value)
            success = await self._user_preference_repo.set(
                config_key=key,
                config_value=str_value,
                user_id=user_id,
                description=None,
            )
            if not success:
                all_success = False
                logger.error(
                    f"Failed to save setting '{key}' with value '{str_value}' for user {user_id}."
                )

        if not all_success:
            logger.warning(
                f"One or more settings failed to save for user {user_id}. Check previous error logs."
            )

        return await self.get_all_settings(user_id)

    async def reset_settings_to_defaults(self, user_id: int) -> Dict[str, Any]:
        """Resets all application settings for a specific user to their defaults.

        Args:
            user_id: The ID of the user whose settings are to be reset.

        Returns:
            An empty dictionary, signifying all user-specific overrides cleared.

        Side Effects:
            Removes all user preference records for the specified user.
        """
        logger.info(
            f"Resetting all settings to defaults for user {user_id} by clearing them."
        )
        cleared_successfully = await self._user_preference_repo.clear_all_for_user(
            user_id
        )

        if not cleared_successfully:
            logger.error(
                f"Failed to clear existing user preferences from database for user {user_id} during reset operation."
            )

        return {}

    # --- API Key Testing (User-Aware) ---

    async def test_api_key_connection(
        self, api_key_id: int, user_id: int
    ) -> Dict[str, Any]:
        """
        Tests the connection and validity of a specific API key for a user.

        Args:
            api_key_id: The ID of the API key to test.
            user_id: The ID of the user who owns the API key.

        Returns:
            A dictionary indicating the test result.

        Side Effects:
            Reads DB, makes external HTTP call to LLM.
        """
        logger.info(f"Testing API key connection for ID {api_key_id}, user {user_id}.")
        api_key_record = await self._api_key_repo.get_by_id(api_key_id, user_id)

        if not api_key_record:
            logger.warning(
                f"API key ID {api_key_id} not found or not owned by user {user_id} for testing."
            )
            return {
                "status": "error",
                "error": "Not Found",
                "message": f"API key with ID '{api_key_id}' not found or not owned by user.",
            }

        api_key_details = dict(api_key_record)
        model_name = api_key_details.get("model")
        base_url_from_db = api_key_details.get(
            "base_url"
        )  # Could be AnyHttpUrl if not cast before
        actual_api_key_str = api_key_details.get("api_key")

        if not all([model_name, base_url_from_db, actual_api_key_str]):
            logger.error(
                f"API key ID {api_key_id} for user {user_id} is missing critical details. Cannot test."
            )
            return {
                "status": "error",
                "error": "Configuration Error",
                "message": f"API key ID '{api_key_id}' is incompletely configured.",
            }

        # Ensure types are strings for AsyncLLMClient
        # The `all` check above ensures they are not None.
        base_url_str_for_client = str(base_url_from_db)
        model_name_str_for_client = str(model_name)
        api_key_str_for_client = str(actual_api_key_str)

        test_messages = [{"role": "user", "content": "hello"}]
        logger.debug(
            f"Attempting LLM connection test to {base_url_str_for_client} with model {model_name_str_for_client} for API key ID {api_key_id}."
        )

        try:
            async with AsyncLLMClient(
                base_url=base_url_str_for_client,
                api_key=api_key_str_for_client,
                model=model_name_str_for_client,
            ) as client:
                response_content = await client.get_completion_content(
                    messages=test_messages
                )
                if not response_content or not response_content.strip():
                    logger.warning(
                        f"LLM test for API key {api_key_id} received an empty or whitespace response."
                    )
                    raise ValueError(
                        "No meaningful response content received from API."
                    )

                logger.info(
                    f"Successfully connected and received response using API key ID {api_key_id}."
                )
                return {"status": "success", "message": "Connection successful."}
        except Exception as e:
            logger.error(
                f"LLM connection test failed for API key ID {api_key_id} (User: {user_id}) "
                f"to {base_url_str_for_client} with model {model_name_str_for_client}. Error: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "error_details": str(e),
                "message": f"Failed to connect to LLM service at {base_url_str_for_client} with model {model_name_str_for_client}. Please verify API key, URL, and model.",
            }
