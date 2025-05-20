"""
Integration Tests for NewsSourceRepository.
"""

import pytest
import asyncpg
from typing import Optional

from db.repositories.news_source_repository import NewsSourceRepository
from db.repositories.news_category_repository import NewsCategoryRepository
from db.repositories.user_repository import UserRepository
from core.security import get_password_hash
from db.schema_constants import NewsSource, NewsCategory

TEST_USER_FOR_NS_REPO = "newssource_user_repo"
TEST_PASSWORD_FOR_NS_REPO = "NewsSourcePassRepo123!"


@pytest.fixture
async def test_user_id_for_ns_repo(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_NS_REPO,
        hashed_password=get_password_hash(TEST_PASSWORD_FOR_NS_REPO),
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def test_category_id_for_ns_repo(
    db_conn: asyncpg.Connection, test_user_id_for_ns_repo: int
) -> int:
    nc_repo = NewsCategoryRepository(connection=db_conn)
    cat_name = "NS Test Category Repo"
    category_id = await nc_repo.add(name=cat_name, user_id=test_user_id_for_ns_repo)
    assert category_id is not None
    return category_id


@pytest.fixture
async def ns_repo(db_conn: asyncpg.Connection) -> NewsSourceRepository:
    return NewsSourceRepository(connection=db_conn)


@pytest.mark.asyncio
class TestNewsSourceRepository:
    """Test suite for NewsSourceRepository methods."""

    async def test_add_source__new_data__returns_id_and_persists(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        source_name = "TechCrunch Repo NS"  # Unique
        source_url = "http://techcrunch.com/repo_ns"  # Unique

        created_id = await ns_repo.add(
            name=source_name, url=source_url, category_id=category_id, user_id=user_id
        )
        assert created_id is not None

        persisted_record = await db_conn.fetchrow(
            f"SELECT * FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.ID} = $1",
            created_id,
        )
        assert persisted_record is not None
        assert persisted_record[NewsSource.NAME.lower()] == source_name

    async def test_add_source__duplicate_url_for_user__returns_existing_id(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        source_url = "http://duplicate.url.com/repo_ns"  # Unique

        id1 = await ns_repo.add(
            name="Source Name 1 NS",
            url=source_url,
            category_id=category_id,
            user_id=user_id,
        )
        id2 = await ns_repo.add(
            name="Source Name 2 NS",
            url=source_url,
            category_id=category_id,
            user_id=user_id,
        )
        assert id1 is not None and id2 is not None and id1 == id2

    async def test_add_source__duplicate_name_for_user__raises_unique_violation(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        source_name = "Duplicate Source Name Repo NS"  # Unique

        await ns_repo.add(
            name=source_name,
            url="http://url1.unique.com/repo_ns",
            category_id=category_id,
            user_id=user_id,
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await ns_repo.add(
                name=source_name,
                url="http://url2.unique.com/repo_ns",
                category_id=category_id,
                user_id=user_id,
            )

    async def test_get_all__sources_exist__returns_list_with_category_names(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        cat_record = await db_conn.fetchrow(
            f"SELECT {NewsCategory.NAME} FROM {NewsCategory.TABLE_NAME} WHERE {NewsCategory.ID} = $1",
            category_id,
        )
        assert cat_record is not None
        category_name = cat_record[NewsCategory.NAME.lower()]

        await ns_repo.add(
            name="Source Alpha Repo NS",
            url="http://alpha.co/repo_ns",
            category_id=category_id,
            user_id=user_id,
        )
        await ns_repo.add(
            name="Source Beta Repo NS",
            url="http://beta.co/repo_ns",
            category_id=category_id,
            user_id=user_id,
        )

        all_sources = await ns_repo.get_all(user_id)
        assert len(all_sources) >= 2
        for source_data in all_sources:
            if source_data[NewsSource.NAME.lower()] in [
                "Source Alpha Repo NS",
                "Source Beta Repo NS",
            ]:
                assert source_data["category_name"] == category_name

    async def test_update_source__valid_update__returns_true_and_updates(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        created_id = await ns_repo.add(
            name="Initial Source NS",
            url="http://initial.ns/repo",
            category_id=category_id,
            user_id=user_id,
        )
        assert created_id is not None

        updated_name = "Updated Source NS"
        updated_url = "http://updated.ns/repo"
        update_successful = await ns_repo.update(
            source_id=created_id,
            user_id=user_id,
            name=updated_name,
            url=updated_url,
            category_id=category_id,
        )
        assert update_successful is True
        updated_record = await db_conn.fetchrow(
            f"SELECT {NewsSource.NAME}, {NewsSource.URL} FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.ID} = $1",
            created_id,
        )
        assert updated_record is not None
        assert updated_record[NewsSource.NAME.lower()] == updated_name
        assert updated_record[NewsSource.URL.lower()] == updated_url

    async def test_delete_source__source_exists_and_owned__returns_true_and_deletes(
        self,
        ns_repo: NewsSourceRepository,
        test_user_id_for_ns_repo: int,
        test_category_id_for_ns_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_ns_repo
        category_id = test_category_id_for_ns_repo
        created_id = await ns_repo.add(
            name="Source to Delete NS",
            url="http://delete.ns/repo",
            category_id=category_id,
            user_id=user_id,
        )
        assert created_id is not None

        delete_successful = await ns_repo.delete(created_id, user_id)
        assert delete_successful is True
        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.ID} = $1",
            created_id,
        )
        assert deleted_record is None
