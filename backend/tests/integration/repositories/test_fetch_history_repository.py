"""
Integration Tests for FetchHistoryRepository.
"""

import pytest
import asyncpg
from typing import Optional
from datetime import date, timedelta

from db.repositories.fetch_history_repository import FetchHistoryRepository
from db.repositories.user_repository import UserRepository
from db.repositories.news_source_repository import NewsSourceRepository
from db.repositories.news_category_repository import NewsCategoryRepository

from core.security import get_password_hash
from db.schema_constants import FetchHistory, NewsSource as NSC

TEST_USER_FOR_FETCH_HISTORY = "fetchhist_user_repo"
TEST_PASSWORD_FOR_FETCH_HISTORY = "FetchHistPassRepo123!"


@pytest.fixture
async def test_user_id_for_fetch_history(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_FETCH_HISTORY,
        hashed_password=get_password_hash(TEST_PASSWORD_FOR_FETCH_HISTORY),
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def test_source_id_for_fetch_history(
    db_conn: asyncpg.Connection, test_user_id_for_fetch_history: int
) -> int:
    user_id = test_user_id_for_fetch_history
    category_repo = NewsCategoryRepository(connection=db_conn)
    source_repo = NewsSourceRepository(connection=db_conn)

    cat_name = "FetchHist Test Category Repo"  # Unique name
    category_id = await category_repo.add(name=cat_name, user_id=user_id)
    assert category_id is not None

    source_name = "FetchHist Test Source Repo"  # Unique name
    source_url = "http://fetchhist.example.com/repo_test"  # Unique URL
    source_id = await source_repo.add(
        name=source_name, url=source_url, category_id=category_id, user_id=user_id
    )
    assert source_id is not None
    return source_id


@pytest.fixture
async def fetch_history_repo(db_conn: asyncpg.Connection) -> FetchHistoryRepository:
    return FetchHistoryRepository(connection=db_conn)


@pytest.mark.asyncio
class TestFetchHistoryRepository:
    """Test suite for FetchHistoryRepository methods."""

    async def test_record_completion__new_day_record__creates_record(
        self,
        fetch_history_repo: FetchHistoryRepository,
        test_user_id_for_fetch_history: int,
        test_source_id_for_fetch_history: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_fetch_history
        source_id = test_source_id_for_fetch_history
        items_saved = 5
        task_group_id = "taskgroup_new_day_repo"

        success = await fetch_history_repo.record_completion(
            user_id=user_id,
            source_id=source_id,
            items_saved_this_run=items_saved,
            task_group_id=task_group_id,
        )
        assert success is True

        today = date.today()
        record = await db_conn.fetchrow(
            f"SELECT * FROM {FetchHistory.TABLE_NAME} WHERE {FetchHistory.USER_ID} = $1 AND {FetchHistory.SOURCE_ID} = $2 AND {FetchHistory.RECORD_DATE} = $3",
            user_id,
            source_id,
            today,
        )
        assert record is not None
        assert record[FetchHistory.ITEMS_SAVED_TODAY.lower()] == items_saved
        assert record[FetchHistory.LAST_BATCH_TASK_GROUP_ID.lower()] == task_group_id

    async def test_record_completion__existing_day_record__updates_record(
        self,
        fetch_history_repo: FetchHistoryRepository,
        test_user_id_for_fetch_history: int,
        test_source_id_for_fetch_history: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_fetch_history
        source_id = test_source_id_for_fetch_history
        initial_items = 3
        additional_items = 7
        task_group_id1 = "taskgroup_update1_repo"
        task_group_id2 = "taskgroup_update2_repo"
        today = date.today()

        await fetch_history_repo.record_completion(
            user_id, source_id, initial_items, task_group_id1
        )
        success = await fetch_history_repo.record_completion(
            user_id, source_id, additional_items, task_group_id2
        )
        assert success is True

        record = await db_conn.fetchrow(
            f"SELECT * FROM {FetchHistory.TABLE_NAME} WHERE {FetchHistory.USER_ID} = $1 AND {FetchHistory.SOURCE_ID} = $2 AND {FetchHistory.RECORD_DATE} = $3",
            user_id,
            source_id,
            today,
        )
        assert record is not None
        assert (
            record[FetchHistory.ITEMS_SAVED_TODAY.lower()]
            == initial_items + additional_items
        )
        assert record[FetchHistory.LAST_BATCH_TASK_GROUP_ID.lower()] == task_group_id2

    async def test_get_history_by_date__records_exist__returns_records(
        self,
        fetch_history_repo: FetchHistoryRepository,
        test_user_id_for_fetch_history: int,
        test_source_id_for_fetch_history: int,
    ):
        user_id = test_user_id_for_fetch_history
        source_id = test_source_id_for_fetch_history
        today = date.today()
        await fetch_history_repo.record_completion(
            user_id, source_id, 10, "task_today_repo_fh"
        )

        history = await fetch_history_repo.get_history_by_date(user_id, today)
        assert len(history) >= 1
        found = any(
            h[FetchHistory.SOURCE_ID.lower()] == source_id
            and h["source_name"] == "FetchHist Test Source Repo"
            for h in history
        )
        assert found

    async def test_get_history_by_date_range__records_exist_in_range__returns_records(
        self,
        fetch_history_repo: FetchHistoryRepository,
        test_user_id_for_fetch_history: int,
        test_source_id_for_fetch_history: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_fetch_history
        source_id = test_source_id_for_fetch_history
        today = date.today()
        yesterday = today - timedelta(days=1)

        await db_conn.execute(
            f"INSERT INTO {FetchHistory.TABLE_NAME} ({FetchHistory.USER_ID}, {FetchHistory.SOURCE_ID}, {FetchHistory.RECORD_DATE}, {FetchHistory.ITEMS_SAVED_TODAY}) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            user_id,
            source_id,
            yesterday,
            5,
        )
        await fetch_history_repo.record_completion(
            user_id, source_id, 10, "task_range_repo_fh"
        )

        history = await fetch_history_repo.get_history_by_date_range(
            user_id, yesterday, today
        )
        assert len(history) >= 2
        dates_found = {
            h[FetchHistory.RECORD_DATE.lower()]
            for h in history
            if h[FetchHistory.SOURCE_ID.lower()] == source_id
        }
        assert yesterday in dates_found
        assert today in dates_found
