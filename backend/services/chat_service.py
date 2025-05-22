"""
Chat service for managing chat sessions and processing messages with LLMs.

This service handles the business logic for chat functionalities, including
session management (CRUD operations on chats), message management (CRUD
operations on messages within chats), and interaction with Large Language
Models (LLMs) to generate responses to user queries. It ensures that
operations are performed in the context of authenticated users and their
respective data.
"""

import logging
import json
import asyncio
import time
from typing import (
    List,
    Dict,
    Any,
    Optional,
    Union,
    AsyncGenerator,
)
from datetime import datetime

from db.repositories.chat_repository import ChatRepository
from db.repositories.message_repository import MessageRepository
from db.repositories.api_key_repository import (
    ApiKeyRepository,
)
from core.llm.client import AsyncLLMClient
from models import (
    Chat,
    ChatCreate,
    Message,
    MessageCreate,
    ChatAnswer,  # Note: ChatAnswer seems unused in this file, consider removal if not needed elsewhere
    User,
    ApiKey,
)

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service layer for managing chat sessions, messages, and LLM interactions.
    """

    def __init__(
        self,
        chat_repo: ChatRepository,
        message_repo: MessageRepository,
        api_key_repo: ApiKeyRepository,
    ):
        """Initializes the ChatService with necessary repositories.

        Args:
            chat_repo: Repository for chat data operations.
            message_repo: Repository for message data operations.
            api_key_repo: Repository for API key data operations.

        Side Effects:
            Initializes internal repository attributes (`_chat_repo`,
            `_message_repo`, `_api_key_repo`).
        """
        self._chat_repo = chat_repo
        self._message_repo = message_repo
        self._api_key_repo = api_key_repo

    # --- Chat Session Management (User-Aware) ---

    async def get_all_chats(self, user_id: int) -> List[Chat]:
        """Retrieves all chat sessions for a specific user.

        Args:
            user_id: The ID of the user whose chats are to be retrieved.

        Returns:
            A list of `Chat` model instances, each representing a chat session
            belonging to the user. Returns an empty list if the user has no chats.

        Side Effects:
            Reads chat data from the database via the chat repository.
        """
        chats_records = await self._chat_repo.get_all(user_id=user_id)
        return [Chat.model_validate(dict(chat_record)) for chat_record in chats_records]

    async def get_chat_by_id(self, chat_id: int, user_id: int) -> Optional[Chat]:
        """Retrieves a specific chat session by its ID for a given user.

        The method also fetches and populates the messages associated with the chat.

        Args:
            chat_id: The ID of the chat session to retrieve.
            user_id: The ID of the user who owns the chat.

        Returns:
            A `Chat` model instance populated with its messages if found and
            owned by the user, otherwise None.

        Side Effects:
            Reads chat and associated message data from the database.
        """
        chat_record = await self._chat_repo.get_by_id(chat_id=chat_id, user_id=user_id)
        if not chat_record:
            return None

        messages = await self.get_messages_by_chat_id(chat_id)

        chat_data = dict(chat_record)
        chat_data["messages"] = messages
        return Chat.model_validate(chat_data)

    async def create_chat(self, chat_data: ChatCreate, user_id: int) -> Chat:
        """Creates a new chat session for a specific user.

        Args:
            chat_data: A `ChatCreate` model instance containing the title for the new chat.
            user_id: The ID of the user for whom the chat is being created.

        Returns:
            The newly created `Chat` model instance.

        Raises:
            ValueError: If the chat creation fails in the repository or if the
                        newly created chat cannot be retrieved.

        Side Effects:
            Adds a new chat record to the database associated with the user.
        """
        chat_id = await self._chat_repo.add(title=chat_data.title, user_id=user_id)
        if chat_id is None:  # Should ideally not happen if repository raises on failure
            logger.error(
                f"Chat repository failed to return a chat_id for user {user_id} with title '{chat_data.title}'."
            )
            raise ValueError(f"Failed to create chat for user {user_id}")

        created_chat = await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)
        if created_chat is None:
            # This indicates an issue, as the chat was supposedly created.
            logger.error(
                f"Failed to retrieve newly created chat {chat_id} for user {user_id} immediately after creation."
            )
            raise ValueError(
                f"Failed to retrieve newly created chat {chat_id} for user {user_id}"
            )
        return created_chat

    async def update_chat(
        self, chat_id: int, chat_data: ChatCreate, user_id: int
    ) -> Optional[Chat]:
        """Updates an existing chat session's title for a specific user.

        Args:
            chat_id: The ID of the chat session to update.
            chat_data: A `ChatCreate` model instance containing the new title.
            user_id: The ID of the user who owns the chat.

        Returns:
            The updated `Chat` model instance if successful and the chat belongs
            to the user, otherwise None.

        Side Effects:
            Modifies the title of an existing chat record in the database,
            provided the chat_id and user_id match an existing record.
        """
        success = await self._chat_repo.update(
            chat_id=chat_id, user_id=user_id, title=chat_data.title
        )

        if not success:
            return None  # Update failed or chat not found for user

        return await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)

    async def delete_chat(self, chat_id: int, user_id: int) -> bool:
        """Deletes a chat session belonging to a specific user.

        Note: This operation might also need to handle the deletion of associated
        messages, depending on the desired data retention policy. Currently,
        message deletion is commented out and relies on repository or database
        cascades if configured.

        Args:
            chat_id: The ID of the chat session to delete.
            user_id: The ID of the user who owns the chat.

        Returns:
            True if the chat session was successfully deleted, False otherwise
            (e.g., chat not found or not owned by the user).

        Side Effects:
            Removes a chat record from the database. May also remove associated
            messages if such logic is enabled (currently commented out).
            # Example:
            # messages_deleted = await self._message_repo.delete_by_chat_id(chat_id)
            # if not messages_deleted:
            #     logger.warning(f"Could not delete all messages for chat {chat_id} during chat deletion.")
        """
        return await self._chat_repo.delete(chat_id=chat_id, user_id=user_id)

    # --- Message Management ---

    async def get_messages_by_chat_id(self, chat_id: int) -> List[Message]:
        """Retrieves all messages for a given chat session.

        Args:
            chat_id: The ID of the chat session whose messages are to be retrieved.

        Returns:
            A list of `Message` model instances associated with the chat_id.
            Returns an empty list if the chat has no messages.

        Side Effects:
            Reads message data from the database.
        """
        message_records = await self._message_repo.get_by_chat_id(chat_id)
        return [
            Message.model_validate(dict(msg_record)) for msg_record in message_records
        ]

    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """Retrieves a specific message by its ID.

        Args:
            message_id: The ID of the message to retrieve.

        Returns:
            A `Message` model instance if found, otherwise None.

        Side Effects:
            Reads message data from the database.
        """
        message_record = await self._message_repo.get_by_id(message_id)
        if not message_record:
            return None
        return Message.model_validate(dict(message_record))

    async def create_message(self, message_create_data: MessageCreate) -> Message:
        """Creates a new message within a chat session.

        User context (ownership of the chat_id) is assumed to be verified
        by the calling method (e.g., `process_question`) before this method
        is invoked. If this method could be called directly from an API endpoint
        without prior user context validation, such checks should be added here.

        Args:
            message_create_data: A `MessageCreate` model instance containing the
                                 details of the message to be created (chat_id,
                                 sender, content, optional sequence_number).

        Returns:
            The newly created `Message` model instance.

        Raises:
            ValueError: If the message creation fails in the repository or if
                        the newly created message cannot be retrieved.

        Side Effects:
            Adds a new message record to the database associated with the given chat_id.
            The sequence number for the message might be generated by the repository
            if not explicitly provided.
        """
        # The message repository's `add` method handles sequence number generation
        # if `sequence_number` is None in `message_create_data`.
        created_message_data = await self._message_repo.add(
            chat_id=message_create_data.chat_id,
            sender=message_create_data.sender,
            content=message_create_data.content,
            sequence_number=message_create_data.sequence_number,
        )

        if created_message_data is None:
            error_msg = f"Failed to save message to database for chat {message_create_data.chat_id} or retrieve it."
            logger.error(error_msg)
            raise ValueError(error_msg)

        return Message.model_validate(dict(created_message_data))

    async def delete_message(self, message_id: int) -> bool:
        """Deletes a specific message by its ID.

        Note: User context checks (i.e., ensuring the user deleting the message
        has rights to do so, typically by checking ownership of the parent chat)
        are not performed in this method directly. Such checks should be
        implemented in the calling layer (e.g., API endpoint handler) if this
        method can be invoked in a way that bypasses user authorization.

        Args:
            message_id: The ID of the message to delete.

        Returns:
            True if the message was successfully deleted, False otherwise.

        Side Effects:
            Removes a message record from the database.
        """
        return await self._message_repo.delete(message_id)

    # --- LLM Interaction (User-Aware) ---

    async def process_question(
        self, content: str, user: User, chat_id: int
    ) -> AsyncGenerator[str, None]:
        """
        Processes a user's question within a specific chat, streams the LLM's
        response, and saves the full response to the database.

        This method orchestrates several steps:
        1. Validates chat ownership and fetches chat history.
        2. Retrieves the user's API key and initializes an LLM client.
        3. Prepares the message history for the LLM, including a system prompt.
        4. Streams the LLM's response chunks back to the caller.
        5. Asynchronously saves the complete LLM response as a new message.

        Args:
            content: The content of the user's question.
            user: The authenticated `User` object making the request.
            chat_id: The ID of the chat session where the question is being asked.
                     This chat must belong to the provided user.

        Yields:
            str: Chunks of the LLM's response as they are generated.
                 Error messages may also be yielded if issues occur during streaming
                 or LLM client initialization.

        Raises:
            ValueError: If the `chat_id` is invalid, does not belong to the user,
                        or if critical errors prevent LLM interaction (e.g., no
                        valid API key after attempting initialization).

        Side Effects:
            - Reads chat history and API key data from the database.
            - Makes external calls to an LLM service.
            - Creates new message records in the database for the user's question
              (implicitly handled by endpoint usually) and the LLM's response.
            - Logs various stages of the process, including errors and warnings.
        """
        messages_for_llm: List[Dict[str, str]] = []
        user_id = user.id

        # Step 1: Validate chat_id and fetch chat history
        logger.info(f"Processing question for user {user_id} in chat {chat_id}.")
        chat = await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            error_msg = (
                f"Chat ID {chat_id} not found or does not belong to user {user_id}."
            )
            logger.error(error_msg)
            # This ValueError will be caught by the API endpoint to return a 404 or 403.
            raise ValueError(error_msg)

        chat_messages = chat.messages or []
        if chat_messages:
            # Prepare chat history for LLM: sort by timestamp and take the last 10 messages.
            # Ensure timestamp is not None before sorting to avoid runtime errors.
            valid_chat_messages = [m for m in chat_messages if m.timestamp is not None]
            # Type ignore used as Pydantic models can sometimes confuse type checkers with datetime.
            sorted_chat_messages = sorted(valid_chat_messages, key=lambda m: m.timestamp)  # type: ignore

            messages_for_llm.extend(
                [
                    {"role": msg.sender, "content": msg.content}
                    for msg in sorted_chat_messages[
                        -10:
                    ]  # Use the last 10 messages for context
                ]
            )
        logger.debug(
            f"Prepared {len(messages_for_llm)} messages from history for LLM context for chat {chat_id}."
        )

        # Add current user message to the history for the LLM
        messages_for_llm.append({"role": "user", "content": content})

        # Step 2: Get user-specific LLM client
        llm_client: Optional[AsyncLLMClient] = None
        api_keys_data = await self._api_key_repo.get_all(user_id)

        if not api_keys_data:
            logger.warning(
                f"No API keys found for user {user_id}. Cannot initialize LLM client."
            )
        else:
            # Attempt to initialize LLM client with the first valid API key found.
            for key_data_row in api_keys_data:
                try:
                    # Validate raw database data against the Pydantic model.
                    api_key_model = ApiKey.model_validate(dict(key_data_row))
                    logger.info(
                        f"Attempting to use API key ID {api_key_model.id}for user {user_id}."
                    )
                    llm_client = AsyncLLMClient(
                        base_url=str(api_key_model.base_url),
                        api_key=api_key_model.api_key,
                        model=api_key_model.model,
                        context=api_key_model.context,  # This maps to system prompt or similar
                        max_output_tokens=api_key_model.max_output_tokens,
                    )
                    logger.info(
                        f"Successfully initialized LLM client for user {user_id} using API key ID {api_key_model.id}."
                    )
                    break  # Found a valid key and initialized client, stop iterating.
                except (
                    Exception
                ) as e:  # Catches Pydantic validation errors or other issues
                    logger.error(
                        f"Failed to validate or instantiate LLM client for API key data: {key_data_row}. Error: {e}",
                        exc_info=True,  # Log full traceback for debugging
                    )
                    continue  # Try next key

        if llm_client is None:
            # If no LLM client could be initialized after trying all keys.
            error_msg = f"No valid LLM API key found or LLM client could not be initialized for user {user_id}."
            logger.error(error_msg)
            # Provide a user-friendly message and save it as an assistant response.
            error_response_content = "Sorry, I cannot process your request. No valid LLM API key is configured, or the LLM client could not be initialized."
            try:
                await self.create_message(
                    MessageCreate(
                        chat_id=chat_id,
                        sender="assistant",
                        content=error_response_content,
                        sequence_number=None,  # Repository handles sequence
                    )
                )
            except Exception as e_save:
                logger.error(
                    f"Failed to save error message for LLM init failure for chat {chat_id}: {e_save}"
                )

            yield error_response_content  # Yield to inform the user via stream
            return  # Critical failure, stop processing.

        # Step 3: Add system prompt if not already present or overridden by API key context
        # The AsyncLLMClient might handle its own system prompt via the 'context' param.
        # This is a fallback or supplementary system prompt.
        system_prompt = "你是一个有帮助的AI助手。"  # Default system prompt
        if not messages_for_llm or messages_for_llm[0].get("role") != "system":
            # Check if the client already set a system prompt from ApiKey.context
            # This simplistic check assumes 'context' from ApiKey is used as a system message by AsyncLLMClient.
            # A more robust solution might involve AsyncLLMClient exposing whether a system prompt is set.
            # For now, if the LLM client has a 'context' (which is like a system prompt), we might not need to add another one.
            # However, the current AsyncLLMClient uses 'context' for general parameters, not directly as a system message in the 'messages' list.
            # So, prepending a system message here is generally safe.
            # If ApiKey.context IS the system prompt, then the LLM client should inject it.
            # If it's just additional configuration, then this system prompt is fine.
            # Assuming client.context IS NOT automatically the first system message in the list for the LLM.
            messages_for_llm.insert(0, {"role": "system", "content": system_prompt})
            logger.debug(
                f"Prepended default system prompt to LLM messages for chat {chat_id}."
            )

        # Step 4: Stream response from LLM
        full_assistant_response = ""
        try:
            logger.info(f"Streaming LLM completion for chat {chat_id}, user {user_id}.")
            async with llm_client as client_instance:  # Ensures client resources are managed
                stream = client_instance.stream_completion_content(
                    messages=messages_for_llm
                )
                async for chunk in stream:
                    full_assistant_response += chunk
                    yield chunk
            logger.info(
                f"LLM stream completed for chat {chat_id}. Full response length: {len(full_assistant_response)} chars."
            )
        except Exception as e:
            error_msg = (
                f"Error during LLM streaming for user {user_id}, chat {chat_id}: {e}"
            )
            logger.error(error_msg, exc_info=True)
            # Yield an error message to the client to inform them of the failure.
            yield f"Sorry, an error occurred while communicating with the LLM: {str(e)}"
            # Save this LLM communication error as an assistant message for record.
            try:
                await self.create_message(
                    MessageCreate(
                        chat_id=chat_id,
                        sender="assistant",
                        content=f"LLM Error: {str(e)}",
                        sequence_number=None,
                    )
                )
            except Exception as e_save:
                logger.error(
                    f"Failed to save LLM streaming error message for chat {chat_id}: {e_save}"
                )
            return  # Stop further processing for this question.
        # No explicit finally block needed for llm_client.close() due to `async with`.

        # Step 5: Save the complete assistant message asynchronously
        if full_assistant_response:
            logger.debug(
                f"Proceeding to save full assistant response for chat {chat_id}."
            )
            try:
                # Create a background task to save the message.
                # This allows the stream to terminate and the client to receive the full
                # streamed response without waiting for the database write to complete.
                async def save_message_task():
                    try:
                        assistant_message_create = MessageCreate(
                            chat_id=chat_id,
                            sender="assistant",
                            content=full_assistant_response,
                            sequence_number=None,  # Repository handles sequence
                        )
                        await self.create_message(assistant_message_create)
                        logger.info(
                            f"Successfully saved assistant's full response to chat {chat_id} for user {user_id} in background task."
                        )
                    except Exception as e_save_task:
                        logger.error(
                            f"Background task failed to save assistant's message for chat {chat_id}, user {user_id}: {e_save_task}",
                            exc_info=True,
                        )

                # Schedule the save operation to run in the background.
                asyncio.create_task(save_message_task())
                logger.debug(
                    f"Created background task to save assistant message for chat {chat_id}."
                )

            except Exception as e_task_create:  # Error creating the asyncio task itself
                logger.error(
                    f"Failed to create asyncio task for saving assistant's message for chat {chat_id}: {e_task_create}",
                    exc_info=True,
                )
                # Fallback: If task creation fails, attempt to save synchronously, though this is not ideal
                # as it would block the stream's apparent completion.
                # For now, just log the error of task creation.
        else:
            # Handle cases where the LLM returns an empty response.
            logger.warning(
                f"LLM generated an empty response for chat {chat_id}, user {user_id}. Saving a placeholder message."
            )
            placeholder_content = "[LLM returned an empty response]"
            try:
                await self.create_message(
                    MessageCreate(
                        chat_id=chat_id,
                        sender="assistant",
                        content=placeholder_content,
                        sequence_number=None,  # Repository handles sequence
                    )
                )
            except Exception as e_save_empty:
                logger.error(
                    f"Failed to save placeholder for empty LLM response for chat {chat_id}: {e_save_empty}"
                )
            yield placeholder_content  # Inform client about empty response
