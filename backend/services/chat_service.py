"""
Chat service for managing chat sessions and processing messages
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
    ChatAnswer,
    User,
    ApiKey,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions and messages"""

    def __init__(
        self,
        chat_repo: ChatRepository,
        message_repo: MessageRepository,
        api_key_repo: ApiKeyRepository,
    ):
        """Initialize the chat service"""
        self._chat_repo = chat_repo
        self._message_repo = message_repo
        self._api_key_repo = api_key_repo

    # --- Chat Session Management (User-Aware) ---

    async def get_all_chats(self, user_id: int) -> List[Chat]:
        """Get all chat sessions for a specific user."""
        chats = await self._chat_repo.get_all(user_id=user_id)
        # Assuming Chat model now includes user_id
        return [
            Chat.model_validate(dict(chat)) for chat in chats
        ]  # Use model_validate for Pydantic v2

    async def get_chat_by_id(self, chat_id: int, user_id: int) -> Optional[Chat]:
        """Get a chat session by ID for a specific user."""
        chat_record = await self._chat_repo.get_by_id(chat_id=chat_id, user_id=user_id)
        if not chat_record:
            return None

        # Get messages for this chat (Message repo doesn't need user_id directly)
        messages = await self.get_messages_by_chat_id(chat_id)

        # Assuming Chat model includes user_id and messages
        chat_data = dict(chat_record)
        chat_data["messages"] = messages
        return Chat.model_validate(dict(chat_data))  # Use model_validate

    async def create_chat(self, chat_data: ChatCreate, user_id: int) -> Chat:
        """Create a new chat session for a specific user."""

        chat_id = await self._chat_repo.add(title=chat_data.title, user_id=user_id)
        if chat_id is None:
            raise ValueError(f"Failed to create chat for user {user_id}")

        created_chat = await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)
        if created_chat is None:
            raise ValueError(
                f"Failed to retrieve newly created chat {chat_id} for user {user_id}"
            )
        return created_chat

    async def update_chat(
        self, chat_id: int, chat_data: ChatCreate, user_id: int
    ) -> Optional[Chat]:
        """Update a chat session belonging to a specific user."""

        # The repository's update method now handles the user_id check
        success = await self._chat_repo.update(
            chat_id=chat_id, user_id=user_id, title=chat_data.title
        )

        if not success:
            return None

        return await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)

    async def delete_chat(self, chat_id: int, user_id: int) -> bool:
        """Delete a chat session belonging to a specific user."""
        # The repository's delete method now handles the user_id check
        # Consider adding logic here to delete associated messages if needed
        # messages_deleted = await self._message_repo.delete_by_chat_id(chat_id)
        # if not messages_deleted: logger.warning(...)
        return await self._chat_repo.delete(chat_id=chat_id, user_id=user_id)

    # --- Message Management (Remains largely unchanged, user context applied via chat_id) ---

    async def get_messages_by_chat_id(self, chat_id: int) -> List[Message]:
        """Get all messages for a chat session"""
        messages = await self._message_repo.get_by_chat_id(chat_id)
        return [
            Message.model_validate(dict(msg)) for msg in messages
        ]  # Use model_validate

    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """Get a message by ID"""
        message_record = await self._message_repo.get_by_id(message_id)
        if not message_record:
            return None
        return Message.model_validate(dict(message_record))  # Use model_validate

    async def create_message(self, message: MessageCreate) -> Message:
        """Create a new message. User context is implicit via chat_id ownership check in process_question."""
        # NOTE: We rely on process_question to verify chat_id ownership before calling this.
        # If create_message could be called directly from an endpoint, add user_id check here.

        if message.sequence_number is not None:
            created_message_data = await self._message_repo.add(
                chat_id=message.chat_id,
                sender=message.sender,
                content=message.content,
                sequence_number=message.sequence_number,
            )
        else:
            # Rely on the repository to generate the sequence number if not provided
            created_message_data = await self._message_repo.add(
                chat_id=message.chat_id,
                sender=message.sender,
                content=message.content,
                # sequence_number argument is omitted here to use repository default
            )

        if created_message_data is None:
            error_msg = f"Failed to save message to database or retrieve it afterwards for chat {message.chat_id}."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Assuming add returns a dict or record convertible by model_validate
        return Message.model_validate(dict(created_message_data))

    async def delete_message(self, message_id: int) -> bool:
        """Delete a message. Add user context check if needed."""
        # NOTE: Add user context check here if required.
        # E.g., Get message, check message.chat_id, check chat ownership via get_chat_by_id(chat_id, user_id)
        return await self._message_repo.delete(message_id)

    # --- LLM Interaction (User-Aware) ---

    async def process_question(
        self, content: str, user: User, chat_id: int  # chat_id is now mandatory
    ) -> AsyncGenerator[str, None]:
        """
        Process a question for a specific user and stream the LLM's response.
        The full response is saved to the database after the stream completes.

        Args:
            content: The question content.
            user: The authenticated user object.
            chat_id: Chat ID for context (must belong to the user).

        Yields:
            str: Chunks of the LLM's response.

        Raises:
            ValueError: If chat_id is invalid or LLM client cannot be initialized.
        """
        messages_for_llm = []
        user_id = user.id

        # 1. Validate chat_id and fetch chat history
        chat = await self.get_chat_by_id(chat_id=chat_id, user_id=user_id)
        if not chat:
            error_msg = (
                f"Chat ID {chat_id} not found or does not belong to user {user_id}"
            )
            logger.error(error_msg)
            # It's tricky to yield an error message here and also raise for the endpoint.
            # The endpoint should handle this specific ValueError.
            # For now, we'll let the ValueError propagate.
            # yield f'{{"error": "{error_msg}"}}' # Example of yielding JSON error
            raise ValueError(error_msg)

        chat_messages = chat.messages or []
        if chat_messages:
            # Sort by timestamp and take last 10 (if messages exist)
            # Ensure timestamp is not None before sorting
            valid_chat_messages = [m for m in chat_messages if m.timestamp is not None]
            sorted_chat_messages = sorted(valid_chat_messages, key=lambda m: m.timestamp)  # type: ignore

            messages_for_llm.extend(
                [
                    {"role": msg.sender, "content": msg.content}
                    for msg in sorted_chat_messages[-10:]  # Take last 10
                ]
            )

        # Add current user message
        messages_for_llm.append({"role": "user", "content": content})

        # 2. Get user-specific LLM client
        llm_client: Optional[AsyncLLMClient] = None
        api_keys_data = await self._api_key_repo.get_all(user_id)

        if not api_keys_data:
            logger.warning(f"No API keys found for user {user_id}.")
        else:
            # Use the first valid API key found
            for key_data in api_keys_data:
                try:
                    api_key_model = ApiKey.model_validate(
                        dict(key_data)
                    )  # Renamed to avoid conflict
                    logger.info(
                        f"Using API key ID {api_key_model.id} for user {user_id}."
                    )
                    llm_client = AsyncLLMClient(
                        base_url=api_key_model.base_url,
                        api_key=api_key_model.api_key,
                        model=api_key_model.model,
                        context=api_key_model.context,
                        max_output_tokens=api_key_model.max_output_tokens,
                    )
                    break  # Found a valid key, stop iterating
                except Exception as e:
                    logger.error(
                        f"Failed to validate or instantiate LLM client for API key data: {key_data}. Error: {e}",
                        exc_info=True,
                    )
                    continue

        if llm_client is None:
            error_msg = f"No valid LLM API key found or LLM client could not be initialized for user {user_id}."
            logger.error(error_msg)
            error_response_content = "Sorry, I cannot process your request. No valid LLM API key is configured or the LLM client could not be initialized."
            await self.create_message(
                MessageCreate(
                    chat_id=chat_id,
                    sender="assistant",
                    content=error_response_content,
                    sequence_number=None,
                )
            )
            yield error_response_content
            return

        # 3. Add system prompt if not present
        system_prompt = "你是一个有帮助的AI助手。"
        if not messages_for_llm or messages_for_llm[0].get("role") != "system":
            messages_for_llm.insert(0, {"role": "system", "content": system_prompt})

        # 4. Stream response from LLM
        full_assistant_response = ""
        try:
            async with llm_client as client_instance:
                stream = client_instance.stream_completion_content(
                    messages=messages_for_llm
                )
                async for chunk in stream:
                    full_assistant_response += chunk
                    yield chunk
        except Exception as e:
            error_msg = f"Error during LLM streaming for user {user_id}: {e}"
            logger.error(error_msg, exc_info=True)
            # Yield an error message to the client
            yield f"Sorry, an error occurred while communicating with the LLM: {str(e)}"
            # Optionally save this error as an assistant message
            await self.create_message(
                MessageCreate(
                    chat_id=chat_id,
                    sender="assistant",
                    content=f"LLM Error: {str(e)}",
                    sequence_number=None,
                )
            )
            return  # Stop further processing
        finally:
            if (
                llm_client
            ):  # Ensure client is closed if not using context manager from pool
                await llm_client.close()

        # 5. Save the complete assistant message asynchronously
        if full_assistant_response:
            try:
                # Create a background task to save the message without blocking the stream's end
                async def save_message_task():
                    try:
                        assistant_message_create = MessageCreate(
                            chat_id=chat_id,
                            sender="assistant",
                            content=full_assistant_response,
                            sequence_number=None,  # Let the repository handle this
                        )
                        await self.create_message(assistant_message_create)
                        logger.info(
                            f"Successfully saved assistant's full response to chat {chat_id} for user {user_id}"
                        )
                    except Exception as e_save:
                        logger.error(
                            f"Failed to save assistant's message for chat {chat_id}, user {user_id}: {e_save}",
                            exc_info=True,
                        )

                asyncio.create_task(save_message_task())

            except Exception as e_task_create:
                logger.error(
                    f"Failed to create task for saving assistant's message: {e_task_create}",
                    exc_info=True,
                )
        else:
            logger.warning(
                f"LLM generated an empty response for chat {chat_id}, user {user_id}. Nothing to save."
            )
            # Optionally, save an "empty response" message or handle as needed
            await self.create_message(
                MessageCreate(
                    chat_id=chat_id,
                    sender="assistant",
                    content="[LLM returned an empty response]",
                    sequence_number=None,  # Let the repository handle this
                )
            )
            yield "[LLM returned an empty response]"
