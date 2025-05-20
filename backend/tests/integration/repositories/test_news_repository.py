"""
Integration Tests for NewsRepository.
"""

import pytest
import asyncpg
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timezone

from db.repositories.news_repository import NewsRepository
from db.repositories.user_repository import UserRepository
from db.repositories.news_source_repository import NewsSourceRepository
from db.repositories.news_category_repository import NewsCategoryRepository
from core.security import get_password_hash
from db.schema_constants import News, Users, NewsSource, NewsCategory

TEST_USER_FOR_NEWS_REPO = "news_user_repo"
TEST_PASSWORD_FOR_NEWS_REPO = "NewsUserPassRepo123!"


@pytest.fixture
async def test_user_id_for_news_repo(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_NEWS_REPO,
        hashed_password=get_password_hash(TEST_PASSWORD_FOR_NEWS_REPO),
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def test_category_for_news_repo(
    db_conn: asyncpg.Connection, test_user_id_for_news_repo: int
) -> Dict[str, Any]:
    nc_repo = NewsCategoryRepository(connection=db_conn)
    cat_name = "News Test Category Repo News"  # Unique
    cat_id = await nc_repo.add(name=cat_name, user_id=test_user_id_for_news_repo)
    assert cat_id is not None
    return {"id": cat_id, "name": cat_name}


@pytest.fixture
async def test_source_for_news_repo(
    db_conn: asyncpg.Connection,
    test_user_id_for_news_repo: int,
    test_category_for_news_repo: Dict[str, Any],
) -> Dict[str, Any]:
    ns_repo = NewsSourceRepository(connection=db_conn)
    source_name = "News Test Source Repo News"  # Unique
    source_url = "http://newstest.example.com/repo_news"  # Unique
    source_id = await ns_repo.add(
        name=source_name,
        url=source_url,
        category_id=test_category_for_news_repo["id"],
        user_id=test_user_id_for_news_repo,
    )
    assert source_id is not None
    return {
        "id": source_id,
        "name": source_name,
        "url": source_url,
        "category_id": test_category_for_news_repo["id"],
    }


@pytest.fixture
async def news_repo(db_conn: asyncpg.Connection) -> NewsRepository:
    return NewsRepository(connection=db_conn)


def _create_news_item_data(
    user_id: int,
    source: Dict[str, Any],
    category: Dict[str, Any],
    title_suffix: str = "",
    url_suffix: str = "",
) -> Dict[str, Any]:
    return {
        "title": f"Test News Title {title_suffix} NewsRepo",
        "url": f"http://testnews.example.com/article{url_suffix}_newsrepo",
        "source_name": source["name"],
        "category_name": category["name"],
        "source_id": source["id"],
        "category_id": category["id"],
        "summary": f"This is a test summary {title_suffix} NewsRepo.",
        "analysis": None,
        "date": datetime.now(timezone.utc).isoformat(),
        "content": f"Full content of the test news article {title_suffix} NewsRepo.",
        "user_id": user_id,
        "top_image": f"http://images.example.com/image{url_suffix}_news.jpg",
        "task_group_id": f"task-group-{title_suffix}-news",
    }


@pytest.mark.asyncio
class TestNewsRepository:
    """Test suite for NewsRepository methods."""

    async def test_add_news_item__valid_data__returns_id_and_persists(
        self,
        news_repo: NewsRepository,
        test_user_id_for_news_repo: int,
        test_source_for_news_repo: Dict[str, Any],
        test_category_for_news_repo: Dict[str, Any],
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_news_repo
        item_data = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "add1news",
            "add1news",
        )

        created_id = await news_repo.add(item=item_data, user_id=user_id)
        assert created_id is not None

        persisted = await db_conn.fetchrow(
            f"SELECT * FROM {News.TABLE_NAME} WHERE {News.ID}=$1", created_id
        )
        assert persisted is not None
        assert persisted[News.TITLE.lower()] == item_data["title"]

    async def test_add_batch__valid_items__adds_new_items_returns_counts(
        self,
        news_repo: NewsRepository,
        test_user_id_for_news_repo: int,
        test_source_for_news_repo: Dict[str, Any],
        test_category_for_news_repo: Dict[str, Any],
    ):
        user_id = test_user_id_for_news_repo
        item1 = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "nbatch1",
            "nbatch1_url",
        )
        item2 = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "nbatch2",
            "nbatch2_url",
        )

        items_to_add = [item1, item2]
        success_count, skipped_count = await news_repo.add_batch(
            items=items_to_add, user_id=user_id
        )
        assert success_count == 2
        assert skipped_count == 0

    async def test_get_by_id__item_exists_and_owned__returns_record(
        self,
        news_repo: NewsRepository,
        test_user_id_for_news_repo: int,
        test_source_for_news_repo: Dict[str, Any],
        test_category_for_news_repo: Dict[str, Any],
    ):
        user_id = test_user_id_for_news_repo
        item_data = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "getidnews",
            "getidnews_url",
        )
        created_id = await news_repo.add(item=item_data, user_id=user_id)
        assert created_id is not None

        retrieved = await news_repo.get_by_id(news_id=created_id, user_id=user_id)
        assert retrieved is not None
        assert retrieved[News.ID.lower()] == created_id

    async def test_update_analysis__updates_field_returns_true(
        self,
        news_repo: NewsRepository,
        test_user_id_for_news_repo: int,
        test_source_for_news_repo: Dict[str, Any],
        test_category_for_news_repo: Dict[str, Any],
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_news_repo
        item_data = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "analysisnews",
            "analysisnews_url",
        )
        created_id = await news_repo.add(item=item_data, user_id=user_id)
        assert created_id is not None

        new_analysis = "This is the updated LLM analysis for news repo."
        success = await news_repo.update_analysis(
            news_id=created_id, user_id=user_id, analysis_text=new_analysis
        )
        assert success is True

        updated_record = await db_conn.fetchrow(
            f"SELECT {News.ANALYSIS} FROM {News.TABLE_NAME} WHERE {News.ID}=$1",
            created_id,
        )
        assert updated_record is not None
        assert updated_record[News.ANALYSIS.lower()] == new_analysis

    async def test_delete_news_item__owned_item__deletes_and_returns_true(
        self,
        news_repo: NewsRepository,
        test_user_id_for_news_repo: int,
        test_source_for_news_repo: Dict[str, Any],
        test_category_for_news_repo: Dict[str, Any],
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_news_repo
        item_data = _create_news_item_data(
            user_id,
            test_source_for_news_repo,
            test_category_for_news_repo,
            "delnews",
            "delnews_url",
        )
        created_id = await news_repo.add(item=item_data, user_id=user_id)
        assert created_id is not None

        success = await news_repo.delete(news_id=created_id, user_id=user_id)
        assert success is True

        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {News.TABLE_NAME} WHERE {News.ID}=$1", created_id
        )
        assert deleted_record is None
