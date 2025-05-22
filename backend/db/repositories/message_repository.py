"""
Message Repository Module for SmartInfo.

This module handles all database operations related to chat messages.
It interacts with the 'messages' table to store, retrieve, update, and
delete individual messages associated with chat sessions.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
import asyncpg
from datetime import datetime, timezone

from db.repositories.base_repository import BaseRepository
from db.schema_constants import Messages

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository):
    """
    Repository for handling chat message operations in the database.

    Provides methods for adding, updating, deleting, and retrieving messages
    associated with chat sessions. Sequence numbers for messages within a chat
    can be managed by this repository.
    """

    async def add(
        self,
        chat_id: int,
        sender: str,
        content: str,
        sequence_number: Optional[int] = None,
    ) -> Optional[asyncpg.Record]:
        """
        Adds a new message to a chat session in the database.

        If `sequence_number` is not provided, it attempts to determine the next
        available sequence number for the given `chat_id`.

        Args:
            chat_id (int): The ID of the chat session this message belongs to.
            sender (str): The sender of the message (e.g., 'user', 'assistant').
            content (str): The textual content of the message.
            sequence_number (Optional[int]): The explicit sequence number for
                this message within the chat. If `None`, the next sequence
                number is calculated. Defaults to `None`.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing all
                                      fields of the newly created message (including
                                      its database-generated ID and timestamp) if
                                      successful, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs during insertion.

        Side Effects:
            - Inserts a new record into the `messages` table.
            - If `sequence_number` is `None`, may execute an additional query to
              determine the next sequence number.
            - Logs the addition of the message or any errors encountered.
        """
        try:
            actual_sequence_number: int
            if sequence_number is None:
                next_seq = await self.get_next_sequence_number(chat_id)
                # get_next_sequence_number returns Messages.DEFAULT_SEQUENCE_NUMBER (0) if no messages.
                actual_sequence_number = next_seq
            else:
                actual_sequence_number = sequence_number

            current_time = datetime.now(timezone.utc)

            query_str = f"""
                INSERT INTO {Messages.TABLE_NAME} (
                    {Messages.CHAT_ID}, {Messages.SENDER}, {Messages.CONTENT},
                    {Messages.TIMESTAMP}, {Messages.SEQUENCE_NUMBER}
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING *  -- Returns all columns of the inserted row
            """
            params: Tuple[Any, ...] = (
                chat_id,
                sender,
                content,
                current_time,
                actual_sequence_number,
            )

            new_message_record = await self._fetchone(query_str, params)

            if new_message_record:
                # Accessing ID using the constant, assuming it's lowercase in the record key
                msg_id_key = Messages.ID.lower()
                logger.info(
                    f"Added message with ID {new_message_record[msg_id_key]} to chat {chat_id}"
                )
                return new_message_record
            else:
                logger.error(
                    f"Failed to add message for chat {chat_id}, no record returned after insert."
                )
                return None  # Should ideally not happen if RETURNING * is used and insert is successful

        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to add message for chat {chat_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error adding message for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def update(
        self,
        message_id: int,
        content: Optional[str] = None,
        sequence_number: Optional[int] = None,
    ) -> bool:
        """
        Updates an existing message in the database.

        Allows updating the `content` and/or `sequence_number` of a message.

        Args:
            message_id (int): The ID of the message to update.
            content (Optional[str]): The new content for the message. If `None`,
                content is not changed.
            sequence_number (Optional[int]): The new sequence number for the
                message. If `None`, sequence number is not changed.

        Returns:
            bool: `True` if the update was successful (one row affected),
                  `False` otherwise (e.g., message not found or no fields
                  were specified for update).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Updates a record in the `messages` table if found.
            - Logs the update status or any errors.
        """
        updates: Dict[str, Any] = {}
        params_list: List[Any] = []

        if content is not None:
            updates[Messages.CONTENT] = content
        if sequence_number is not None:
            updates[Messages.SEQUENCE_NUMBER] = sequence_number

        if not updates:
            logger.warning(f"No update data provided for message ID {message_id}.")
            return False  # Or True, if no change is considered a success

        set_clauses = []
        param_idx = 1
        for field, value in updates.items():
            set_clauses.append(f"{field} = ${param_idx}")
            params_list.append(value)
            param_idx += 1

        params_list.append(message_id)  # For WHERE clause

        set_clause_str = ", ".join(set_clauses)
        query_str = f"""
            UPDATE {Messages.TABLE_NAME}
            SET {set_clause_str}
            WHERE {Messages.ID} = ${param_idx}
        """
        final_params = tuple(params_list)

        try:
            status = await self._execute(query_str, final_params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(f"Updated message with ID {message_id}.")
            else:
                logger.warning(
                    f"Update command for message ID {message_id} executed but status was '{status}'. "
                    "Message might not exist or no effective change was made."
                )
            return updated
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to update message {message_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating message {message_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def delete(self, message_id: int) -> bool:
        """
        Deletes a message by its ID from the database.

        Args:
            message_id (int): The ID of the message to delete.

        Returns:
            bool: `True` if the deletion was successful (one row affected),
                  `False` otherwise (e.g., message not found).

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes a record from the `messages` table.
            - Logs the deletion status or any errors.
        """
        query_str = f"DELETE FROM {Messages.TABLE_NAME} WHERE {Messages.ID} = $1"
        params = (message_id,)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(f"Deleted message with ID {message_id}.")
            else:
                logger.warning(
                    f"Delete command for message ID {message_id} executed but status was '{status}'. "
                    "Message might not exist."
                )
            return deleted
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to delete message {message_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting message {message_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def delete_by_chat_id(self, chat_id: int) -> bool:
        """
        Deletes all messages associated with a specific chat ID.

        Args:
            chat_id (int): The ID of the chat whose messages are to be deleted.

        Returns:
            bool: `True` if the delete command was executed successfully (regardless
                  of how many rows were affected, as it could be 0 if the chat
                  had no messages). `False` only if a database error occurs.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes multiple records from the `messages` table.
            - Logs the execution status or any errors.
        """
        query_str = f"DELETE FROM {Messages.TABLE_NAME} WHERE {Messages.CHAT_ID} = $1"
        params = (chat_id,)
        try:
            status = await self._execute(query_str, params)
            # DELETE command returns "DELETE <count>".
            # We consider it successful if no DB error occurred.
            logger.info(
                f"Executed delete for messages in chat {chat_id}. Status: {status}"
            )
            return True  # Indicates command execution success
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to delete messages for chat {chat_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting messages for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, message_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific message by its ID.

        Args:
            message_id (int): The ID of the message to retrieve.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      message details if found, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `messages` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {Messages.ID}, {Messages.CHAT_ID}, {Messages.SENDER},
                   {Messages.CONTENT}, {Messages.TIMESTAMP}, {Messages.SEQUENCE_NUMBER}
            FROM {Messages.TABLE_NAME} WHERE {Messages.ID} = $1
        """
        params = (message_id,)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(f"Failed to get message {message_id}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting message {message_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_by_chat_id(self, chat_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all messages for a specific chat session, ordered by their
        sequence number in ascending order.

        Args:
            chat_id (int): The ID of the chat session.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  representing a message. Returns an empty list
                                  if no messages are found for the chat.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `messages` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {Messages.ID}, {Messages.CHAT_ID}, {Messages.SENDER},
                   {Messages.CONTENT}, {Messages.TIMESTAMP}, {Messages.SEQUENCE_NUMBER}
            FROM {Messages.TABLE_NAME}
            WHERE {Messages.CHAT_ID} = $1
            ORDER BY {Messages.SEQUENCE_NUMBER} ASC, {Messages.TIMESTAMP} ASC
        """
        params = (chat_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get messages for chat {chat_id}: {str(e)}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting messages for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_chat_message_count(self, chat_id: int) -> int:
        """
        Gets the total count of messages in a specific chat session.

        Args:
            chat_id (int): The ID of the chat session.

        Returns:
            int: The total number of messages in the chat. Returns 0 if an
                 error occurs or no messages are found.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT COUNT(*) query.
            - Logs errors if any occur.
        """
        query_str = (
            f"SELECT COUNT(*) FROM {Messages.TABLE_NAME} WHERE {Messages.CHAT_ID} = $1"
        )
        params = (chat_id,)
        try:
            count = await self._fetchval(query_str, params)
            return count if count is not None else 0
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get message count for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Or return 0
        except Exception as e:
            logger.error(
                f"Unexpected error getting message count for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Or return 0

    async def get_next_sequence_number(self, chat_id: int) -> int:
        """
        Determines the next available sequence number for a new message in a chat.

        It finds the maximum existing sequence number for the given `chat_id`
        and returns that number incremented by one. If no messages exist for
        the chat, it returns `Messages.DEFAULT_SEQUENCE_NUMBER` (typically 0).

        Args:
            chat_id (int): The ID of the chat session.

        Returns:
            int: The next sequence number to be used for a new message.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT MAX(...) query.
            - Logs errors if any occur.
        """
        query_str = f"SELECT MAX({Messages.SEQUENCE_NUMBER}) FROM {Messages.TABLE_NAME} WHERE {Messages.CHAT_ID} = $1"
        params = (chat_id,)
        try:
            max_sequence = await self._fetchval(query_str, params)

            if max_sequence is None:  # No messages yet, or MAX returned NULL
                return Messages.DEFAULT_SEQUENCE_NUMBER
            else:
                return int(max_sequence) + 1  # Ensure it's int before adding
        except asyncpg.PostgresError as e:
            logger.error(
                f"Failed to get next sequence number for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Or return default on error
        except Exception as e:
            logger.error(
                f"Unexpected error getting next sequence number for chat {chat_id}: {str(e)}",
                exc_info=True,
            )
            raise  # Or return default
