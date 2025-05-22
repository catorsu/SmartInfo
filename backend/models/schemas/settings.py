"""
Pydantic Schemas for User Preference Settings.

This module defines Pydantic models for managing user-specific application
preferences. These preferences are stored as key-value pairs and allow users
to customize their experience within the SmartInfo application.

Key Schemas:
  - UserPreferenceBase: Base schema defining the structure of a single preference.
  - UserPreference: Represents a user preference as stored or retrieved.
  - UserPreferenceUpdate: Schema for bulk updating multiple user preferences.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional


class UserPreferenceBase(BaseModel):
    """
    Base schema for a single user preference setting.
    Defines the core fields for a user-specific configuration item.
    """

    config_key: str = Field(
        ...,
        description="Unique key identifying the preference setting, e.g., 'ui_theme', 'llm_default_model'.",
        examples=["ui_theme", "notifications_enabled", "llm_temperature_chat"],
    )
    config_value: str = Field(
        ...,
        description="Value of the preference setting. All values are stored as strings in the database and should be parsed/cast as needed by the application.",
        examples=["dark", "true", "0.7"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional human-readable description of what this preference setting controls.",
        examples=[
            "User interface theme preference",
            "Enable/disable email notifications",
        ],
    )
    user_id: int = Field(
        ...,
        description="ID of the user to whom this preference setting belongs.",
        examples=[1, 42],
    )


class UserPreference(UserPreferenceBase):
    """
    Schema representing a user preference setting as retrieved from the database
    or used internally. It inherits all fields from `UserPreferenceBase`.
    The composite primary key in the database is (`config_key`, `user_id`), so
    no separate `id` field is typically needed for this model.
    """

    # Inherits all fields from UserPreferenceBase.
    # `config_key` and `user_id` together form the unique identifier.

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceUpdate(BaseModel):
    """
    Schema for updating multiple user preference settings in a single request.
    The `settings` field is a dictionary where keys are preference `config_key`s
    and values are the new `config_value`s to be set.
    """

    settings: Dict[str, Any] = Field(
        ...,
        description="A dictionary where keys are preference names (config_key) and values are the new preference values. Values will be converted to strings for storage.",
        examples=[
            {"ui_theme": "dark", "llm_temperature_chat": 0.8, "items_per_page": 25}
        ],
    )
