"""
Chat Repository Module for SmartInfo.

This module handles all database operations related to chat sessions, including
creating, retrieving, updating, and deleting chat records. It interacts
primarily with the 'chats' table.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
import asyncpg
from datetime import datetime, timezone

from db.repositories.base_repository import BaseRepository
from db.schema_constants import Chats

logger = logging.getLogger(__name__)


class ChatRepository(BaseRepository):
    """
    Repository for handling chat session operations in the database.

    Provides methods for adding, updating, deleting, and retrieving chat
    sessions, ensuring that operations are performed in the context of a
    specific user.
    """

    async def add(self, title: str, user_id: int) -> Optional[int]:
        """
        Creates a new chat session in the database for a specific user.

        Args:
            title (str): The title of the new chat session.
            user_id (int): The ID of the user creating the chat session.

        Returns:
            Optional[int]: The ID of the newly created chat session if successful,
                           otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs during insertion.

        Side Effects:
            - Inserts a new record into the `chats` table.
            - Logs the creation of the chat or any errors encountered.
        """
        current_time = datetime.now(timezone.utc)
        query_str = f"""
            INSERT INTO {Chats.TABLE_NAME} (
                {Chats.TITLE}, {Chats.CREATED_AT}, {Chats.UPDATED_AT}, {Chats.USER_ID}
            ) VALUES ($1, $2, $3, $4)
            RETURNING {Chats.ID}
        """
        params: Tuple[Any, ...] = (title, current_time, current_time, user_id)

        try:
            chat_id = await self._fetchval(query_str, params)
            if chat_id is not None:
                logger.info(f"Created chat with ID {chat_id} for user {user_id}")
            else:
                # This case might indicate an issue if RETURNING id didn't work as expected
                # or if fetchval returned None for other reasons.
                logger.warning(
                    f"Failed to create chat for user {user_id}, no ID returned from database."
                )
            return chat_id  # chat_id is already Optional[Any]
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to create chat for user {user_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error creating chat for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def update(
        self, chat_id: int, user_id: int, title: Optional[str] = None
    ) -> bool:
        """
        Updates an existing chat session belonging to a specific user.

        Currently, only the title and the `updated_at` timestamp are updated.

        Args:
            chat_id (int): The ID of the chat session to update.
            user_id (int): The ID of the user who owns the chat session.
                This is used to ensure that a user can only update their own chats.
            title (Optional[str]): The new title for the chat session. If `None`,
                the title is not changed (though `updated_at` will still be set).

        Returns:
            bool: `True` if the update was successful (one row affected),
                  `False` otherwise (e.g., chat not found, not owned by user,
                  or no actual change made to the title if it was the only field
                  to update and was provided as None).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Updates a record in the `chats` table if found and owned by the user.
            - Sets the `updated_at` field to the current timestamp.
            - Logs the update status or any errors.
        """
        updates: Dict[str, Any] = {}
        params_list: List[Any] = []  # For building parameters dynamically

        if title is not None:
            updates[Chats.TITLE] = title

        # Always update updated_at
        updates[Chats.UPDATED_AT] = datetime.now(timezone.utc)

        if not updates:  # Should not happen as updated_at is always set
            logger.warning(
                f"No update data provided for chat ID {chat_id}, user {user_id}."
            )
            return False  # Or True if no change is considered success

        set_clauses = []
        param_idx = 1
        for field, value in updates.items():
            set_clauses.append(f"{field} = ${param_idx}")
            params_list.append(value)
            param_idx += 1

        params_list.extend([chat_id, user_id])  # Add ID and user_id for WHERE clause

        set_clause_str = ", ".join(set_clauses)

        query_str = f"""
            UPDATE {Chats.TABLE_NAME}
            SET {set_clause_str}
            WHERE {Chats.ID} = ${param_idx} AND {Chats.USER_ID} = ${param_idx + 1}
        """

        final_params = tuple(params_list)

        try:
            status = await self._execute(query_str, final_params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(f"Updated chat with ID {chat_id} for user {user_id}.")
            else:
                # This could mean the chat_id/user_id didn't match, or no fields actually changed value.
                logger.warning(
                    f"Update command for chat ID {chat_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Chat might not exist, "
                    "not belong to user, or no effective change was made."
                )
            return updated
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to update chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def delete(self, chat_id: int, user_id: int) -> bool:
        """
        Deletes a chat session by its ID, ensuring it belongs to the specified user.

        Args:
            chat_id (int): The ID of the chat session to delete.
            user_id (int): The ID of the user who owns the chat. This ensures
                           a user can only delete their own chat sessions.

        Returns:
            bool: `True` if the deletion was successful (one row affected),
                  `False` otherwise (e.g., chat not found or not owned by user).

        Raises:
            asyncpg.PostgresError: If a database error occurs. Note that foreign
                                   key constraints (e.g., on `messages` table
                                   with `ON DELETE CASCADE`) will handle deletion
                                   of related messages.

        Side Effects:
            - Deletes a record from the `chats` table.
            - If `ON DELETE CASCADE` is set for `messages.chat_id` foreign key,
              all associated messages will also be deleted.
            - Logs the deletion status or any errors.
        """
        query_str = f"DELETE FROM {Chats.TABLE_NAME} WHERE {Chats.ID} = $1 AND {Chats.USER_ID} = $2"
        params = (chat_id, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(f"Deleted chat with ID {chat_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Delete command for chat ID {chat_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Chat might not exist or not belong to user."
                )
            return deleted
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to delete chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, chat_id: int, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific chat session by its ID, ensuring it belongs to the
        specified user.

        Args:
            chat_id (int): The ID of the chat session to retrieve.
            user_id (int): The ID of the user who is expected to own the chat.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      chat session details if found and owned by
                                      the user, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `chats` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {Chats.ID}, {Chats.TITLE}, {Chats.CREATED_AT}, 
                   {Chats.UPDATED_AT}, {Chats.USER_ID}
            FROM {Chats.TABLE_NAME} WHERE {Chats.ID} = $1 AND {Chats.USER_ID} = $2
        """
        params = (chat_id, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting chat {chat_id} for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_all(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """
        Retrieves all chat sessions for a specific user, with pagination.

        Chats are ordered by their last update time in descending order.

        Args:
            user_id (int): The ID of the user whose chat sessions to retrieve.
            limit (int): The maximum number of chat sessions to return.
                         Defaults to 100.
            offset (int): The number of chat sessions to skip before starting to
                          collect the result set. Defaults to 0.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  representing a chat session. Returns an empty
                                  list if no chats are found for the user or
                                  if the offset is beyond the total number of chats.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `chats` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {Chats.ID}, {Chats.TITLE}, {Chats.CREATED_AT}, 
                   {Chats.UPDATED_AT}, {Chats.USER_ID}
            FROM {Chats.TABLE_NAME}
            WHERE {Chats.USER_ID} = $1
            ORDER BY {Chats.UPDATED_AT} DESC
            LIMIT $2 OFFSET $3
        """
        params = (user_id, limit, offset)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get chats for user {user_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting chats for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_count(self, user_id: int) -> int:
        """
        Gets the total number of chat sessions for a specific user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            int: The total count of chat sessions for the user. Returns 0 if
                 an error occurs or no chats are found.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT COUNT(*) query.
            - Logs errors if any occur.
        """
        query_str = (
            f"SELECT COUNT(*) FROM {Chats.TABLE_NAME} WHERE {Chats.USER_ID} = $1"
        )
        params = (user_id,)
        try:
            count = await self._fetchval(query_str, params)
            return count if count is not None else 0
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get chat count for user {user_id}: {str(e)}", exc_info=True
            )
            raise  # Or return 0 depending on desired error handling
        except Exception as e:
            logger.error(
                f"Unexpected error getting chat count for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Or return 0
