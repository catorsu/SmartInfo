"""
Pydantic Schemas for API Key Management.

This module defines the Pydantic models used for representing API key
configurations within the SmartInfo application. These schemas are utilized for
request validation, response serialization, and internal data representation
related to user-provided LLM API keys.

Key Schemas:
  - ApiKeyFields: Base fields for creating and updating API keys.
  - ApiKeyCreate: Schema for creating a new API key.
  - ApiKeyUpdate: Schema for updating an existing API key.
  - ApiKey: Represents a full API key object, including database ID and user ID.
  - ApiKeyResponse: Schema for API key data returned in API responses (excludes sensitive info).
"""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, AnyHttpUrl
from typing import Optional


class ApiKeyFields(BaseModel):
    """
    Base fields shared by API key creation and update schemas.
    These fields define the core configuration for an LLM API key.
    """

    model: str = Field(
        ...,
        description="Model identifier, e.g., 'deepseek-chat', 'gpt-4-turbo'. This specifies which LLM model the key is for.",
        examples=["deepseek-chat", "gpt-4-0125-preview"],
    )
    base_url: AnyHttpUrl = Field(
        ...,
        description="The base URL of the LLM API endpoint. For OpenAI, this would be 'https://api.openai.com/v1'. For other providers, it will vary.",
        examples=["https://api.deepseek.com/v1", "https://api.openai.com/v1"],
    )
    api_key: str = Field(
        ...,
        description="The actual API key string provided by the LLM service. This is sensitive data.",
        examples=["sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"],
    )
    context: int = Field(
        ...,
        description="The total context window size (input + output) supported by the model, in tokens.",
        examples=[8192, 16384, 128000],
    )
    max_output_tokens: int = Field(
        ...,
        description="The maximum number of tokens the LLM is allowed to generate in a single response.",
        examples=[2048, 4096],
    )
    description: Optional[str] = Field(
        None,
        description="An optional user-defined description for this API key configuration, e.g., 'My primary DeepSeek key'.",
        examples=["Personal OpenAI Key", "Work DeepSeek Key for Summaries"],
    )


class ApiKeyCreate(ApiKeyFields):
    """
    Schema for creating a new API key configuration.
    This model is used as the request body when a user adds a new API key.
    It inherits all fields from `ApiKeyFields`. The `user_id` is typically
    derived from the authenticated user context in the service layer, not
    from this payload.
    """

    # Inherits fields from ApiKeyFields.
    # user_id is handled by the service layer based on the authenticated user.
    pass


class ApiKeyUpdate(ApiKeyFields):
    """
    Schema for updating an existing API key configuration.
    All fields are optional, allowing partial updates. If a field is not
    provided in the request, its existing value is typically retained.
    """

    # Inherits fields from ApiKeyFields, makes them optional for updates
    model: Optional[str] = Field(
        None,
        description="Updated model identifier (e.g., 'deepseek-chat').",
        examples=["deepseek-coder"],
    )
    base_url: Optional[AnyHttpUrl] = Field(
        None,
        description="Updated API base URL.",
        examples=["https://api.another-provider.com/v1"],
    )
    api_key: Optional[str] = Field(
        None,
        description="Updated API key string (sensitive data).",
        examples=["sk-newkeyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"],
    )
    context: Optional[int] = Field(
        None,
        description="Updated model context length (in tokens).",
        examples=[32768],
    )
    max_output_tokens: Optional[int] = Field(
        None, description="Updated maximum output tokens.", examples=[8192]
    )
    description: Optional[str] = Field(
        None,
        description="Updated optional description for the API key.",
        examples=["Updated key for new model"],
    )


class ApiKey(ApiKeyFields):
    """
    Schema representing a full API key object as stored in the database or
    used internally. Includes database ID, user ownership, and timestamps.
    """

    id: int = Field(
        ...,
        description="Unique identifier for the API key configuration.",
        examples=[1, 101],
    )
    user_id: int = Field(
        ...,
        description="ID of the user who owns this API key configuration.",
        examples=[1, 25],
    )
    created_date: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when this API key configuration was created.",
        examples=["2023-10-26T10:00:00Z"],
    )
    modified_date: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when this API key configuration was last modified.",
        examples=["2023-10-27T14:30:00Z"],
    )

    model_config = ConfigDict(from_attributes=True)


class ApiKeyResponse(BaseModel):
    """
    Schema for representing an API key configuration in API responses.
    Excludes sensitive information like the `api_key` string itself and `user_id`.
    """

    id: int = Field(
        ...,
        description="Unique identifier for the API key configuration.",
        examples=[1, 101],
    )
    model: str = Field(
        ...,
        description="Model identifier, e.g., 'deepseek-chat'.",
        examples=["deepseek-chat"],
    )
    base_url: AnyHttpUrl = Field(
        ...,
        description="The base URL of the LLM API endpoint.",
        examples=["https://api.deepseek.com/v1"],
    )
    context: int = Field(
        ...,
        description="Model context length (in tokens).",
        examples=[16384],
    )
    max_output_tokens: int = Field(
        ..., description="Maximum output tokens.", examples=[4096]
    )
    description: Optional[str] = Field(
        None,
        description="Optional user-defined description for this API key configuration.",
        examples=["Main key for general tasks"],
    )
    created_date: Optional[datetime] = Field(
        None,
        description="Creation timestamp (ISO 8601 format).",
        examples=["2023-10-26T10:00:00Z"],
    )
    modified_date: Optional[datetime] = Field(
        None,
        description="Last modification timestamp (ISO 8601 format).",
        examples=["2023-10-27T14:30:00Z"],
    )

    model_config = ConfigDict(from_attributes=True)
