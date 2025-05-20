"""
News Source Repository Module for SmartInfo.

This module handles database operations for news sources, allowing users to
define and manage the origins of their news content. It interacts with the
`news_sources` table.

@module_purpose: To provide a persistent storage interface for user-defined
                 news sources, linking them to categories.
@primary_consumers: `services.news_service.NewsService`.
@primary_dependencies: `db.repositories.base_repository.BaseRepository`,
                       `db.schema_constants.NewsSource`,
                       `db.schema_constants.NewsCategory` (for joins), `asyncpg`.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import asyncpg

from db.schema_constants import NewsSource, NewsCategory  # NewsCategory for join
from db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NewsSourceRepository(BaseRepository):
    """
    Repository for news_sources table operations.

    Provides methods for adding, retrieving, updating, and deleting news
    sources for users, including associating them with news categories.

    @class_responsibility: To encapsulate all database interactions related to
                           the `news_sources` table.
    @typical_usage_pattern: Instantiated and used by `NewsService` to manage
                            news sources based on user actions.
    """

    async def add(
        self, name: str, url: str, category_id: int, user_id: int
    ) -> Optional[int]:
        """
        Adds a new news source for a user.

        If a source with the same URL already exists for the user, this method
        attempts to retrieve and return the ID of the existing source.
        Uses `ON CONFLICT (url, user_id) DO NOTHING` for graceful conflict handling.
        A similar conflict on `(name, user_id)` is also possible due to table constraints
        but is not explicitly handled by `ON CONFLICT` in this query; such a conflict
        would raise an `IntegrityConstraintViolationError`.

        Args:
            name (str): The name of the news source.
            url (str): The URL of the news source (e.g., homepage, RSS feed).
            category_id (int): The ID of the category this source belongs to.
                               This category must exist and belong to the user.
            user_id (int): The ID of the user adding the source.

        Returns:
            Optional[int]: The ID of the newly added or existing source (if URL
                           conflicted). Returns `None` if insertion fails for
                           other reasons (e.g., category_id FK violation, name conflict)
                           or if an unexpected error occurs.

        Raises:
            asyncpg.IntegrityConstraintViolationError: If `category_id` is invalid
                or if a unique constraint on `(name, user_id)` is violated.
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Inserts a new record into `news_sources` if no URL conflict for the user.
            - May execute a SELECT query if URL conflict occurs.
            - Logs status or errors.
        """
        query_insert = f"""
            INSERT INTO {NewsSource.TABLE_NAME} (
                {NewsSource.NAME}, {NewsSource.URL}, {NewsSource.CATEGORY_ID}, {NewsSource.USER_ID}
            ) VALUES ($1, $2, $3, $4)
            ON CONFLICT ({NewsSource.URL}, {NewsSource.USER_ID}) DO NOTHING
            RETURNING {NewsSource.ID}
        """
        query_select_by_url = f"""
            SELECT {NewsSource.ID} FROM {NewsSource.TABLE_NAME}
            WHERE {NewsSource.URL} = $1 AND {NewsSource.USER_ID} = $2
        """
        params_insert = (name, url, category_id, user_id)
        params_select_url = (url, user_id)

        try:
            inserted_record = await self._fetchone(query_insert, params_insert)
            if inserted_record and inserted_record[0] is not None:
                inserted_id = int(inserted_record[0])
                logger.info(
                    f"Added news source '{name}' with URL '{url}', ID {inserted_id} for user {user_id}."
                )
                return inserted_id
            else:
                # Conflict on (URL, user_id) likely occurred, or insert failed silently
                logger.debug(
                    f"Source with URL '{url}' for user {user_id} insert returned no ID "
                    "(likely exists or failed). Attempting to fetch existing ID by URL."
                )
                existing_record_by_url = await self._fetchone(
                    query_select_by_url, params_select_url
                )
                if existing_record_by_url and existing_record_by_url[0] is not None:
                    existing_id = int(existing_record_by_url[0])
                    logger.debug(
                        f"Found existing source with URL '{url}', ID {existing_id} for user {user_id}."
                    )
                    return existing_id
                else:
                    # This means INSERT failed (no ID) AND SELECT by URL also failed.
                    # Could be a conflict on (name, user_id) or invalid category_id.
                    # These would raise IntegrityConstraintViolationError, caught below.
                    # If no exception, it's an unexpected state.
                    logger.error(
                        f"Failed to add or find source with URL '{url}' for user {user_id} after insert attempt. "
                        "Possible name conflict or invalid category ID."
                    )
                    return None  # Should be caught by specific exceptions if those are the cause

        except asyncpg.IntegrityConstraintViolationError as e:
            # This can be due to:
            # 1. Foreign key violation (category_id does not exist for user).
            # 2. Unique constraint violation on (name, user_id).
            logger.error(
                f"Integrity constraint violation adding news source '{name}' (URL: '{url}') for user {user_id}. "
                f"Check category_id ({category_id}) validity or if name is duplicate for user. Error: {e}",
                exc_info=True,
            )
            raise  # Re-raise for service layer to handle
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error adding news source '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error adding news source '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def update(
        self, source_id: int, user_id: int, name: str, url: str, category_id: int
    ) -> bool:
        """
        Updates an existing news source belonging to a specific user.

        Args:
            source_id (int): The ID of the news source to update.
            user_id (int): The ID of the user who owns the source.
            name (str): The new name for the source.
            url (str): The new URL for the source.
            category_id (int): The new category ID for the source.
                               This category must exist and belong to the user.

        Returns:
            bool: `True` if update was successful (one row affected), `False`
                  otherwise (e.g., source not found, not owned, or conflict).

        Raises:
            asyncpg.IntegrityConstraintViolationError: If the update causes a
                unique constraint violation (e.g., duplicate URL or name for
                the user) or an FK violation for `category_id`.
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Updates a record in `news_sources`.
            - Logs status or errors.
        """
        query_str = f"""
            UPDATE {NewsSource.TABLE_NAME}
            SET {NewsSource.NAME} = $1, {NewsSource.URL} = $2, {NewsSource.CATEGORY_ID} = $3
            WHERE {NewsSource.ID} = $4 AND {NewsSource.USER_ID} = $5
        """
        params = (name, url, category_id, source_id, user_id)
        try:
            status = await self._execute(query_str, params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(f"Updated source ID {source_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Update command for source ID {source_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Source might not exist or not belong to user."
                )
            return updated
        except asyncpg.IntegrityConstraintViolationError as e:
            logger.error(
                f"Integrity error updating source ID {source_id} for user {user_id} "
                f"(check URL '{url}' or name '{name}' uniqueness for user, and category_id {category_id}): {e}",
                exc_info=True,
            )
            raise
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating news source ID {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating news source ID {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, source_id: int, user_id: int) -> bool:
        """
        Deletes a news source belonging to a specific user.

        Note: `ON DELETE CASCADE` for `news.source_id` in the schema means
        deleting a source will also delete associated news items.

        Args:
            source_id (int): The ID of the source to delete.
            user_id (int): The ID of the user.

        Returns:
            bool: `True` if deletion successful (one row affected), `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes a record from `news_sources`.
            - May delete associated records in `news` table due to CASCADE.
            - Logs status or errors.
        """
        query_str = f"DELETE FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.ID} = $1 AND {NewsSource.USER_ID} = $2"
        params = (source_id, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(f"Deleted source ID {source_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Delete command for source ID {source_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Source might not exist or not belong to user."
                )
            return deleted
        except (
            asyncpg.PostgresError
        ) as e:  # Catches FK violation if ON DELETE RESTRICT was used for news items
            logger.error(
                f"Error deleting news source {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting news source {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(self, source_id: int, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a news source by ID, ensuring it belongs to the user.

        Args:
            source_id (int): ID of the source.
            user_id (int): ID of the user.

        Returns:
            Optional[asyncpg.Record]: Source details if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {NewsSource.ID}, {NewsSource.NAME}, {NewsSource.URL},
                   {NewsSource.CATEGORY_ID}, {NewsSource.USER_ID}
            FROM {NewsSource.TABLE_NAME}
            WHERE {NewsSource.ID} = $1 AND {NewsSource.USER_ID} = $2
        """
        params = (source_id, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news source by ID {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news source by ID {source_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_name(self, name: str, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a news source by name, ensuring it belongs to the user.

        Args:
            name (str): Name of the source.
            user_id (int): ID of the user.

        Returns:
            Optional[asyncpg.Record]: Source details if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {NewsSource.ID}, {NewsSource.NAME}, {NewsSource.URL},
                   {NewsSource.CATEGORY_ID}, {NewsSource.USER_ID}
            FROM {NewsSource.TABLE_NAME}
            WHERE {NewsSource.NAME} = $1 AND {NewsSource.USER_ID} = $2
        """
        params = (name, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news source by name '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news source by name '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_url(self, url: str, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a news source by URL, ensuring it belongs to the user.

        Args:
            url (str): URL of the source.
            user_id (int): ID of the user.

        Returns:
            Optional[asyncpg.Record]: Source details if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {NewsSource.ID}, {NewsSource.NAME}, {NewsSource.URL},
                   {NewsSource.CATEGORY_ID}, {NewsSource.USER_ID}
            FROM {NewsSource.TABLE_NAME}
            WHERE {NewsSource.URL} = $1 AND {NewsSource.USER_ID} = $2
        """
        params = (url, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news source by URL '{url}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news source by URL '{url}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_all(self, user_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all news sources for a user, joined with category names.

        Sources are ordered by category name, then by source name.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[asyncpg.Record]: List of sources with `category_name` included.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query with a JOIN.
            - Logs errors.
        """
        query_str = f"""
            SELECT
                ns.{NewsSource.ID}, ns.{NewsSource.NAME}, ns.{NewsSource.URL},
                ns.{NewsSource.CATEGORY_ID}, ns.{NewsSource.USER_ID},
                nc.{NewsCategory.NAME} as category_name
            FROM {NewsSource.TABLE_NAME} ns
            JOIN {NewsCategory.TABLE_NAME} nc
                ON ns.{NewsSource.CATEGORY_ID} = nc.{NewsCategory.ID}
            WHERE ns.{NewsSource.USER_ID} = $1
              AND nc.{NewsSource.USER_ID} = $1 -- Ensure category also belongs to the user
            ORDER BY nc.{NewsCategory.NAME} ASC, ns.{NewsSource.NAME} ASC
        """
        params = (user_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all news sources for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting all news sources for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_category(
        self, category_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """
        Retrieves all sources for a category, ensuring user ownership of both.

        Args:
            category_id (int): ID of the category.
            user_id (int): ID of the user.

        Returns:
            List[asyncpg.Record]: List of sources in the category.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query with JOINs.
            - Logs errors.
        """
        query_str = f"""
            SELECT
                ns.{NewsSource.ID}, ns.{NewsSource.NAME}, ns.{NewsSource.URL},
                ns.{NewsSource.CATEGORY_ID}, ns.{NewsSource.USER_ID},
                nc.{NewsCategory.NAME} as category_name
            FROM {NewsSource.TABLE_NAME} ns
            JOIN {NewsCategory.TABLE_NAME} nc
                ON ns.{NewsSource.CATEGORY_ID} = nc.{NewsCategory.ID}
            WHERE ns.{NewsSource.CATEGORY_ID} = $1
              AND ns.{NewsSource.USER_ID} = $2
              AND nc.{NewsCategory.USER_ID} = $2 -- Ensure category also belongs to user
            ORDER BY ns.{NewsSource.NAME} ASC
        """
        params = (category_id, user_id)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting sources by category {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting sources by category {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def exists_by_url(self, url: str, user_id: int) -> bool:
        """
        Checks if a news source with the given URL exists for the user.

        Args:
            url (str): URL to check.
            user_id (int): User's ID.

        Returns:
            bool: `True` if exists, `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT 1 ... LIMIT 1 query.
            - Logs errors.
        """
        query_str = f"SELECT 1 FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.URL} = $1 AND {NewsSource.USER_ID} = $2 LIMIT 1"
        params = (url, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return record is not None
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error checking if source URL '{url}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking if source URL '{url}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False

    async def exists_by_name(self, name: str, user_id: int) -> bool:
        """
        Checks if a news source with the given name exists for the user.

        Args:
            name (str): Name to check.
            user_id (int): User's ID.

        Returns:
            bool: `True` if exists, `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT 1 ... LIMIT 1 query.
            - Logs errors.
        """
        query_str = f"SELECT 1 FROM {NewsSource.TABLE_NAME} WHERE {NewsSource.NAME} = $1 AND {NewsSource.USER_ID} = $2 LIMIT 1"
        params = (name, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return record is not None
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error checking if source name '{name}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking if source name '{name}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False
