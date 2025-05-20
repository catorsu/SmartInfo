"""
Integration Tests for UserRepository.

These tests verify the interaction of the UserRepository with a live test database,
ensuring that SQL queries are correct, data is handled properly, and database
constraints are respected.
"""

import pytest
import asyncpg  # For asyncpg.UniqueViolationError
from typing import Dict, Any, Optional

from db.repositories.user_repository import UserRepository
from models.schemas.user import UserInDB  # For asserting return types
from core.security import get_password_hash  # For creating test data
from db.schema_constants import (
    Users,
)  # For direct column name reference in assertions if needed

# Sample data for tests
TEST_USERNAME = "testuser_repo"
TEST_PASSWORD = "StrongPassword123!"
TEST_USERNAME_2 = "testuser_repo_2"


@pytest.fixture
async def user_repo(db_conn: asyncpg.Connection) -> UserRepository:
    """
    Provides a UserRepository instance initialized with the test database connection.
    """
    return UserRepository(connection=db_conn)


@pytest.mark.asyncio
class TestUserRepository:
    """
    Test suite for UserRepository methods.
    """

    async def test_add_user__valid_data__returns_user_in_db_and_persists(
        self, user_repo: UserRepository, db_conn: asyncpg.Connection
    ):
        """
        Tests adding a new user with valid data.
        Verifies that the user is persisted and the returned object matches.
        """
        # Arrange
        hashed_password = get_password_hash(TEST_PASSWORD)

        # Act
        created_user: Optional[UserInDB] = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )

        # Assert
        assert created_user is not None
        assert created_user.username == TEST_USERNAME
        assert created_user.id is not None

        # Verify persistence by fetching directly (optional, but good for confidence)
        persisted_record = await db_conn.fetchrow(
            f"SELECT {Users.ID}, {Users.USERNAME}, {Users.HASHED_PASSWORD} FROM {Users.TABLE_NAME} WHERE {Users.USERNAME} = $1",
            TEST_USERNAME,
        )
        assert persisted_record is not None
        assert persisted_record[Users.ID.lower()] == created_user.id
        assert persisted_record[Users.USERNAME.lower()] == TEST_USERNAME

    async def test_add_user__duplicate_username__returns_none(
        self, user_repo: UserRepository
    ):
        """
        Tests adding a user with a username that already exists.
        Expects None to be returned by add_user due to unique constraint.
        """
        # Arrange: First, add a user
        hashed_password = get_password_hash(TEST_PASSWORD)
        await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )

        # Act: Try to add the same user again
        duplicate_user = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )

        # Assert
        assert duplicate_user is None

    async def test_get_user_by_username__user_exists__returns_user_in_db(
        self, user_repo: UserRepository
    ):
        """
        Tests retrieving an existing user by their username.
        """
        # Arrange
        hashed_password = get_password_hash(TEST_PASSWORD)
        original_user = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )
        assert original_user is not None  # Ensure user was created

        # Act
        retrieved_user = await user_repo.get_user_by_username(TEST_USERNAME)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.id == original_user.id
        assert retrieved_user.username == TEST_USERNAME
        assert retrieved_user.hashed_password == hashed_password

    async def test_get_user_by_username__user_not_exists__returns_none(
        self, user_repo: UserRepository
    ):
        """
        Tests retrieving a user by a username that does not exist.
        """
        # Act
        retrieved_user = await user_repo.get_user_by_username("nonexistentuser_repo")

        # Assert
        assert retrieved_user is None

    async def test_get_user_by_id__user_exists__returns_user_in_db(
        self, user_repo: UserRepository
    ):
        """
        Tests retrieving an existing user by their ID.
        """
        # Arrange
        hashed_password = get_password_hash(TEST_PASSWORD)
        original_user = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )
        assert original_user is not None
        assert original_user.id is not None

        # Act
        retrieved_user = await user_repo.get_user_by_id(original_user.id)

        # Assert
        assert retrieved_user is not None
        assert retrieved_user.id == original_user.id
        assert retrieved_user.username == TEST_USERNAME

    async def test_get_user_by_id__user_not_exists__returns_none(
        self, user_repo: UserRepository
    ):
        """
        Tests retrieving a user by an ID that does not exist.
        """
        # Act
        retrieved_user = await user_repo.get_user_by_id(999999)  # Non-existent ID

        # Assert
        assert retrieved_user is None

    async def test_update_username__valid_change__updates_and_returns_true(
        self, user_repo: UserRepository, db_conn: asyncpg.Connection
    ):
        """
        Tests updating a user's username successfully.
        """
        # Arrange
        hashed_password = get_password_hash(TEST_PASSWORD)
        user = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )
        assert user is not None and user.id is not None
        new_username = "updated_testuser_repo"

        # Act
        update_successful = await user_repo.update_username(user.id, new_username)

        # Assert
        assert update_successful is True
        updated_user_record = await db_conn.fetchrow(
            f"SELECT {Users.USERNAME} FROM {Users.TABLE_NAME} WHERE {Users.ID} = $1",
            user.id,
        )
        assert updated_user_record is not None
        assert updated_user_record[Users.USERNAME.lower()] == new_username

    async def test_update_username__conflict_with_existing__raises_unique_violation(
        self, user_repo: UserRepository
    ):
        """
        Tests updating a username to one that already exists for another user.
        Expects UniqueViolationError to be raised by the repository.
        """
        # Arrange
        hashed_password = get_password_hash(TEST_PASSWORD)
        user1 = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=hashed_password
        )
        await user_repo.add_user(
            username=TEST_USERNAME_2, hashed_password=hashed_password
        )  # User 2 with different username
        assert user1 is not None and user1.id is not None

        # Act & Assert
        with pytest.raises(asyncpg.UniqueViolationError):
            # Attempt to update user1's username to user2's username
            await user_repo.update_username(user1.id, TEST_USERNAME_2)

    async def test_update_username__user_not_exists__returns_false(
        self, user_repo: UserRepository
    ):
        """
        Tests updating username for a non-existent user.
        """
        # Act
        update_successful = await user_repo.update_username(
            999999, "new_username_for_ghost"
        )

        # Assert
        assert update_successful is False

    async def test_update_password__valid_change__updates_and_returns_true(
        self, user_repo: UserRepository, db_conn: asyncpg.Connection
    ):
        """
        Tests updating a user's password successfully.
        """
        # Arrange
        original_hashed_password = get_password_hash(TEST_PASSWORD)
        user = await user_repo.add_user(
            username=TEST_USERNAME, hashed_password=original_hashed_password
        )
        assert user is not None and user.id is not None

        new_password_plain = "NewStrongPassword456!"
        new_hashed_password = get_password_hash(new_password_plain)

        # Act
        update_successful = await user_repo.update_password(
            user.id, new_hashed_password
        )

        # Assert
        assert update_successful is True
        updated_user_record = await db_conn.fetchrow(
            f"SELECT {Users.HASHED_PASSWORD} FROM {Users.TABLE_NAME} WHERE {Users.ID} = $1",
            user.id,
        )
        assert updated_user_record is not None
        assert updated_user_record[Users.HASHED_PASSWORD.lower()] == new_hashed_password
        assert (
            updated_user_record[Users.HASHED_PASSWORD.lower()]
            != original_hashed_password
        )

    async def test_update_password__user_not_exists__returns_false(
        self, user_repo: UserRepository
    ):
        """
        Tests updating password for a non-existent user.
        """
        # Act
        new_hashed_password = get_password_hash("some_new_password")
        update_successful = await user_repo.update_password(999999, new_hashed_password)

        # Assert
        assert update_successful is False
