"""
Integration Tests for ChatRepository.
"""

import pytest
import asyncpg
from typing import Optional

from db.repositories.chat_repository import ChatRepository
from db.repositories.user_repository import UserRepository
from core.security import get_password_hash
from db.schema_constants import Chats

TEST_USER_FOR_CHAT_REPO = "chat_user_repo"
TEST_PASSWORD_FOR_CHAT_REPO = "ChatUserPassRepo123!"


@pytest.fixture
async def test_user_id_for_chat_repo(db_conn: asyncpg.Connection) -> int:
    """Creates a test user for chat tests and returns their ID."""
    user_repo = UserRepository(connection=db_conn)
    hashed_password = get_password_hash(TEST_PASSWORD_FOR_CHAT_REPO)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_CHAT_REPO, hashed_password=hashed_password
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def chat_repo(db_conn: asyncpg.Connection) -> ChatRepository:
    """Provides a ChatRepository instance."""
    return ChatRepository(connection=db_conn)


@pytest.mark.asyncio
class TestChatRepository:
    """Test suite for ChatRepository methods."""

    async def test_add_chat__valid_data__returns_id_and_persists(
        self,
        chat_repo: ChatRepository,
        test_user_id_for_chat_repo: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests adding a new chat session."""
        user_id = test_user_id_for_chat_repo
        title = "Test Chat Session Repo"

        created_id = await chat_repo.add(title=title, user_id=user_id)

        assert created_id is not None
        assert isinstance(created_id, int)

        persisted_record = await db_conn.fetchrow(
            f"SELECT * FROM {Chats.TABLE_NAME} WHERE {Chats.ID} = $1 AND {Chats.USER_ID} = $2",
            created_id,
            user_id,
        )
        assert persisted_record is not None
        assert persisted_record[Chats.TITLE.lower()] == title
        assert persisted_record[Chats.USER_ID.lower()] == user_id

    async def test_get_by_id__chat_exists_and_owned__returns_record(
        self, chat_repo: ChatRepository, test_user_id_for_chat_repo: int
    ):
        """Tests retrieving a chat by ID that exists and is owned by the user."""
        user_id = test_user_id_for_chat_repo
        title = "Gettable Chat Repo"
        created_id = await chat_repo.add(title=title, user_id=user_id)
        assert created_id is not None

        retrieved_chat = await chat_repo.get_by_id(created_id, user_id)

        assert retrieved_chat is not None
        assert retrieved_chat[Chats.ID.lower()] == created_id
        assert retrieved_chat[Chats.TITLE.lower()] == title

    async def test_get_by_id__chat_not_exists__returns_none(
        self, chat_repo: ChatRepository, test_user_id_for_chat_repo: int
    ):
        """Tests retrieving a chat by an ID that does not exist."""
        retrieved_chat = await chat_repo.get_by_id(999888, test_user_id_for_chat_repo)
        assert retrieved_chat is None

    async def test_get_by_id__chat_exists_not_owned__returns_none(
        self,
        chat_repo: ChatRepository,
        test_user_id_for_chat_repo: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests retrieving a chat owned by another user."""
        owner_user_id = test_user_id_for_chat_repo
        owned_chat_id = await chat_repo.add(
            title="Owned Chat by Owner", user_id=owner_user_id
        )
        assert owned_chat_id is not None

        other_user_repo = UserRepository(connection=db_conn)
        other_user = await other_user_repo.add_user(
            "other_chat_user_repo", get_password_hash("pass")
        )
        assert other_user is not None and other_user.id is not None

        retrieved_chat = await chat_repo.get_by_id(owned_chat_id, other_user.id)
        assert retrieved_chat is None

    async def test_get_all__chats_exist__returns_list_of_records(
        self, chat_repo: ChatRepository, test_user_id_for_chat_repo: int
    ):
        """Tests retrieving all chats for a user."""
        user_id = test_user_id_for_chat_repo
        await chat_repo.add(title="Chat 1 Repo", user_id=user_id)
        await chat_repo.add(title="Chat 2 Repo", user_id=user_id)

        all_chats = await chat_repo.get_all(user_id=user_id, limit=5)

        assert len(all_chats) >= 2
        titles_found = {chat[Chats.TITLE.lower()] for chat in all_chats}
        assert "Chat 1 Repo" in titles_found
        assert "Chat 2 Repo" in titles_found

    async def test_update_chat__valid_update__returns_true_and_updates(
        self,
        chat_repo: ChatRepository,
        test_user_id_for_chat_repo: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests updating an existing chat's title."""
        user_id = test_user_id_for_chat_repo
        initial_title = "Initial Chat Title Repo"
        created_id = await chat_repo.add(title=initial_title, user_id=user_id)
        assert created_id is not None

        updated_title = "Updated Chat Title Repo"
        update_successful = await chat_repo.update(
            chat_id=created_id, user_id=user_id, title=updated_title
        )

        assert update_successful is True
        updated_record = await db_conn.fetchrow(
            f"SELECT {Chats.TITLE}, {Chats.UPDATED_AT} FROM {Chats.TABLE_NAME} WHERE {Chats.ID} = $1",
            created_id,
        )
        assert updated_record is not None
        assert updated_record[Chats.TITLE.lower()] == updated_title
        original_record = await chat_repo.get_by_id(created_id, user_id)
        assert original_record is not None
        assert (
            updated_record[Chats.UPDATED_AT.lower()]
            > original_record[Chats.CREATED_AT.lower()]
        )

    async def test_delete_chat__chat_exists_and_owned__returns_true_and_deletes(
        self,
        chat_repo: ChatRepository,
        test_user_id_for_chat_repo: int,
        db_conn: asyncpg.Connection,
    ):
        """Tests deleting a chat that exists and is owned by the user."""
        user_id = test_user_id_for_chat_repo
        chat_to_delete_title = "Chat to Delete Repo"
        created_id = await chat_repo.add(title=chat_to_delete_title, user_id=user_id)
        assert created_id is not None

        delete_successful = await chat_repo.delete(created_id, user_id)

        assert delete_successful is True
        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {Chats.TABLE_NAME} WHERE {Chats.ID} = $1", created_id
        )
        assert deleted_record is None

    async def test_get_count__returns_correct_chat_count(
        self, chat_repo: ChatRepository, test_user_id_for_chat_repo: int
    ):
        """Tests getting the count of chats for a user."""
        user_id = test_user_id_for_chat_repo

        initial_count = await chat_repo.get_count(user_id)

        await chat_repo.add(title="Count Chat 1 Repo", user_id=user_id)
        await chat_repo.add(title="Count Chat 2 Repo", user_id=user_id)

        count = await chat_repo.get_count(user_id)
        assert count == initial_count + 2
