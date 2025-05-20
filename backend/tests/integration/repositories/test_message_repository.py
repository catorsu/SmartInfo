"""
Integration Tests for MessageRepository.
"""

import pytest
import asyncpg
from typing import Optional

from db.repositories.message_repository import MessageRepository
from db.repositories.chat_repository import ChatRepository
from db.repositories.user_repository import UserRepository
from core.security import get_password_hash
from db.schema_constants import Messages, Chats

TEST_USER_FOR_MSG_REPO = "message_user_repo"
TEST_PASSWORD_FOR_MSG_REPO = "MsgUserPassRepo123!"


@pytest.fixture
async def test_user_id_for_msg_repo(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_MSG_REPO,
        hashed_password=get_password_hash(TEST_PASSWORD_FOR_MSG_REPO),
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def test_chat_id_for_msg_repo(
    db_conn: asyncpg.Connection, test_user_id_for_msg_repo: int
) -> int:
    chat_repo = ChatRepository(connection=db_conn)
    chat_title = "Message Test Chat Repo"  # Unique title
    chat_id = await chat_repo.add(title=chat_title, user_id=test_user_id_for_msg_repo)
    assert chat_id is not None
    return chat_id


@pytest.fixture
async def message_repo(db_conn: asyncpg.Connection) -> MessageRepository:
    return MessageRepository(connection=db_conn)


@pytest.mark.asyncio
class TestMessageRepository:
    """Test suite for MessageRepository methods."""

    async def test_add_message__valid_data__returns_record_and_persists(
        self,
        message_repo: MessageRepository,
        test_chat_id_for_msg_repo: int,
        db_conn: asyncpg.Connection,
    ):
        chat_id = test_chat_id_for_msg_repo
        sender = "user"
        content = "Hello from message repo test!"

        created_message_record = await message_repo.add(
            chat_id=chat_id, sender=sender, content=content
        )

        assert created_message_record is not None
        msg_id = created_message_record[Messages.ID.lower()]
        assert isinstance(msg_id, int)
        assert created_message_record[Messages.SENDER.lower()] == sender
        assert created_message_record[Messages.CONTENT.lower()] == content
        assert created_message_record[Messages.CHAT_ID.lower()] == chat_id
        assert (
            created_message_record[Messages.SEQUENCE_NUMBER.lower()]
            == Messages.DEFAULT_SEQUENCE_NUMBER
        )

        persisted = await db_conn.fetchrow(
            f"SELECT * FROM {Messages.TABLE_NAME} WHERE {Messages.ID} = $1", msg_id
        )
        assert persisted is not None
        assert persisted[Messages.CONTENT.lower()] == content

    async def test_get_by_chat_id__messages_exist__returns_ordered_list(
        self, message_repo: MessageRepository, test_chat_id_for_msg_repo: int
    ):
        chat_id = test_chat_id_for_msg_repo
        await message_repo.add(chat_id, "user", "Second message", sequence_number=1)
        await message_repo.add(chat_id, "assistant", "First message", sequence_number=0)
        await message_repo.add(chat_id, "user", "Third message", sequence_number=2)

        messages = await message_repo.get_by_chat_id(chat_id)
        assert len(messages) == 3
        assert messages[0][Messages.CONTENT.lower()] == "First message"
        assert messages[1][Messages.CONTENT.lower()] == "Second message"
        assert messages[2][Messages.CONTENT.lower()] == "Third message"

    async def test_update_message__valid_update__returns_true_and_updates(
        self,
        message_repo: MessageRepository,
        test_chat_id_for_msg_repo: int,
        db_conn: asyncpg.Connection,
    ):
        chat_id = test_chat_id_for_msg_repo
        original_content = "Original message content for update repo"
        msg_record = await message_repo.add(chat_id, "user", original_content)
        assert msg_record is not None
        msg_id = msg_record[Messages.ID.lower()]

        updated_content = "Updated message content repo!"
        updated_sequence = msg_record[Messages.SEQUENCE_NUMBER.lower()] + 5

        success = await message_repo.update(
            message_id=msg_id, content=updated_content, sequence_number=updated_sequence
        )
        assert success is True

        persisted = await db_conn.fetchrow(
            f"SELECT {Messages.CONTENT}, {Messages.SEQUENCE_NUMBER} FROM {Messages.TABLE_NAME} WHERE {Messages.ID} = $1",
            msg_id,
        )
        assert persisted is not None
        assert persisted[Messages.CONTENT.lower()] == updated_content
        assert persisted[Messages.SEQUENCE_NUMBER.lower()] == updated_sequence

    async def test_delete_message__message_exists__returns_true_and_deletes(
        self,
        message_repo: MessageRepository,
        test_chat_id_for_msg_repo: int,
        db_conn: asyncpg.Connection,
    ):
        chat_id = test_chat_id_for_msg_repo
        msg_record = await message_repo.add(chat_id, "user", "Message to delete repo")
        assert msg_record is not None
        msg_id = msg_record[Messages.ID.lower()]

        success = await message_repo.delete(msg_id)
        assert success is True

        persisted = await db_conn.fetchrow(
            f"SELECT 1 FROM {Messages.TABLE_NAME} WHERE {Messages.ID} = $1", msg_id
        )
        assert persisted is None

    async def test_delete_by_chat_id__deletes_all_messages_for_chat(
        self,
        message_repo: MessageRepository,
        test_chat_id_for_msg_repo: int,
        db_conn: asyncpg.Connection,
    ):
        chat_id = test_chat_id_for_msg_repo
        await message_repo.add(chat_id, "user", "msg A repo")
        await message_repo.add(chat_id, "assistant", "msg B repo")

        count_before = await message_repo.get_chat_message_count(chat_id)
        assert count_before == 2

        success = await message_repo.delete_by_chat_id(chat_id)
        assert success is True

        count_after = await message_repo.get_chat_message_count(chat_id)
        assert count_after == 0
