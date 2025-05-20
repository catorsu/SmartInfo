"""
Integration Tests for ApiKeyRepository.
"""

import pytest
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from db.repositories.api_key_repository import ApiKeyRepository
from db.repositories.user_repository import UserRepository  # To create a test user
from core.security import get_password_hash
from db.schema_constants import ApiConfig, Users

# Test data
TEST_USER_FOR_API_KEY = "apikey_user"
TEST_PASSWORD_FOR_API_KEY = "ApiKeyUserPass123!"


@pytest.fixture
async def test_user_id_for_api_keys(db_conn: asyncpg.Connection) -> int:
    """Creates a test user and returns their ID."""
    user_repo = UserRepository(connection=db_conn)
    hashed_password = get_password_hash(TEST_PASSWORD_FOR_API_KEY)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_API_KEY, hashed_password=hashed_password
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def api_key_repo(db_conn: asyncpg.Connection) -> ApiKeyRepository:
    """Provides an ApiKeyRepository instance."""
    return ApiKeyRepository(connection=db_conn)


@pytest.mark.asyncio
class TestApiKeyRepository:
    """Test suite for ApiKeyRepository methods."""

    async def test_add_api_key__valid_data__returns_id_and_persists(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests adding a new API key configuration."""
        # Arrange
        user_id = test_user_id_for_api_keys
        api_key_data = {
            "model": "test-model-gpt",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-testapikey12345",
            "context": 4096,
            "max_output_tokens": 1024,
            "description": "Test API Key for GPT",
        }

        # Act
        created_id = await api_key_repo.add(user_id=user_id, **api_key_data)

        # Assert
        assert created_id is not None
        assert isinstance(created_id, int)

        persisted_record = await db_conn.fetchrow(
            f"SELECT * FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1 AND {ApiConfig.USER_ID} = $2",
            created_id,
            user_id,
        )
        assert persisted_record is not None
        assert persisted_record[ApiConfig.MODEL.lower()] == api_key_data["model"]
        assert persisted_record[ApiConfig.API_KEY.lower()] == api_key_data["api_key"]

    async def test_get_by_id__key_exists_and_owned__returns_record(
        self, api_key_repo: ApiKeyRepository, test_user_id_for_api_keys: int
    ):
        """Tests retrieving an API key by ID that exists and is owned by the user."""
        # Arrange
        user_id = test_user_id_for_api_keys
        api_key_data = {
            "model": "get-by-id-model",
            "base_url": "https://get.by.id/v1",
            "api_key": "sk-getbyidkey",
            "context": 2048,
            "max_output_tokens": 512,
        }
        created_id = await api_key_repo.add(user_id=user_id, **api_key_data)
        assert created_id is not None

        # Act
        retrieved_key = await api_key_repo.get_by_id(created_id, user_id)

        # Assert
        assert retrieved_key is not None
        assert retrieved_key[ApiConfig.ID.lower()] == created_id
        assert retrieved_key[ApiConfig.MODEL.lower()] == api_key_data["model"]

    async def test_get_by_id__key_not_exists__returns_none(
        self, api_key_repo: ApiKeyRepository, test_user_id_for_api_keys: int
    ):
        """Tests retrieving an API key by an ID that does not exist."""
        # Act
        retrieved_key = await api_key_repo.get_by_id(99999, test_user_id_for_api_keys)
        # Assert
        assert retrieved_key is None

    async def test_get_by_id__key_exists_not_owned__returns_none(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests retrieving an API key owned by another user."""
        # Arrange: Create a key for the primary test user
        user_id_owner = test_user_id_for_api_keys
        api_key_data = {
            "model": "owner-model",
            "base_url": "https://owner.co/v1",
            "api_key": "sk-owner",
            "context": 100,
            "max_output_tokens": 50,
        }
        created_id = await api_key_repo.add(user_id=user_id_owner, **api_key_data)
        assert created_id is not None

        # Create another user
        other_user_repo = UserRepository(connection=db_conn)
        other_user = await other_user_repo.add_user(
            "other_api_user", get_password_hash("pass")
        )
        assert other_user is not None and other_user.id is not None
        other_user_id = other_user.id
        assert other_user_id != user_id_owner

        # Act: Try to retrieve the key as the other user
        retrieved_key = await api_key_repo.get_by_id(created_id, other_user_id)

        # Assert
        assert retrieved_key is None

    async def test_get_all__keys_exist__returns_list_of_records(
        self, api_key_repo: ApiKeyRepository, test_user_id_for_api_keys: int
    ):
        """Tests retrieving all API keys for a user."""
        # Arrange
        user_id = test_user_id_for_api_keys
        await api_key_repo.add(
            user_id=user_id,
            model="model1",
            base_url="url1",
            api_key="key1",
            context=10,
            max_output_tokens=5,
        )
        await api_key_repo.add(
            user_id=user_id,
            model="model2",
            base_url="url2",
            api_key="key2",
            context=20,
            max_output_tokens=10,
        )

        # Act
        all_keys = await api_key_repo.get_all(user_id)

        # Assert
        assert (
            len(all_keys) >= 2
        )  # Could be more if other tests added keys for this user
        models_found = {key[ApiConfig.MODEL.lower()] for key in all_keys}
        assert "model1" in models_found
        assert "model2" in models_found

    async def test_get_all__no_keys_exist__returns_empty_list(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests retrieving all API keys when none exist for the user."""
        # Arrange: Create a new user with no keys
        temp_user_repo = UserRepository(connection=db_conn)
        temp_user = await temp_user_repo.add_user(
            "no_keys_user_api", get_password_hash("pass")
        )
        assert temp_user is not None and temp_user.id is not None

        # Act
        all_keys = await api_key_repo.get_all(temp_user.id)

        # Assert
        assert isinstance(all_keys, list)
        assert len(all_keys) == 0

    async def test_update_api_key__valid_update__returns_true_and_updates(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests updating an existing API key."""
        # Arrange
        user_id = test_user_id_for_api_keys
        created_id = await api_key_repo.add(
            user_id=user_id,
            model="initial_model",
            base_url="initial_url",
            api_key="initial_key",
            context=1000,
            max_output_tokens=500,
        )
        assert created_id is not None

        update_data = {
            "model": "updated_model",
            "base_url": "https://updated.url/v2",
            "api_key": "sk-updatedkey789",
            "context": 8192,
            "max_output_tokens": 2048,
            "description": "Updated Description",
        }

        # Act
        update_successful = await api_key_repo.update(
            api_id=created_id, user_id=user_id, **update_data  # type: ignore
        )

        # Assert
        assert update_successful is True
        updated_record = await db_conn.fetchrow(
            f"SELECT * FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1",
            created_id,
        )
        assert updated_record is not None
        assert updated_record[ApiConfig.MODEL.lower()] == update_data["model"]
        assert (
            updated_record[ApiConfig.DESCRIPTION.lower()] == update_data["description"]
        )
        # Check modified_date was updated (hard to check exact time, but check it's not the created_date)
        assert (
            updated_record[ApiConfig.MODIFIED_DATE.lower()]
            > updated_record[ApiConfig.CREATED_DATE.lower()]
        )

    async def test_update_api_key__not_owned__returns_false(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests updating an API key not owned by the user."""
        # Arrange
        owner_user_id = test_user_id_for_api_keys
        owned_key_id = await api_key_repo.add(
            user_id=owner_user_id,
            model="owned",
            base_url="o",
            api_key="o",
            context=1,
            max_output_tokens=0,
        )
        assert owned_key_id is not None

        other_user_repo = UserRepository(connection=db_conn)
        other_user = await other_user_repo.add_user(
            "other_updater_api", get_password_hash("pass")
        )
        assert other_user is not None and other_user.id is not None

        # Act
        update_successful = await api_key_repo.update(
            api_id=owned_key_id,
            user_id=other_user.id,  # Attempt update as other user
            model="updated_by_other",
            base_url="other.url",
            api_key="other_key",
            context=200,
            max_output_tokens=100,
        )
        # Assert
        assert update_successful is False

    async def test_delete_api_key__key_exists_and_owned__returns_true_and_deletes(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests deleting an API key that exists and is owned by the user."""
        # Arrange
        user_id = test_user_id_for_api_keys
        created_id = await api_key_repo.add(
            user_id=user_id,
            model="to_delete_model",
            base_url="delete.url",
            api_key="delete_key",
            context=50,
            max_output_tokens=20,
        )
        assert created_id is not None

        # Act
        delete_successful = await api_key_repo.delete(created_id, user_id)

        # Assert
        assert delete_successful is True
        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1",
            created_id,
        )
        assert deleted_record is None

    async def test_delete_api_key__not_owned__returns_false(
        self,
        api_key_repo: ApiKeyRepository,
        test_user_id_for_api_keys: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests deleting an API key not owned by the user."""
        # Arrange
        owner_user_id = test_user_id_for_api_keys
        owned_key_id = await api_key_repo.add(
            user_id=owner_user_id,
            model="owned_del",
            base_url="od",
            api_key="od",
            context=1,
            max_output_tokens=0,
        )
        assert owned_key_id is not None

        other_user_repo = UserRepository(connection=db_conn)
        other_user = await other_user_repo.add_user(
            "other_deleter_api", get_password_hash("pass")
        )
        assert other_user is not None and other_user.id is not None

        # Act
        delete_successful = await api_key_repo.delete(owned_key_id, other_user.id)
        # Assert
        assert delete_successful is False
        # Verify original key still exists
        original_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {ApiConfig.TABLE_NAME} WHERE {ApiConfig.ID} = $1",
            owned_key_id,
        )
        assert original_record is not None

    async def test_get_api_count__returns_correct_count(
        self, api_key_repo: ApiKeyRepository, test_user_id_for_api_keys: int
    ):
        """Tests getting the count of API keys for a user."""
        # Arrange
        user_id = test_user_id_for_api_keys
        # Clear existing keys for this user for a clean count, or ensure test isolation
        # For now, assume test isolation from db_conn fixture (transaction rollback)

        initial_count = await api_key_repo.get_api_count(user_id)

        await api_key_repo.add(
            user_id=user_id,
            model="count_model1",
            base_url="c1",
            api_key="c1k",
            context=1,
            max_output_tokens=0,
        )
        await api_key_repo.add(
            user_id=user_id,
            model="count_model2",
            base_url="c2",
            api_key="c2k",
            context=1,
            max_output_tokens=0,
        )

        # Act
        count = await api_key_repo.get_api_count(user_id)

        # Assert
        assert count == initial_count + 2

    async def test_get_api_count__no_keys__returns_zero(
        self, api_key_repo: ApiKeyRepository, db_conn: asyncpg.Connection
    ):
        """Tests getting API key count for a user with no keys."""
        # Arrange: Create a new user with no keys
        temp_user_repo = UserRepository(connection=db_conn)
        temp_user = await temp_user_repo.add_user(
            "no_keys_count_user_api", get_password_hash("pass")
        )
        assert temp_user is not None and temp_user.id is not None

        # Act
        count = await api_key_repo.get_api_count(temp_user.id)
        # Assert
        assert count == 0
