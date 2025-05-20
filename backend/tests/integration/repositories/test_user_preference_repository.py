"""
Integration Tests for UserPreferenceRepository.
"""

import pytest
import asyncpg
from typing import Optional, Dict, Any

from db.repositories.user_preference_repository import UserPreferenceRepository
from db.repositories.user_repository import UserRepository
from core.security import get_password_hash
from db.schema_constants import UserPreferences

TEST_USER_FOR_UP_REPO = "userpref_user_repo"
TEST_PASSWORD_FOR_UP_REPO = "UserPrefPassRepo123!"


@pytest.fixture
async def test_user_id_for_up_repo(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    hashed_password = get_password_hash(TEST_PASSWORD_FOR_UP_REPO)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_UP_REPO, hashed_password=hashed_password
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def up_repo(db_conn: asyncpg.Connection) -> UserPreferenceRepository:
    return UserPreferenceRepository(connection=db_conn)


@pytest.mark.asyncio
class TestUserPreferenceRepository:
    """Test suite for UserPreferenceRepository methods."""

    async def test_set_preference__new_key__creates_preference(
        self,
        up_repo: UserPreferenceRepository,
        test_user_id_for_up_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_up_repo
        key = "ui_theme_repo_up"  # Unique key
        value = "dark"
        description = "User interface theme repo"

        success = await up_repo.set(
            config_key=key, config_value=value, user_id=user_id, description=description
        )
        assert success is True

        persisted_record = await db_conn.fetchrow(
            f"SELECT * FROM {UserPreferences.TABLE_NAME} WHERE {UserPreferences.KEY} = $1 AND {UserPreferences.USER_ID} = $2",
            key,
            user_id,
        )
        assert persisted_record is not None
        assert persisted_record[UserPreferences.VALUE.lower()] == value

    async def test_set_preference__existing_key__updates_preference(
        self,
        up_repo: UserPreferenceRepository,
        test_user_id_for_up_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_up_repo
        key = "notifications_repo_up"  # Unique key
        initial_value = "enabled"
        await up_repo.set(config_key=key, config_value=initial_value, user_id=user_id)

        updated_value = "disabled"
        success = await up_repo.set(
            config_key=key,
            config_value=updated_value,
            user_id=user_id,
            description="Updated",
        )
        assert success is True

        persisted_record = await db_conn.fetchrow(
            f"SELECT {UserPreferences.VALUE} FROM {UserPreferences.TABLE_NAME} WHERE {UserPreferences.KEY} = $1 AND {UserPreferences.USER_ID} = $2",
            key,
            user_id,
        )
        assert persisted_record is not None
        assert persisted_record[UserPreferences.VALUE.lower()] == updated_value

    async def test_get_preference__key_exists__returns_record(
        self, up_repo: UserPreferenceRepository, test_user_id_for_up_repo: int
    ):
        user_id = test_user_id_for_up_repo
        key = "language_repo_up"  # Unique key
        value = "en-US"
        await up_repo.set(config_key=key, config_value=value, user_id=user_id)

        retrieved_pref = await up_repo.get(config_key=key, user_id=user_id)
        assert retrieved_pref is not None
        assert retrieved_pref[UserPreferences.VALUE.lower()] == value

    async def test_get_all__preferences_exist__returns_dict(
        self, up_repo: UserPreferenceRepository, test_user_id_for_up_repo: int
    ):
        user_id = test_user_id_for_up_repo
        await up_repo.set(
            config_key="pref1_repo_up", config_value="val1_up", user_id=user_id
        )
        await up_repo.set(
            config_key="pref2_repo_up", config_value="val2_up", user_id=user_id
        )

        all_prefs = await up_repo.get_all(user_id=user_id)
        assert isinstance(all_prefs, dict)
        assert len(all_prefs) >= 2
        assert all_prefs.get("pref1_repo_up") == "val1_up"

    async def test_delete_preference__key_exists__returns_true_and_deletes(
        self,
        up_repo: UserPreferenceRepository,
        test_user_id_for_up_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_up_repo
        key_to_delete = "to_delete_pref_repo_up"  # Unique key
        await up_repo.set(
            config_key=key_to_delete, config_value="delete_me_up", user_id=user_id
        )

        delete_successful = await up_repo.delete(
            config_key=key_to_delete, user_id=user_id
        )
        assert delete_successful is True

        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {UserPreferences.TABLE_NAME} WHERE {UserPreferences.KEY} = $1 AND {UserPreferences.USER_ID} = $2",
            key_to_delete,
            user_id,
        )
        assert deleted_record is None

    async def test_clear_all_for_user__deletes_all_prefs_for_user(
        self, up_repo: UserPreferenceRepository, test_user_id_for_up_repo: int
    ):
        user_id = test_user_id_for_up_repo
        await up_repo.set(
            config_key="clear_prefA_repo_up", config_value="A_up", user_id=user_id
        )
        await up_repo.set(
            config_key="clear_prefB_repo_up", config_value="B_up", user_id=user_id
        )

        success = await up_repo.clear_all_for_user(user_id=user_id)
        assert success is True

        all_prefs_after = await up_repo.get_all(user_id)
        assert len(all_prefs_after) == 0
