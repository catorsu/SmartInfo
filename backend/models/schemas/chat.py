"""
Pydantic Schemas for Chat Functionality.

This module defines Pydantic models for representing chat sessions and messages
within the SmartInfo application. These schemas are used for data validation in
API requests, serialization for API responses, and as data structures for
internal service and repository layers.

Key Schemas:
  - MessageBase, MessageCreate, Message: For individual chat messages.
  - ChatFields, ChatCreate, Chat: For chat sessions.
  - MessageResponse, ChatResponse, ChatListResponseItem: For API responses.
  - ChatAnswer, Question: For LLM interaction payloads.
"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class MessageBase(BaseModel):
    """
    Base schema for core message data, shared by create and full message models.
    It defines the essential information for a message within a chat.
    """

    chat_id: int = Field(
        ...,
        description="ID of the chat session this message belongs to.",
        examples=[101, 205],
    )
    sender: str = Field(
        ...,
        description="Sender of the message, typically 'user' or 'assistant'.",
        examples=["user", "assistant"],
    )
    content: str = Field(
        ...,
        description="The textual content of the message.",
        examples=["Hello, how can I help you?", "What is the capital of France?"],
    )


class MessageCreate(MessageBase):
    """
    Schema for creating a new message. Used as a request body.
    `sequence_number` is optional as it can be determined by the service layer
    based on existing messages in the chat.
    """

    sequence_number: Optional[int] = Field(
        None,
        description="Order of the message within the chat. If None, the service will assign the next available sequence number.",
        examples=[0, 1, 5],
    )
    # user_id is not part of a message; messages belong to a chat, which belongs to a user.


class Message(MessageBase):
    """
    Schema representing a full message object, typically for database representation
    or internal use. Includes database ID and timestamp.
    """

    id: int = Field(
        ..., description="Unique identifier for the message.", examples=[1001, 2050]
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when the message was created.",
        examples=["2023-10-26T10:00:00Z"],
    )
    sequence_number: int = Field(
        ...,
        description="Order of the message within the chat, ensuring chronological display.",
        examples=[0, 1, 2],
    )

    model_config = ConfigDict(from_attributes=True)


class ChatFields(BaseModel):
    """
    Base fields for chat session data, primarily the title.
    Shared by chat creation and full chat models.
    """

    title: str = Field(
        ...,
        max_length=255,
        description="Title of the chat session, often derived from the first user message or set by the user.",
        examples=["Discussing FastAPI", "AI News Summary"],
    )


class ChatCreate(ChatFields):
    """
    Schema for creating a new chat session. Used as a request body.
    The `user_id` is typically derived from the authenticated user context in
    the service layer, not from this payload.
    """

    pass  # Inherits title. user_id is handled by the service.


# No ChatUpdate model is explicitly defined as updates currently only target the title,
# which can be handled by ChatCreate or a more specific ChatTitleUpdate if needed.


class Chat(ChatFields):
    """
    Schema representing a full chat session object, typically for database
    representation or internal use. Includes database ID, user ownership,
    timestamps, and optionally, its messages.
    """

    id: int = Field(
        ..., description="Unique identifier for the chat session.", examples=[1, 42]
    )
    user_id: int = Field(
        ..., description="ID of the user who owns this chat session.", examples=[1, 10]
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when the chat session was created.",
        examples=["2023-10-26T09:00:00Z"],
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when the chat session was last updated (e.g., new message added).",
        examples=["2023-10-26T09:05:00Z"],
    )
    messages: Optional[List[Message]] = Field(
        None,
        description="List of messages in this chat session. This field is optional and typically loaded on demand when retrieving a specific chat.",
    )

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """
    Schema for representing a message in API responses.
    Excludes `chat_id` as it's usually part of the parent `ChatResponse`.
    """

    id: int = Field(
        ..., description="Unique identifier for the message.", examples=[1001]
    )
    sender: str = Field(
        ...,
        description="Sender of the message ('user' or 'assistant').",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="Content of the message.",
        examples=["What is the weather like?"],
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when the message was created.",
        examples=["2023-10-26T10:00:00Z"],
    )
    sequence_number: int = Field(
        ...,
        description="Order of the message within the chat.",
        examples=[0],
    )

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """
    Schema for representing a full chat session in API responses.
    Excludes `user_id` for security/privacy. Messages use `MessageResponse`.
    """

    id: int = Field(
        ..., description="Unique identifier for the chat session.", examples=[42]
    )
    title: str = Field(
        ...,
        max_length=255,
        description="Title of the chat session.",
        examples=["AI in Healthcare"],
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Creation timestamp (ISO 8601 format).",
        examples=["2023-10-26T09:00:00Z"],
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last modification timestamp (ISO 8601 format).",
        examples=["2023-10-26T09:05:00Z"],
    )
    messages: Optional[List[MessageResponse]] = Field(
        None,
        description="List of messages in this chat session (optional, loaded on demand).",
    )

    model_config = ConfigDict(from_attributes=True)


class ChatListResponseItem(BaseModel):
    """
    Schema for representing a chat session in a list (e.g., sidebar).
    Excludes `user_id` and the full `messages` list for brevity.
    """

    id: int = Field(
        ..., description="Unique identifier for the chat session.", examples=[42]
    )
    title: str = Field(
        ...,
        max_length=255,
        description="Title of the chat session.",
        examples=["AI in Healthcare"],
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Creation timestamp (ISO 8601 format).",
        examples=["2023-10-26T09:00:00Z"],
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last modification timestamp (ISO 8601 format).",
        examples=["2023-10-26T09:05:00Z"],
    )

    model_config = ConfigDict(from_attributes=True)


class ChatAnswer(BaseModel):
    """
    Schema representing the structure of an answer from the LLM in a chat context.
    This is typically used by the service layer to structure data received from
    the LLM before it's potentially transformed into a `Message` object.
    """

    chat_id: int = Field(
        ...,
        description="ID of the chat session this answer pertains to.",
        examples=[42],
    )
    message_id: Optional[int] = Field(
        None,
        description="ID of the assistant's message created in the database (if saved before streaming ends).",
        examples=[1002],
    )
    content: str = Field(
        ...,
        description="Content of the assistant's response.",
        examples=["The capital of France is Paris."],
    )


class Question(BaseModel):
    """
    Schema for a user's question submitted to the chat API endpoint.
    """

    content: str = Field(
        ...,
        description="The textual content of the user's question or statement.",
        examples=["What is FastAPI?", "Tell me a joke."],
    )
    chat_id: Optional[int] = Field(
        None,
        description="Optional ID of an existing chat session to continue the conversation. If None, a new chat might be initiated by the service.",
        examples=[42],
    )
