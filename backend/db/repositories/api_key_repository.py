"""
API Key Repository Module for SmartInfo.

This module provides data access operations for the `api_config` table,
which stores API key configurations for users. It allows for creating,
retrieving, updating, and deleting API key settings associated with users.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import asyncpg
from datetime import datetime, timezone

from db.schema_constants import ApiConfig
from db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ApiKeyRepository(BaseRepository):
    """
    Repository for managing API key configurations in the database.

    This class provides methods to interact with the `api_config` table,
    handling operations such as adding, updating, deleting, and retrieving
    API key details for users.
    """

    async def add(
        self,
        model: str,
        base_url: str,
        api_key: str,
        context: int,
        max_output_tokens: int,
        user_id: int,
        description: Optional[str] = None,
    ) -> Optional[int]:
        """
        Adds a new API key configuration for a user to the database.

        Args:
            model (str): The identifier of the LLM model (e.g., 'gpt-4').
            base_url (str): The base URL for the LLM API endpoint.
            api_key (str): The API key for the LLM service.
            context (int): The context window size (in tokens) for the model.
            max_output_tokens (int): The maximum number of tokens for LLM output.
            user_id (int): The ID of the user to whom this API key belongs.
            description (Optional[str]): A user-friendly description for this
                API configuration. Defaults to None.

        Returns:
            Optional[int]: The ID of the newly created API key record if
                           successful, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs during insertion.

        Side Effects:
            - Inserts a new record into the `api_config` table.
            - Logs the addition of the API key or any errors encountered.
        """
        current_time = datetime.now(timezone.utc)
        query_str = f"""
            INSERT INTO {ApiConfig.TABLE_NAME} (
                {ApiConfig.MODEL}, {ApiConfig.BASE_URL}, {ApiConfig.API_KEY},
                {ApiConfig.CONTEXT}, {ApiConfig.MAX_OUTPUT_TOKENS}, {ApiConfig.DESCRIPTION},
                {ApiConfig.CREATED_DATE}, {ApiConfig.MODIFIED_DATE}, {ApiConfig.USER_ID}
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING {ApiConfig.ID}
        """
        params: Tuple[Any, ...] = (  # Explicitly typing params
            model,
            base_url,
            api_key,
            context,
            max_output_tokens,
            description,
            current_time,
            current_time,
            user_id,
        )

        try:
            record_id = await self._fetchval(query_str, params)
            if record_id is not None:
                logger.info(
                    f"Added API key for model {model} with ID {record_id} for user {user_id}."
                )
            else:
                logger.warning(
                    f"Failed to add API key for model {model} for user {user_id}, no ID returned."
                )
            return record_id  # record_id is already Optional[Any], fetchval returns Optional[Any]
        except asyncpg.PostgresError as e:
            logger.error(f"Error adding API key for user {user_id}: {e}", exc_info=True)
            # Do not return None here, let the exception propagate if not handled by caller
            raise
        except Exception as e:  # Catching generic Exception is broad
            logger.error(
                f"Unexpected error adding API key for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def update(
        self,
        api_id: int,
        user_id: int,
        model: str,  # Assuming model is required for an update
        base_url: str,  # Assuming base_url is required
        api_key: Optional[str] = None,  # API key can be optional if not changing
        context: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Updates an existing API key configuration for a specific user.

        The method first fetches the existing record to ensure it belongs to the
        user and to use existing values for fields not provided in the update.

        Args:
            api_id (int): The ID of the API key configuration to update.
            user_id (int): The ID of the user who owns the API key.
            model (str): The new model identifier.
            base_url (str): The new base URL for the API.
            api_key (Optional[str]): The new API key. If `None`, the existing
                key is retained.
            context (Optional[int]): The new context window size. If `None`,
                the existing value is retained.
            max_output_tokens (Optional[int]): The new max output tokens. If
                `None`, the existing value is retained.
            description (Optional[str]): The new description. If `None`, the
                existing description is retained.

        Returns:
            bool: `True` if the update was successful (one row affected),
                  `False` otherwise (e.g., key not found, not owned by user,
                  or DB error).

        Raises:
            asyncpg.PostgresError: If a database error occurs during the update.

        Side Effects:
            - Updates a record in the `api_config` table if found and owned.
            - Sets the `modified_date` to the current timestamp.
            - Logs the update status or any errors.
        """
        existing_record = await self.get_by_id(api_id, user_id)
        if not existing_record:
            logger.warning(
                f"API key ID {api_id} not found or not owned by user {user_id} for update."
            )
            return False

        # Coerce asyncpg.Record to a Dict for easier field access with .get() and type checking
        existing_data: Dict[str, Any] = dict(existing_record)

        current_time = datetime.now(timezone.utc)
        query_str = f"""
            UPDATE {ApiConfig.TABLE_NAME}
            SET {ApiConfig.MODEL} = $1, {ApiConfig.BASE_URL} = $2,
                {ApiConfig.API_KEY} = $3, {ApiConfig.CONTEXT} = $4,
                {ApiConfig.MAX_OUTPUT_TOKENS} = $5, {ApiConfig.DESCRIPTION} = $6,
                {ApiConfig.MODIFIED_DATE} = $7
            WHERE {ApiConfig.ID} = $8 AND {ApiConfig.USER_ID} = $9
        """
        params: Tuple[Any, ...] = (
            model,  # model is now required
            base_url,  # base_url is now required
            (
                api_key
                if api_key is not None
                else existing_data.get(ApiConfig.API_KEY.lower())
            ),
            (
                context
                if context is not None
                else existing_data.get(ApiConfig.CONTEXT.lower())
            ),
            (
                max_output_tokens
                if max_output_tokens is not None
                else existing_data.get(ApiConfig.MAX_OUTPUT_TOKENS.lower())
            ),
            (
                description
                if description is not None
                else existing_data.get(ApiConfig.DESCRIPTION.lower())
            ),
            current_time,
            api_id,
            user_id,
        )

        try:
            status = await self._execute(query_str, params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(f"Updated API key ID {api_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Update command for API key ID {api_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Record might not exist or no changes made."
                )
            return updated
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating API key ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Propagate DB errors
        except Exception as e:
            logger.error(
                f"Unexpected error updating API key ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, api_id: int, user_id: int) -> bool:
        """
        Deletes an API key configuration for a specific user.

        Args:
            api_id (int): The ID of the API key configuration to delete.
            user_id (int): The ID of the user who owns the API key.

        Returns:
            bool: `True` if the deletion was successful (one row affected),
                  `False` otherwise (e.g., key not found or not owned by user).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes a record from the `api_config` table.
            - Logs the deletion status or any errors.
        """
        query_str = f"DELETE FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1 AND {ApiConfig.USER_ID} = $2"
        params = (api_id, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(f"Deleted API key ID {api_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Delete command for API key ID {api_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Key might not exist or not belong to user."
                )
            return deleted
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error deleting API key ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting API key ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, api_id: int, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific API key configuration by its ID, ensuring it
        belongs to the specified user.

        Args:
            api_id (int): The ID of the API key configuration.
            user_id (int): The ID of the user.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      API key details if found and owned by the
                                      user, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `api_config` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {ApiConfig.ID}, {ApiConfig.MODEL}, {ApiConfig.BASE_URL},
                   {ApiConfig.API_KEY}, {ApiConfig.CONTEXT}, {ApiConfig.MAX_OUTPUT_TOKENS},
                   {ApiConfig.DESCRIPTION}, {ApiConfig.CREATED_DATE}, {ApiConfig.MODIFIED_DATE},
                   {ApiConfig.USER_ID}
            FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1 AND {ApiConfig.USER_ID} = $2
        """
        params = (api_id, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting API key by ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting API key by ID {api_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_all(self, user_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all API key configurations for a specific user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  representing an API key configuration. Returns
                                  an empty list if no keys are found for the user.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `api_config` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {ApiConfig.ID}, {ApiConfig.MODEL}, {ApiConfig.BASE_URL},
                   {ApiConfig.API_KEY}, {ApiConfig.CONTEXT}, {ApiConfig.MAX_OUTPUT_TOKENS},
                   {ApiConfig.DESCRIPTION}, {ApiConfig.CREATED_DATE}, {ApiConfig.MODIFIED_DATE},
                   {ApiConfig.USER_ID}
            FROM {ApiConfig.TABLE_NAME}
            WHERE {ApiConfig.USER_ID} = $1
            ORDER BY {ApiConfig.MODEL}, {ApiConfig.CREATED_DATE} DESC
        """
        params = (user_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all API keys for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting all API keys for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_api_count(self, user_id: int) -> int:
        """
        Gets the total count of API key configurations for a specific user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            int: The total number of API keys for the user. Returns 0 if an
                 error occurs or no keys are found.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT COUNT(*) query.
            - Logs errors if any occur.
        """
        query_str = f"SELECT COUNT(*) FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.USER_ID} = $1"
        params = (user_id,)
        try:
            count = await self._fetchval(query_str, params)
            return count if count is not None else 0
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting API key count for user {user_id}: {e}", exc_info=True
            )
            raise  # Or return 0 depending on desired error handling
        except Exception as e:
            logger.error(
                f"Unexpected error getting API key count for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return 0
