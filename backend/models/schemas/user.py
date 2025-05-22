"""
Pydantic Schemas for User Management.

This module defines Pydantic models related to user accounts in the SmartInfo
application. These schemas are used for creating users, representing user data
retrieved from the database, and handling requests for password or username changes.

Key Schemas:
  - UserBase: Base schema for user data (username).
  - UserCreate: Schema for creating a new user, including password.
  - UserInDBBase: Base schema for user data as stored in the database, including ID and hashed password.
  - User: Schema for representing a user in API responses (excludes sensitive data like hashed_password).
  - UserInDB: Full schema for user data from the database.
  - PasswordChangeRequest: Schema for password change requests.
  - UsernameChangeRequest: Schema for username change requests.
"""

from pydantic import BaseModel, Field, ConfigDict


class UserBase(BaseModel):
    """
    Base schema for user data, primarily containing the username.
    This is inherited by other user-related schemas.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username for the user. Must be between 3 and 50 characters.",
        examples=["john_doe", "jane_smith88"],
    )


class UserCreate(UserBase):
    """
    Schema for creating a new user. Used as a request body for registration.
    Includes the username (from `UserBase`) and a password.
    """

    password: str = Field(
        ...,
        min_length=6,
        description="User's password. Must be at least 6 characters long.",
        examples=["P@$wOrd123", "secure_Pa$w0rd!"],
    )


class UserInDBBase(UserBase):
    """
    Base schema representing user data as it is stored in the database.
    Includes the database ID and the hashed password.
    """

    id: int = Field(
        ...,
        description="Unique identifier for the user in the database.",
        examples=[1, 101],
    )
    hashed_password: str = Field(
        ...,
        description="The user's password, hashed using bcrypt.",
        examples=["$2b$12$EixyP23GjZJzK9n3Y0sLz.uY9fX.cO8qHhJzJzK9n3Y0sLz.uY9fX"],
    )

    model_config = ConfigDict(from_attributes=True)


class User(UserBase):
    """
    Schema for representing a user in API responses.
    This model is typically used to return user information to clients,
    excluding sensitive data like the hashed password.
    """

    id: int = Field(
        ..., description="Unique identifier for the user.", examples=[1, 101]
    )
    # Excludes hashed_password for security.

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserInDBBase):
    """
    Full schema for user data as retrieved from the database, including all fields.
    This is primarily for internal use within the backend.
    """

    # Inherits id, username, hashed_password from UserInDBBase.
    model_config = ConfigDict(from_attributes=True)


class PasswordChangeRequest(BaseModel):
    """
    Schema for handling requests to change a user's password.
    Requires the user's current password for verification and the new password.
    """

    current_password: str = Field(
        ...,
        min_length=6,
        description="The user's current password for verification.",
        examples=["oldP@$wOrd"],
    )
    new_password: str = Field(
        ...,
        min_length=6,
        description="The desired new password. Must be at least 6 characters long.",
        examples=["newP@$wOrd123!"],
    )


class UsernameChangeRequest(BaseModel):
    """
    Schema for handling requests to change a user's username.
    Requires the new username and the user's current password for verification.
    """

    new_username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="The desired new username. Must be between 3 and 50 characters.",
        examples=["john_doe_updated"],
    )
    current_password: str = Field(
        ...,
        min_length=6,
        description="The user's current password for verification before changing the username.",
        examples=["currentP@$wOrd"],
    )
