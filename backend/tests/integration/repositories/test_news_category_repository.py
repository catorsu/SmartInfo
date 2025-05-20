"""
Integration Tests for NewsCategoryRepository.
"""

import pytest
import asyncpg
from typing import Optional

from db.repositories.news_category_repository import NewsCategoryRepository
from db.repositories.user_repository import UserRepository
from db.repositories.news_source_repository import NewsSourceRepository
from core.security import get_password_hash
from db.schema_constants import NewsCategory, NewsSource

TEST_USER_FOR_NC_REPO = "newscat_user_repo"
TEST_PASSWORD_FOR_NC_REPO = "NewsCatPassRepo123!"


@pytest.fixture
async def test_user_id_for_nc_repo(db_conn: asyncpg.Connection) -> int:
    user_repo = UserRepository(connection=db_conn)
    user = await user_repo.add_user(
        username=TEST_USER_FOR_NC_REPO,
        hashed_password=get_password_hash(TEST_PASSWORD_FOR_NC_REPO),
    )
    assert user is not None and user.id is not None
    return user.id


@pytest.fixture
async def nc_repo(db_conn: asyncpg.Connection) -> NewsCategoryRepository:
    return NewsCategoryRepository(connection=db_conn)


@pytest.mark.asyncio
class TestNewsCategoryRepository:
    """Test suite for NewsCategoryRepository methods."""

    async def test_add_category__new_name__returns_id_and_persists(
        self,
        nc_repo: NewsCategoryRepository,
        test_user_id_for_nc_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_nc_repo
        cat_name = "Tech News Repo NC"  # Unique name

        created_id = await nc_repo.add(name=cat_name, user_id=user_id)

        assert created_id is not None
        assert isinstance(created_id, int)

        persisted_record = await db_conn.fetchrow(
            f"SELECT * FROM {NewsCategory.TABLE_NAME} WHERE {NewsCategory.ID} = $1 AND {NewsCategory.USER_ID} = $2",
            created_id,
            user_id,
        )
        assert persisted_record is not None
        assert persisted_record[NewsCategory.NAME.lower()] == cat_name

    async def test_add_category__duplicate_name_for_user__returns_existing_id(
        self, nc_repo: NewsCategoryRepository, test_user_id_for_nc_repo: int
    ):
        user_id = test_user_id_for_nc_repo
        cat_name = "Duplicate Category Repo NC"  # Unique name

        id1 = await nc_repo.add(name=cat_name, user_id=user_id)
        id2 = await nc_repo.add(name=cat_name, user_id=user_id)

        assert id1 is not None
        assert id2 is not None
        assert id1 == id2

    async def test_get_by_id__category_exists_and_owned__returns_record(
        self, nc_repo: NewsCategoryRepository, test_user_id_for_nc_repo: int
    ):
        user_id = test_user_id_for_nc_repo
        cat_name = "Gettable Category Repo NC"  # Unique name
        created_id = await nc_repo.add(name=cat_name, user_id=user_id)
        assert created_id is not None

        retrieved_cat = await nc_repo.get_by_id(created_id, user_id)

        assert retrieved_cat is not None
        assert retrieved_cat[NewsCategory.ID.lower()] == created_id
        assert retrieved_cat[NewsCategory.NAME.lower()] == cat_name

    async def test_update_category__valid_update__returns_true_and_updates(
        self,
        nc_repo: NewsCategoryRepository,
        test_user_id_for_nc_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_nc_repo
        initial_name = "Initial Cat Name Repo NC"  # Unique name
        created_id = await nc_repo.add(name=initial_name, user_id=user_id)
        assert created_id is not None

        updated_name = "Updated Cat Name Repo NC"  # Unique name
        update_successful = await nc_repo.update(
            category_id=created_id, user_id=user_id, name=updated_name
        )

        assert update_successful is True
        updated_record = await db_conn.fetchrow(
            f"SELECT {NewsCategory.NAME} FROM {NewsCategory.TABLE_NAME} WHERE {NewsCategory.ID} = $1",
            created_id,
        )
        assert updated_record is not None
        assert updated_record[NewsCategory.NAME.lower()] == updated_name

    async def test_delete_category__category_exists_and_owned__returns_true_and_deletes(
        self,
        nc_repo: NewsCategoryRepository,
        test_user_id_for_nc_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_nc_repo
        cat_to_delete_name = "Category to Delete Repo NC"  # Unique name
        created_id = await nc_repo.add(name=cat_to_delete_name, user_id=user_id)
        assert created_id is not None

        delete_successful = await nc_repo.delete(created_id, user_id)

        assert delete_successful is True
        deleted_record = await db_conn.fetchrow(
            f"SELECT 1 FROM {NewsCategory.TABLE_NAME} WHERE {NewsCategory.ID} = $1",
            created_id,
        )
        assert deleted_record is None

    async def test_get_with_source_count__returns_categories_with_counts(
        self,
        nc_repo: NewsCategoryRepository,
        test_user_id_for_nc_repo: int,
        db_conn: asyncpg.Connection,
    ):
        user_id = test_user_id_for_nc_repo
        source_repo = NewsSourceRepository(connection=db_conn)

        cat1_name = "CatWithSources Repo NC"  # Unique name
        cat2_name = "CatWithoutSources Repo NC"  # Unique name
        cat1_id = await nc_repo.add(name=cat1_name, user_id=user_id)
        cat2_id = await nc_repo.add(name=cat2_name, user_id=user_id)
        assert cat1_id is not None and cat2_id is not None

        await source_repo.add(
            name="Source A NC",
            url="http://a.co/rnc",
            category_id=cat1_id,
            user_id=user_id,
        )
        await source_repo.add(
            name="Source B NC",
            url="http://b.co/rnc",
            category_id=cat1_id,
            user_id=user_id,
        )

        categories_with_counts = await nc_repo.get_with_source_count(user_id)

        found_cat1 = False
        found_cat2 = False
        for cat_data in categories_with_counts:
            if cat_data[NewsCategory.ID.lower()] == cat1_id:
                assert cat_data[NewsCategory.NAME.lower()] == cat1_name
                assert cat_data["source_count"] == 2
                found_cat1 = True
            elif cat_data[NewsCategory.ID.lower()] == cat2_id:
                assert cat_data[NewsCategory.NAME.lower()] == cat2_name
                assert cat_data["source_count"] == 0
                found_cat2 = True

        assert found_cat1 and found_cat2
