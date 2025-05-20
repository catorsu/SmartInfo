"""
User Repository Module for SmartInfo.

This module handles database operations related to user accounts, such as
creating new users and retrieving user information for authentication and
profile management. It interacts with the 'users' table.

@module_purpose: To provide a persistent storage interface for user account data,
                 including credentials and basic profile information.
@primary_consumers: `services.auth_service.AuthService`.
@primary_dependencies: `db.repositories.base_repository.BaseRepository`,
                       `models.schemas.user.UserInDB` (Pydantic model),
                       `db.schema_constants.Users`, `asyncpg`.
"""

from typing import Optional, Any, Tuple
import asyncpg
import logging

from .base_repository import BaseRepository
from models.schemas.user import UserInDB  # Pydantic model for DB representation
from db.schema_constants import Users

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """
    Repository for user-related database operations.

    Provides methods to add new users and retrieve user details by username or ID.
    This class is crucial for user registration and authentication processes.

    @class_responsibility: To encapsulate all database interactions related to
                           the `users` table, managing user account data.
    @typical_usage_pattern: Instantiated and used by `AuthService` to handle
                            user creation, authentication, and profile updates.
    """

    async def add_user(self, username: str, hashed_password: str) -> Optional[UserInDB]:
        """
        Adds a new user to the database.

        Args:
            username (str): The username for the new user. Must be unique.
            hashed_password (str): The securely hashed password for the new user.

        Returns:
            Optional[UserInDB]: A `UserInDB` Pydantic model instance representing
                                the newly created user if successful. Returns `None`
                                if the username already exists (due to unique
                                constraint) or if another database error occurs.

        Raises:
            asyncpg.UniqueViolationError: Propagated if the username already exists
                                          and not caught internally.
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Inserts a new record into the `users` table.
            - Logs user addition status or errors.
        """
        query = f"""
            INSERT INTO {Users.TABLE_NAME} ({Users.USERNAME}, {Users.HASHED_PASSWORD})
            VALUES ($1, $2)
            RETURNING {Users.ID}, {Users.USERNAME}, {Users.HASHED_PASSWORD}
        """
        params: Tuple[Any, ...] = (username, hashed_password)
        try:
            record = await self._fetchone(query, params)
            return UserInDB.model_validate(dict(record)) if record else None
        except asyncpg.UniqueViolationError:
            # This error means the username (which has a UNIQUE constraint) already exists.
            logger.warning(f"Attempt to add user with existing username: '{username}'.")
            return None  # Explicitly return None for "username already exists"
        except asyncpg.PostgresError as e:
            logger.error(f"Error adding user '{username}': {e}", exc_info=True)
            raise  # Re-raise other DB errors
        except Exception as e:
            logger.error(
                f"Unexpected error adding user '{username}': {e}", exc_info=True
            )
            raise

    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """
        Retrieves a user from the database by their username.

        Args:
            username (str): The username of the user to search for.

        Returns:
            Optional[UserInDB]: A `UserInDB` Pydantic model instance if a user
                                with the given username is found, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `users` table.
            - Logs errors if any occur.
        """
        query = f"""
            SELECT {Users.ID}, {Users.USERNAME}, {Users.HASHED_PASSWORD}
            FROM {Users.TABLE_NAME}
            WHERE {Users.USERNAME} = $1
        """
        params = (username,)
        try:
            record = await self._fetchone(query, params)
            return UserInDB.model_validate(dict(record)) if record else None
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting user by username '{username}': {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting user by username '{username}': {e}",
                exc_info=True,
            )
            raise

    async def get_user_by_id(self, user_id: int) -> Optional[UserInDB]:
        """
        Retrieves a user from the database by their unique ID.

        Args:
            user_id (int): The ID of the user to search for.

        Returns:
            Optional[UserInDB]: A `UserInDB` Pydantic model instance if a user
                                with the given ID is found, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `users` table.
            - Logs errors if any occur.
        """
        query = f"""
            SELECT {Users.ID}, {Users.USERNAME}, {Users.HASHED_PASSWORD}
            FROM {Users.TABLE_NAME}
            WHERE {Users.ID} = $1
        """
        params = (user_id,)
        try:
            record = await self._fetchone(query, params)
            return UserInDB.model_validate(dict(record)) if record else None
        except asyncpg.PostgresError as e:
            logger.error(f"Error getting user by ID {user_id}: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting user by ID {user_id}: {e}", exc_info=True
            )
            raise

    async def update_username(self, user_id: int, new_username: str) -> bool:
        """
        Updates the username for a given user ID.

        Args:
            user_id (int): The ID of the user whose username is to be updated.
            new_username (str): The new username.

        Returns:
            bool: `True` if the username was successfully updated (one row affected),
                  `False` otherwise (e.g., user not found, or username conflict).

        Raises:
            asyncpg.UniqueViolationError: If the `new_username` already exists for
                                          another user.
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Updates the `username` field of a record in the `users` table.
            - Logs status or errors.
        """
        query = f"""
            UPDATE {Users.TABLE_NAME}
            SET {Users.USERNAME} = $1
            WHERE {Users.ID} = $2
        """
        params = (new_username, user_id)
        try:
            status = await self._execute(query, params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(
                    f"Username updated for user ID {user_id} to '{new_username}'."
                )
            else:
                logger.warning(
                    f"Update username for user ID {user_id} to '{new_username}' "
                    f"executed but status was '{status}'. User might not exist."
                )
            return updated
        except asyncpg.UniqueViolationError:
            logger.warning(
                f"Attempt to update username for user ID {user_id} to an already existing username: '{new_username}'."
            )
            # This specific error should ideally be handled by the service layer
            # to provide a user-friendly message. Re-raise for now.
            raise
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating username for user ID {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating username for user ID {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def update_password(self, user_id: int, new_hashed_password: str) -> bool:
        """
        Updates the hashed password for a given user ID.

        Args:
            user_id (int): The ID of the user whose password is to be updated.
            new_hashed_password (str): The new, securely hashed password.

        Returns:
            bool: `True` if the password was successfully updated (one row affected),
                  `False` otherwise (e.g., user not found).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Updates the `hashed_password` field of a record in the `users` table.
            - Logs status or errors.
        """
        query = f"""
            UPDATE {Users.TABLE_NAME}
            SET {Users.HASHED_PASSWORD} = $1
            WHERE {Users.ID} = $2
        """
        params = (new_hashed_password, user_id)
        try:
            status = await self._execute(query, params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(f"Password updated for user ID {user_id}.")
            else:
                logger.warning(
                    f"Update password for user ID {user_id} executed but status was '{status}'. "
                    "User might not exist."
                )
            return updated
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating password for user ID {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating password for user ID {user_id}: {e}",
                exc_info=True,
            )
            raise
