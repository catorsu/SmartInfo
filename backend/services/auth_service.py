"""
Authentication Service Module
Handles user registration and authentication logic.
"""

from typing import Optional
import logging

from db.repositories import UserRepository
from models import UserCreate, UserInDB
from core.security import get_password_hash, verify_password
from models.schemas.user import User

logger = logging.getLogger(__name__)


class AuthService:
    """
    Service layer for authentication operations.
    """

    def __init__(self, user_repo: UserRepository):
        """Initializes the AuthService with a user repository.

        Args:
            user_repo: An instance of UserRepository for database interactions.

        Side Effects:
            Initializes `self.user_repo`.
        """
        self.user_repo = user_repo

    async def register_user(self, user_create: UserCreate) -> Optional[UserInDB]:
        """Registers a new user.

        Args:
            user_create: Pydantic model containing username and password.

        Returns:
            The created user object (UserInDB) if registration is successful,
            otherwise None (e.g., if username already exists or an error occurs).

        Side Effects:
            Adds a new user to the database if the username is not already taken.
            Prints to console on registration failure or error.
        """
        existing_user = await self.user_repo.get_user_by_username(user_create.username)
        if existing_user:
            # Log this information instead of printing in a production environment
            print(
                f"Registration failed: Username '{user_create.username}' already exists."
            )
            return None

        hashed_password = get_password_hash(user_create.password)

        try:
            new_user = await self.user_repo.add_user(
                username=user_create.username, hashed_password=hashed_password
            )
            return new_user
        except Exception as e:
            # Log this error instead of printing in a production environment
            print(f"Error during user registration: {e}")
            return None

    async def authenticate_user(
        self, username: str, password: str
    ) -> Optional[UserInDB]:
        """Authenticates a user based on username and password.

        Args:
            username: The username provided by the user.
            password: The password provided by the user.

        Returns:
            The user object (UserInDB) if authentication is successful,
            otherwise None.

        Side Effects:
            Reads user data from the database.
        """
        user = await self.user_repo.get_user_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None

        return user

    async def change_password(
        self, user_id: int, current_password_str: str, new_password_str: str
    ) -> bool:
        """Changes the password for a given user.

        Args:
            user_id: The ID of the user whose password is to be changed.
            current_password_str: The user's current password.
            new_password_str: The new password to set.

        Returns:
            True if the password was successfully changed, False otherwise
            (e.g., user not found, incorrect current password).

        Side Effects:
            Updates the user's hashed password in the database if the current
            password is correct. Logs a warning on failed attempts due to
            incorrect current password.
        """
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            return False

        if not verify_password(current_password_str, user.hashed_password):
            logger.warning(
                f"Password change attempt failed for user {user_id}: Incorrect current password."
            )
            return False

        new_hashed_password = get_password_hash(new_password_str)
        return await self.user_repo.update_password(user_id, new_hashed_password)

    async def change_username(
        self, user_id: int, new_username: str, current_password_str: str
    ) -> Optional[User]:
        """Changes the username for a given user.

        Args:
            user_id: The ID of the user whose username is to be changed.
            new_username: The new username to set.
            current_password_str: The user's current password for verification.

        Returns:
            The updated User object if the username was successfully changed or
            if the new username is the same as the current one. Returns None
            if the user is not found or if the current password is incorrect.

        Raises:
            ValueError: If the new username is already taken or the database
                        update operation fails for other reasons.

        Side Effects:
            Updates the user's username in the database if the current password
            is correct and the new username is available and different from
            the current one. Logs warnings for incorrect password attempts and
            info for attempts to change to the same username.
        """
        user_in_db = await self.user_repo.get_user_by_id(user_id)
        if not user_in_db:
            return None

        if not verify_password(current_password_str, user_in_db.hashed_password):
            logger.warning(
                f"Username change attempt failed for user {user_id}: Incorrect current password."
            )
            return None

        if user_in_db.username == new_username:
            logger.info(
                f"User {user_id} attempted to change username to the same value ('{new_username}'). No change made."
            )
            # Return the current user data as no change was made.
            return User.model_validate(user_in_db)

        success = await self.user_repo.update_username(user_id, new_username)
        if not success:
            # This case typically means the username is already taken,
            # as per repository logic.
            raise ValueError("Username already taken or update failed.")

        updated_user_in_db = await self.user_repo.get_user_by_id(user_id)
        if updated_user_in_db:
            return User.model_validate(updated_user_in_db)
        # This case should ideally not be reached if update_username was successful
        # and then get_user_by_id fails, indicating a potential inconsistency.
        # However, adhering to current structure.
        return None
