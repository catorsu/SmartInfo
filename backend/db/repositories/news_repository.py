"""
News Repository Module for SmartInfo.

This module provides data access operations for news articles, interacting
primarily with the 'news' table. It supports adding individual or batches of
news items, retrieving news by various criteria (ID, filters, URLs), updating
analysis content, and deleting news items for specific users.

@module_purpose: To manage the persistence and retrieval of news articles
                 collected and processed by users.
@primary_consumers: `services.news_service.NewsService`, background tasks
                    (`background.tasks.news_tasks`).
@primary_dependencies: `db.repositories.base_repository.BaseRepository`,
                       `db.schema_constants.News`, `asyncpg`.
"""

import logging
from typing import List, Dict, Optional, Tuple, Any
import asyncpg
from datetime import date  # For type hinting fetch_date

from db.schema_constants import News
from db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NewsRepository(BaseRepository):
    """
    Repository for news table operations, handling CRUD and specific queries
    for news articles associated with users.

    @class_responsibility: To encapsulate all database interactions related to
                           the `news` table, managing news article data.
    @typical_usage_pattern: Instantiated and used by `NewsService` and
                            background news fetching tasks to store, retrieve,
                            and manage news articles.
    """

    async def add(self, item: Dict[str, Any], user_id: int) -> Optional[int]:
        """
        Adds a single news item for a user to the database.

        Uses `ON CONFLICT (url, user_id) DO NOTHING` to prevent duplicate entries
        based on the combination of URL and user ID. If a conflict occurs,
        no new record is inserted, and the method returns `None`.

        Args:
            item (Dict[str, Any]): A dictionary containing the news item's
                attributes (e.g., title, url, source_name, category_name,
                summary, content, etc.).
            user_id (int): The ID of the user to whom this news item belongs.

        Returns:
            Optional[int]: The ID of the newly inserted news item if successful
                           and no conflict occurred. Returns `None` if a conflict
                           occurred (item already exists for the user) or if
                           the insertion failed for other reasons.

        Raises:
            asyncpg.PostgresError: If a database error (other than a gracefully
                                   handled conflict) occurs during insertion.

        Side Effects:
            - Inserts a new record into the `news` table if no conflict occurs.
            - Logs the addition of the news item or conflict information.
        """
        url = item.get("url")
        if not item.get("title") or not url:
            logger.warning(
                f"Skipping news item for user {user_id} due to missing title or url. URL: '{url}'"
            )
            return None

        # Ensure default category_name if not provided
        category_name = item.get("category_name", "Uncategorized")

        query_str = f"""
            INSERT INTO {News.TABLE_NAME} (
                {News.TITLE}, {News.URL}, {News.SOURCE_NAME}, {News.CATEGORY_NAME},
                {News.SOURCE_ID}, {News.CATEGORY_ID}, {News.SUMMARY},
                {News.ANALYSIS}, {News.DATE}, {News.CONTENT}, {News.USER_ID},
                {News.TOP_IMAGE}, {News.TASK_GROUP_ID} -- Added TASK_GROUP_ID
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT ({News.URL}, {News.USER_ID}) DO NOTHING
            RETURNING {News.ID}
        """
        params: Tuple[Any, ...] = (
            item.get("title"),
            url,
            item.get("source_name"),
            category_name,
            item.get("source_id"),
            item.get("category_id"),
            item.get("summary"),
            item.get("analysis"),
            item.get("date"),
            item.get("content"),
            user_id,
            item.get("top_image"),
            item.get("task_group_id"),  # Added task_group_id
        )

        try:
            record = await self._fetchone(query_str, params)
            # record will be None if ON CONFLICT DO NOTHING was triggered
            # or if RETURNING clause didn't execute (e.g., insert failed silently for other reasons)
            last_id = record[0] if record and record[0] is not None else None

            if last_id is not None:
                logger.info(
                    f"Added news item '{item.get('title')}' with ID {last_id} for user {user_id}."
                )
            else:
                # This means either conflict or some other non-exception failure of INSERT
                logger.debug(
                    f"News item with URL '{url}' for user {user_id} either already exists "
                    "or failed to insert (ON CONFLICT or other non-exception failure)."
                )
            return last_id
        except asyncpg.IntegrityConstraintViolationError as e:
            # This might catch FK violations if source_id/category_id are invalid,
            # though the ON CONFLICT for URL/user_id is handled by returning None above.
            logger.error(
                f"Integrity constraint violation adding news item for user {user_id} "
                f"(URL: {url}, SourceID: {item.get('source_id')}, CategoryID: {item.get('category_id')}): {e}",
                exc_info=True,
            )
            raise  # Re-raise as this is an unexpected integrity issue beyond simple duplicates
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error adding news item for user {user_id} (URL: {url}): {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error adding news item for user {user_id} (URL: {url}): {e}",
                exc_info=True,
            )
            raise

    async def add_batch(
        self, items: List[Dict[str, Any]], user_id: int
    ) -> Tuple[int, int]:
        """
        Adds multiple news items for a user in a batch.

        Filters out items with missing titles/URLs or duplicates already present
        in the database or within the current batch. Uses `ON CONFLICT DO NOTHING`
        for database-level duplicate handling.

        Args:
            items (List[Dict[str, Any]]): A list of dictionaries, each
                representing a news item to add.
            user_id (int): The ID of the user.

        Returns:
            Tuple[int, int]: A tuple containing:
                - success_count (int): The number of items successfully prepared
                  for batch insertion (database `executemany` handles actual
                  insertion and conflict resolution).
                - skipped_count (int): The number of items skipped due to missing
                  data or being duplicates found before DB submission.

        Raises:
            asyncpg.PostgresError: If a database error occurs during batch execution.

        Side Effects:
            - Potentially inserts multiple records into the `news` table.
            - Logs batch processing details and any errors.
        """
        if not items:
            return 0, 0

        params_list: List[Tuple[Any, ...]] = []
        skipped_count = 0

        # Fetch all existing URLs for the user once to optimize duplicate checks
        try:
            urls_in_db_list = await self.get_all_urls(user_id)
            urls_in_db_set = set(urls_in_db_list)
        except Exception as e:  # Catch potential errors from get_all_urls
            logger.error(
                f"Failed to fetch existing URLs for user {user_id} during batch add: {e}",
                exc_info=True,
            )
            # Depending on policy, could raise, or proceed without this pre-check (relying solely on ON CONFLICT)
            # For now, let's proceed but log the issue.
            urls_in_db_set = set()

        processed_urls_in_batch = set()  # To handle duplicates within the same batch

        for item in items:
            url = item.get("url")
            if not item.get("title") or not url:
                logger.warning(
                    f"Skipping news item in batch for user {user_id} due to missing title or url. URL: '{url}'"
                )
                skipped_count += 1
                continue

            if url in urls_in_db_set or url in processed_urls_in_batch:
                logger.debug(
                    f"Skipping duplicate URL in batch for user {user_id}: {url} (already in DB or batch)"
                )
                skipped_count += 1
                continue

            params: Tuple[Any, ...] = (
                item.get("title", ""),  # Default to empty string if missing
                url,
                item.get("source_name", ""),
                item.get("category_name", "Uncategorized"),
                item.get("source_id"),  # Can be None
                item.get("category_id"),  # Can be None
                item.get("summary", ""),
                item.get("analysis", ""),
                item.get("date"),  # Can be None
                item.get("content", ""),
                user_id,
                item.get("top_image"),  # Can be None
                item.get("task_group_id"),  # Can be None
            )
            params_list.append(params)
            processed_urls_in_batch.add(url)

        if not params_list:
            logger.info(
                f"No valid new items found in the batch for user {user_id} to add."
            )
            return 0, skipped_count

        query_str = f"""
            INSERT INTO {News.TABLE_NAME} (
                {News.TITLE}, {News.URL}, {News.SOURCE_NAME}, {News.CATEGORY_NAME},
                {News.SOURCE_ID}, {News.CATEGORY_ID}, {News.SUMMARY},
                {News.ANALYSIS}, {News.DATE}, {News.CONTENT}, {News.USER_ID},
                {News.TOP_IMAGE}, {News.TASK_GROUP_ID}
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT ({News.URL}, {News.USER_ID}) DO NOTHING
        """

        success_count = 0
        try:
            # _executemany returns True on successful command submission, not row count
            if await self._executemany(query_str, params_list):
                # The actual number of rows inserted depends on conflicts.
                # We report the number of items *attempted* for insertion via executemany.
                success_count = len(params_list)
                logger.info(
                    f"Batch add news: {success_count} items submitted for user {user_id}. "
                    f"{skipped_count} items were skipped pre-DB (missing data/duplicates). "
                    "DB's ON CONFLICT handled further duplicates."
                )
            else:
                # This path in _executemany (returning False) is unlikely unless an
                # exception was caught and suppressed within _executemany itself,
                # which is not its current design (it re-raises).
                logger.error(
                    f"Batch add news command submission failed for user {user_id}."
                )

        except asyncpg.IntegrityConstraintViolationError as e:
            # This could catch FK violations if source_id/category_id are invalid.
            # The ON CONFLICT for URL/user_id is handled by DO NOTHING.
            logger.error(
                f"Integrity constraint violation during batch add news for user {user_id} "
                f"(check foreign keys, etc.): {e}",
                exc_info=True,
            )
            # success_count remains 0 or its value before error
            raise  # Re-raise
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error in batch add news for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in batch add news for user {user_id}: {e}",
                exc_info=True,
            )
            raise

        return success_count, skipped_count

    async def get_by_id(self, news_id: int, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific news item by its ID, ensuring it belongs to the
        specified user.

        Args:
            news_id (int): The ID of the news item to retrieve.
            user_id (int): The ID of the user who is expected to own the item.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object with news item
                                      details if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        # Selects most fields, excluding 'content' for brevity in general listings.
        # 'content' can be fetched separately if needed.
        query_str = f"""
            SELECT {News.ID}, {News.TITLE}, {News.URL}, {News.SOURCE_NAME},
                   {News.CATEGORY_NAME}, {News.SOURCE_ID}, {News.CATEGORY_ID},
                   {News.SUMMARY}, {News.ANALYSIS}, {News.DATE}, {News.USER_ID},
                   {News.CREATED_AT}, {News.TOP_IMAGE}, {News.TASK_GROUP_ID}
            FROM {News.TABLE_NAME} WHERE {News.ID} = $1 AND {News.USER_ID} = $2
        """
        params = (news_id, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_content_by_id(self, news_id: int, user_id: int) -> Optional[str]:
        """
        Retrieves only the `content` field of a news item by its ID, ensuring
        it belongs to the specified user.

        Args:
            news_id (int): The ID of the news item.
            user_id (int): The ID of the user.

        Returns:
            Optional[str]: The content string if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query for the `content` field.
            - Logs errors.
        """
        query_str = f"""
            SELECT {News.CONTENT}
            FROM {News.TABLE_NAME} WHERE {News.ID} = $1 AND {News.USER_ID} = $2
        """
        params = (news_id, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return (
                record[News.CONTENT.lower()]
                if record and record[News.CONTENT.lower()] is not None
                else None
            )
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news content by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news content by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_all(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """
        Retrieves all news items for a user, with pagination.

        Items are ordered by ID in descending order. Excludes full `content`.

        Args:
            user_id (int): The ID of the user.
            limit (int): Max number of items to return.
            offset (int): Number of items to skip.

        Returns:
            List[asyncpg.Record]: List of news items.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {News.ID}, {News.TITLE}, {News.URL}, {News.SOURCE_NAME},
                   {News.CATEGORY_NAME}, {News.SOURCE_ID}, {News.CATEGORY_ID},
                   {News.SUMMARY}, {News.ANALYSIS}, {News.DATE}, {News.USER_ID},
                   {News.CREATED_AT}, {News.TOP_IMAGE}, {News.TASK_GROUP_ID}
            FROM {News.TABLE_NAME} WHERE {News.USER_ID} = $1
            ORDER BY {News.ID} DESC LIMIT $2 OFFSET $3
        """
        params = (user_id, limit, offset)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all news for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting all news for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_news_with_filters(
        self,
        user_id: int,
        category_id: Optional[int] = None,
        source_id: Optional[int] = None,
        analyzed: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        search_term: Optional[str] = None,
        fetch_date: Optional[date] = None,
        sort_by: Optional[str] = None,
    ) -> List[asyncpg.Record]:
        """
        Retrieves news items with various filters, pagination, and sorting.

        Includes full `content` in the selection, which might be large.
        Uses 'simple' FTS config if `search_term` is provided.

        Args:
            user_id (int): The user's ID.
            category_id (Optional[int]): Filter by category ID.
            source_id (Optional[int]): Filter by source ID.
            analyzed (Optional[bool]): Filter by analysis status (True if analysis
                                     is not NULL and not empty, False otherwise).
            page (int): Page number for pagination (1-indexed).
            page_size (int): Number of items per page.
            search_term (Optional[str]): Term for full-text search across title,
                                       summary, source name, category name.
            fetch_date (Optional[date]): Filter by creation date of news record.
            sort_by (Optional[str]): Sorting option, e.g., 'created_at_desc'.

        Returns:
            List[asyncpg.Record]: Filtered and paginated list of news items.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a complex SELECT query with dynamic conditions.
            - Logs errors.
        """
        select_fields = f"""
            {News.ID}, {News.TITLE}, {News.URL}, {News.SOURCE_NAME},
            {News.CATEGORY_NAME}, {News.SOURCE_ID}, {News.CATEGORY_ID},
            {News.SUMMARY}, {News.ANALYSIS}, {News.DATE}, {News.CONTENT}, -- Content included
            {News.USER_ID}, {News.CREATED_AT}, {News.TOP_IMAGE}, {News.TASK_GROUP_ID}
        """
        base_query = (
            f"SELECT {select_fields} FROM {News.TABLE_NAME} WHERE {News.USER_ID} = $1"
        )

        params_list: List[Any] = [user_id]
        conditions: List[str] = []
        param_idx = 2  # Start indexing from $2 for additional params

        if category_id is not None:
            conditions.append(f"{News.CATEGORY_ID} = ${param_idx}")
            params_list.append(category_id)
            param_idx += 1
        if source_id is not None:
            conditions.append(f"{News.SOURCE_ID} = ${param_idx}")
            params_list.append(source_id)
            param_idx += 1
        if analyzed is not None:
            if analyzed:
                conditions.append(
                    f"({News.ANALYSIS} IS NOT NULL AND {News.ANALYSIS} <> '')"
                )
            else:
                conditions.append(f"({News.ANALYSIS} IS NULL OR {News.ANALYSIS} = '')")
        if search_term:
            # Using 'simple' FTS configuration. Ensure 'zhparsercfg' is used if Chinese FTS is set up.
            conditions.append(
                f"""
                to_tsvector('simple',
                    COALESCE({News.TITLE}, '') || ' ' || COALESCE({News.SUMMARY}, '') || ' ' ||
                    COALESCE({News.SOURCE_NAME}, '') || ' ' || COALESCE({News.CATEGORY_NAME}, '')
                ) @@ plainto_tsquery('simple', ${param_idx})
                """
            )
            params_list.append(search_term)
            param_idx += 1
        if fetch_date is not None:
            conditions.append(f"DATE({News.CREATED_AT}) = ${param_idx}")
            params_list.append(fetch_date)
            param_idx += 1

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        # Sorting
        order_clause = (
            f"ORDER BY {News.CREATED_AT} DESC, {News.ID} DESC"  # Default sort
        )
        if sort_by == "created_at_asc":
            order_clause = f"ORDER BY {News.CREATED_AT} ASC, {News.ID} ASC"
        elif sort_by == "title_asc":
            order_clause = f"ORDER BY {News.TITLE} ASC, {News.ID} DESC"
        elif sort_by == "title_desc":
            order_clause = f"ORDER BY {News.TITLE} DESC, {News.ID} DESC"
        # Add more sort options as needed

        base_query += f" {order_clause}"

        # Pagination
        offset = (page - 1) * page_size
        base_query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params_list.extend([page_size, offset])

        final_params = tuple(params_list)

        try:
            return await self._fetchall(base_query, final_params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error in get_news_with_filters for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in get_news_with_filters for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, news_id: int, user_id: int) -> bool:
        """
        Deletes a specific news item by its ID, ensuring it belongs to the user.

        Args:
            news_id (int): The ID of the news item to delete.
            user_id (int): The ID of the user.

        Returns:
            bool: `True` if deletion was successful (one row affected),
                  `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes a record from the `news` table.
            - Logs status or errors.
        """
        query_str = f"DELETE FROM {News.TABLE_NAME} WHERE {News.ID} = $1 AND {News.USER_ID} = $2"
        params = (news_id, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = (
                status is not None and status.lower() == "delete 1"
            )  # asyncpg returns "DELETE <count>"
            if deleted:
                logger.info(f"Deleted news item with ID {news_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Delete command for news ID {news_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Item might not exist or not belong to user."
                )
            return deleted
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error deleting news by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting news by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def exists_by_url(self, url: str, user_id: int) -> bool:
        """
        Checks if a news item with the given URL already exists for the user.

        Args:
            url (str): The URL to check.
            user_id (int): The ID of the user.

        Returns:
            bool: `True` if an item with the URL exists for the user, `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT 1 ... LIMIT 1 query.
            - Logs errors.
        """
        query_str = f"SELECT 1 FROM {News.TABLE_NAME} WHERE {News.URL} = $1 AND {News.USER_ID} = $2 LIMIT 1"
        params = (url, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return record is not None
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error checking if news URL '{url}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking if news URL '{url}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False

    async def get_all_urls(self, user_id: int) -> List[str]:
        """
        Retrieves all unique URLs of news items for a specific user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[str]: A list of URL strings. Empty if no URLs found or error.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT DISTINCT query.
            - Logs errors.
        """
        query_str = f"SELECT DISTINCT {News.URL} FROM {News.TABLE_NAME} WHERE {News.USER_ID} = $1"
        params = (user_id,)
        try:
            records = await self._fetchall(query_str, params)
            return [
                record[News.URL.lower()]
                for record in records
                if record[News.URL.lower()] is not None
            ]
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all news URLs for user {user_id}: {e}", exc_info=True
            )
            raise  # Or return []
        except Exception as e:
            logger.error(
                f"Unexpected error getting all news URLs for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return []

    async def clear_all_for_user(self, user_id: int) -> bool:
        """
        Deletes all news items for a specific user. USE WITH CAUTION.

        Args:
            user_id (int): The ID of the user whose news items to delete.

        Returns:
            bool: `True` if the command executed successfully (regardless of rows
                  affected), `False` if a database error occurred.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Deletes all records for the user from the `news` table.
            - Logs status or errors.
        """
        query_str = f"DELETE FROM {News.TABLE_NAME} WHERE {News.USER_ID} = $1"
        params = (user_id,)
        try:
            status = await self._execute(query_str, params)
            logger.info(f"Cleared all news for user {user_id}. Status: {status}")
            return True  # Indicates command execution success
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error clearing all news for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error clearing all news for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def update_analysis(
        self, news_id: int, user_id: int, analysis_text: str
    ) -> bool:
        """
        Updates the `analysis` field for a specific news item belonging to a user.

        Args:
            news_id (int): The ID of the news item to update.
            user_id (int): The ID of the user.
            analysis_text (str): The new analysis text.

        Returns:
            bool: `True` if update successful (one row affected), `False` otherwise.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Updates the `analysis` field of a record in `news` table.
            - Logs status or errors.
        """
        query_str = f"""
            UPDATE {News.TABLE_NAME}
            SET {News.ANALYSIS} = $1
            WHERE {News.ID} = $2 AND {News.USER_ID} = $3
        """
        params = (analysis_text, news_id, user_id)
        try:
            status = await self._execute(query_str, params)
            updated = status is not None and status.lower() == "update 1"
            if updated:
                logger.info(
                    f"Updated analysis for news ID {news_id} for user {user_id}."
                )
            else:
                logger.warning(
                    f"Update analysis for news ID {news_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Item might not exist or not belong to user."
                )
            return updated
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating analysis for news ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating analysis for news ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_news_with_filters_as_dict(
        self,
        user_id: int,
        category_id: Optional[int] = None,
        source_id: Optional[int] = None,
        analyzed: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        search_term: Optional[str] = None,
        fetch_date: Optional[date] = None,
        sort_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves news items with filters, returning them as a list of dictionaries.

        This method calls `get_news_with_filters` and then converts each
        `asyncpg.Record` into a dictionary. `None` values in records are
        converted to empty strings for potentially easier JSON serialization,
        though Pydantic models usually handle `None` correctly.

        Args:
            user_id (int): User's ID.
            category_id (Optional[int]): Filter by category.
            source_id (Optional[int]): Filter by source.
            analyzed (Optional[bool]): Filter by analysis status.
            page (int): Page number.
            page_size (int): Items per page.
            search_term (Optional[str]): Search term.
            fetch_date (Optional[date]): Filter by creation date.
            sort_by (Optional[str]): Sorting option.

        Returns:
            List[Dict[str, Any]]: List of news items as dictionaries.

        Side Effects:
            - Calls `get_news_with_filters`.
        """
        result_records = await self.get_news_with_filters(
            user_id=user_id,
            category_id=category_id,
            source_id=source_id,
            analyzed=analyzed,
            page=page,
            page_size=page_size,
            search_term=search_term,
            fetch_date=fetch_date,
            sort_by=sort_by,
        )

        result_dicts: List[Dict[str, Any]] = []
        for record in result_records:
            item_dict = dict(record)
            # Clean up None values for better JSON serialization if needed,
            # but Pydantic models handle None correctly.
            # This conversion to "" might be undesirable if None has semantic meaning.
            # Consider removing this loop if Pydantic models are the final destination.
            # for key, value in item_dict.items():
            #     if value is None:
            #         item_dict[key] = "" # Or keep as None
            result_dicts.append(item_dict)
        return result_dicts

    async def get_analysis_by_id(self, news_id: int, user_id: int) -> Optional[str]:
        """
        Retrieves only the `analysis` field of a news item by ID for a user.

        Args:
            news_id (int): The ID of the news item.
            user_id (int): The ID of the user.

        Returns:
            Optional[str]: The analysis text if found and owned, else `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query for the `analysis` field.
            - Logs errors.
        """
        query_str = f"""
            SELECT {News.ANALYSIS}
            FROM {News.TABLE_NAME} WHERE {News.ID} = $1 AND {News.USER_ID} = $2
        """
        params = (news_id, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return (
                record[News.ANALYSIS.lower()]
                if record and record[News.ANALYSIS.lower()] is not None
                else None
            )
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting news analysis by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting news analysis by ID {news_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
