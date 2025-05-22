"""
User Preference Repository Module for SmartInfo.

This module handles database operations for user-specific application preferences,
stored in the `user_preferences` table. It allows setting, retrieving, and
deleting key-value preference pairs for users.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import asyncpg

from db.schema_constants import UserPreferences
from db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserPreferenceRepository(BaseRepository):
    """
    Repository for managing user-specific preference settings in the database.

    This class provides methods to interact with the `user_preferences` table,
    handling operations such as setting (inserting or updating), retrieving,
    and deleting preferences for users.
    """

    async def set(
        self,
        config_key: str,
        config_value: str,  # Values are stored as strings
        user_id: int,
        description: Optional[str] = None,
    ) -> bool:
        """
        Sets (inserts or updates) a preference value for a specific user.

        Uses an UPSERT (INSERT ... ON CONFLICT ... DO UPDATE) operation to
        either create a new preference record or update an existing one
        based on the composite primary key (`config_key`, `user_id`).

        Args:
            config_key (str): The unique key identifying the preference item
                              (e.g., 'ui_theme', 'llm_temperature').
            config_value (str): The value to store for the preference. All values
                                are stored as strings in the database.
            user_id (int): The ID of the user to whom this setting belongs.
            description (Optional[str]): An optional description of the preference
                item's purpose. Defaults to `None`.

        Returns:
            bool: `True` if the operation was successful (record inserted or
                  updated), `False` if a database error occurred.

        Raises:
            asyncpg.PostgresError: If a database error occurs during the UPSERT.

        Side Effects:
            - Inserts or updates a record in the `user_preferences` table.
            - Logs the operation status or any errors.
        """
        query_str = f"""
            INSERT INTO {UserPreferences.TABLE_NAME} (
                {UserPreferences.KEY}, {UserPreferences.VALUE},
                {UserPreferences.DESCRIPTION}, {UserPreferences.USER_ID}
            ) VALUES ($1, $2, $3, $4)
            ON CONFLICT ({UserPreferences.KEY}, {UserPreferences.USER_ID}) DO UPDATE SET
                {UserPreferences.VALUE} = EXCLUDED.{UserPreferences.VALUE},
                {UserPreferences.DESCRIPTION} = EXCLUDED.{UserPreferences.DESCRIPTION}
        """
        params: Tuple[Any, ...] = (config_key, config_value, description, user_id)

        try:
            status = await self._execute(query_str, params)
            success = status is not None and (
                status.lower().startswith("insert")
                or status.lower().startswith("update")
            )
            if success:
                logger.info(
                    f"Set preference key '{config_key}' for user {user_id}. Status: {status}"
                )
            else:
                logger.warning(
                    f"Set command for preference key '{config_key}' (User: {user_id}) "
                    f"executed but status was '{status}'. This might indicate an issue "
                    "if an insert/update was expected."
                )
            # Return True if no exception, as the DB operation was attempted.
            return True
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error setting user preference key '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error setting user preference key '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get(self, config_key: str, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific preference item by its key for a user.

        Args:
            config_key (str): The key of the preference item to look up.
            user_id (int): The ID of the user.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      preference details (`config_key`,
                                      `config_value`, `description`, `user_id`)
                                      if found, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {UserPreferences.KEY}, {UserPreferences.VALUE},
                   {UserPreferences.DESCRIPTION}, {UserPreferences.USER_ID}
            FROM {UserPreferences.TABLE_NAME}
            WHERE {UserPreferences.KEY} = $1 AND {UserPreferences.USER_ID} = $2
        """
        params = (config_key, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting user preference by key '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting user preference by key '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_all(self, user_id: int) -> Dict[str, str]:
        """
        Retrieves all preference items for a specific user as a key-value dictionary.

        Only `config_key` and `config_value` are included in the returned dictionary.

        Args:
            user_id (int): The ID of the user.

        Returns:
            Dict[str, str]: A dictionary mapping preference keys to their string values
                            for the user. Returns an empty dictionary if no
                            preferences are found or an error occurs.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {UserPreferences.KEY}, {UserPreferences.VALUE}
            FROM {UserPreferences.TABLE_NAME}
            WHERE {UserPreferences.USER_ID} = $1
        """
        params = (user_id,)
        try:
            records = await self._fetchall(query_str, params)
            # Ensure keys from record are accessed correctly (usually lowercase)
            key_col = UserPreferences.KEY.lower()
            value_col = UserPreferences.VALUE.lower()
            return {
                record[key_col]: record[value_col]
                for record in records
                if record[key_col] is not None
                and record[value_col] is not None  # Ensure value is not None
            }
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all user preferences for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return {}
        except Exception as e:
            logger.error(
                f"Unexpected error getting all user preferences for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return {}

    async def get_all_with_details(self, user_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all preference items with their full details for a user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  containing `config_key`, `config_value`,
                                  `description`, and `user_id`. Ordered by key.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {UserPreferences.KEY}, {UserPreferences.VALUE},
                   {UserPreferences.DESCRIPTION}, {UserPreferences.USER_ID}
            FROM {UserPreferences.TABLE_NAME}
            WHERE {UserPreferences.USER_ID} = $1
            ORDER BY {UserPreferences.KEY} ASC
        """
        params = (user_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all user preferences with details for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting all user preferences with details for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, config_key: str, user_id: int) -> bool:
        """
        Deletes a specific preference item by its key for a user.

        Args:
            config_key (str): The key of the preference item to delete.
            user_id (int): The ID of the user.

        Returns:
            bool: `True` if the deletion was successful (one row affected),
                  `False` otherwise (e.g., preference not found).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes a record from `user_preferences`.
            - Logs status or errors.
        """
        query_str = f"""
            DELETE FROM {UserPreferences.TABLE_NAME}
            WHERE {UserPreferences.KEY} = $1 AND {UserPreferences.USER_ID} = $2
        """
        params = (config_key, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(
                    f"Deleted preference key '{config_key}' for user {user_id}."
                )
            else:
                logger.warning(
                    f"Delete command for preference key '{config_key}' (User: {user_id}) "
                    f"executed but status was '{status}'. Key might not exist."
                )
            return deleted
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error deleting user preference '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting user preference '{config_key}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def clear_all_for_user(self, user_id: int) -> bool:
        """
        Deletes all preference items for a specific user.

        Args:
            user_id (int): The ID of the user whose preferences to clear.

        Returns:
            bool: `True` if the command executed successfully (regardless of rows
                  affected), `False` if a database error occurred.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes all records for the user from `user_preferences`.
            - Logs status or errors.
        """
        query_str = f"DELETE FROM {UserPreferences.TABLE_NAME} WHERE {UserPreferences.USER_ID} = $1"
        params = (user_id,)
        try:
            status = await self._execute(query_str, params)
            # DELETE command returns "DELETE <count>".
            # We consider it successful if no DB error occurred.
            logger.info(
                f"Cleared user preference settings for user {user_id}. Status: {status}."
            )
            return True  # Indicates command execution success
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error clearing user preferences for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error clearing user preferences for user {user_id}: {e}",
                exc_info=True,
            )
            raise
