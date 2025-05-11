"""
User Pydantic Schemas
"""

from pydantic import BaseModel, Field, ConfigDict


class UserBase(BaseModel):
    username: str = Field(..., description="Unique username for the user")


class UserCreate(UserBase):
    password: str = Field(..., description="User's password")


class UserInDBBase(UserBase):
    id: int
    hashed_password: str

    model_config = ConfigDict(from_attributes=True)


class User(UserBase):
    id: int = Field(..., description="Unique identifier for the user")
    # Excludes hashed_password

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserInDBBase):
    model_config = ConfigDict(from_attributes=True)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)


class UsernameChangeRequest(BaseModel):
    new_username: str = Field(..., min_length=3)
    current_password: str = Field(..., min_length=6)
