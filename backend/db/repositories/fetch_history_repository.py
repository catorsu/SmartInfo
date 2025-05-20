"""
Fetch History Repository Module for SmartInfo.

This module handles database operations for the `fetch_history` table,
which tracks the number of news items saved per source per day for each user.
It supports recording fetch completions and retrieving history records.

@module_purpose: To maintain a log of news fetching activities, enabling features
                 like daily fetch limits, activity tracking, and reporting.
@primary_consumers: `background.tasks.news_tasks` (for recording completions),
                    API endpoints related to user activity or fetch statistics.
@primary_dependencies: `db.repositories.base_repository.BaseRepository`,
                       `db.schema_constants.FetchHistory`,
                       `db.schema_constants.NewsSource`, `asyncpg`.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import asyncpg
from datetime import date, datetime, timezone

from db.repositories.base_repository import BaseRepository
from db.schema_constants import FetchHistory, NewsSource  # NewsSource for joining

logger = logging.getLogger(__name__)


class FetchHistoryRepository(BaseRepository):
    """
    Repository for operations on the `fetch_history` table.

    This class provides methods to record when news items are fetched and saved
    for a user from a specific source, and to retrieve this history. It uses
    UPSERT logic to handle daily records efficiently.

    @class_responsibility: To encapsulate all database interactions related to
                           tracking news fetching history.
    @typical_usage_pattern: Instantiated and used by background tasks
                            (`news_tasks`) to log fetch completions and by
                            services or API endpoints that need to display
                            fetch history to users.
    """

    async def record_completion(
        self,
        user_id: int,
        source_id: int,
        items_saved_this_run: int,
        task_group_id: Optional[str] = None,
    ) -> bool:
        """
        Records a fetch completion for a news source on the current day.

        If a record for the user, source, and current date already exists,
        it increments `items_saved_today` by `items_saved_this_run` and updates
        `last_updated_at` and `last_batch_task_group_id`. Otherwise, it inserts
        a new record. This is handled atomically using an UPSERT (INSERT ...
        ON CONFLICT ... DO UPDATE) SQL statement.

        Args:
            user_id (int): The ID of the user for whom the fetch was performed.
            source_id (int): The ID of the news source that was fetched.
            items_saved_this_run (int): The number of new items saved from this
                source during the current fetch operation. If 0, the method
                returns `True` without making database changes.
            task_group_id (Optional[str]): The Celery task group ID associated
                with this fetch batch. Defaults to None.

        Returns:
            bool: `True` if the operation was successful (record inserted/updated
                  or `items_saved_this_run` was 0), `False` if a database
                  error occurred.

        Raises:
            asyncpg.PostgresError: If a database error occurs during the UPSERT.

        Side Effects:
            - Inserts or updates a record in the `fetch_history` table.
            - Logs the operation status or any errors.
        """
        if items_saved_this_run <= 0:
            logger.debug(
                f"Skipping history record for source {source_id}, user {user_id} "
                f"as items_saved_this_run is {items_saved_this_run}."
            )
            return True  # Not an error, just nothing to record

        current_date = date.today()
        current_timestamp = datetime.now(timezone.utc)

        query_str = f"""
            INSERT INTO {FetchHistory.TABLE_NAME} (
                {FetchHistory.USER_ID}, {FetchHistory.SOURCE_ID}, {FetchHistory.RECORD_DATE},
                {FetchHistory.ITEMS_SAVED_TODAY}, {FetchHistory.LAST_UPDATED_AT},
                {FetchHistory.LAST_BATCH_TASK_GROUP_ID}
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT ({FetchHistory.USER_ID}, {FetchHistory.SOURCE_ID}, {FetchHistory.RECORD_DATE})
            DO UPDATE SET
                {FetchHistory.ITEMS_SAVED_TODAY} = {FetchHistory.TABLE_NAME}.{FetchHistory.ITEMS_SAVED_TODAY} + EXCLUDED.{FetchHistory.ITEMS_SAVED_TODAY},
                {FetchHistory.LAST_UPDATED_AT} = EXCLUDED.{FetchHistory.LAST_UPDATED_AT},
                {FetchHistory.LAST_BATCH_TASK_GROUP_ID} = EXCLUDED.{FetchHistory.LAST_BATCH_TASK_GROUP_ID}
        """
        params: Tuple[Any, ...] = (
            user_id,
            source_id,
            current_date,
            items_saved_this_run,
            current_timestamp,
            task_group_id,
        )

        try:
            status = await self._execute(query_str, params)
            # INSERT 0 1 (new record) or UPDATE 1 (existing record) indicates success.
            # Other statuses might occur if ON CONFLICT DO NOTHING was used and conflict happened.
            success = status is not None and (
                status.lower().startswith("insert")
                or status.lower().startswith("update")
            )
            if success:
                logger.info(
                    f"Recorded/Updated fetch history for source {source_id}, user {user_id}, "
                    f"date {current_date}. Added {items_saved_this_run} items. Status: {status}"
                )
            else:
                # This path might be taken if the status string is unexpected,
                # e.g., "INSERT 0 0" if ON CONFLICT DO NOTHING was used and it conflicted.
                # With DO UPDATE, we expect INSERT or UPDATE.
                logger.warning(
                    f"UPSERT command for fetch history (Source: {source_id}, User: {user_id}, "
                    f"Date: {current_date}) executed but status was '{status}'. "
                    "This might indicate an issue if items_saved_this_run > 0."
                )
            # Return True if no exception, as the DB operation was attempted.
            # Caller might need to check items_saved_this_run if specific outcome is critical.
            return True
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error recording fetch history for source {source_id}, user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Propagate DB errors
        except Exception as e:
            logger.error(
                f"Unexpected error recording fetch history for source {source_id}, user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_history_by_date(
        self, user_id: int, record_date: date
    ) -> List[asyncpg.Record]:
        """
        Retrieves fetch history records for a specific user and date.

        The results include the source name by joining with the `news_sources`
        table and are ordered by the last update time in descending order.

        Args:
            user_id (int): The ID of the user.
            record_date (date): The specific date (YYYY-MM-DD) for which to
                                retrieve history.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  containing history details (source_id,
                                  source_name, record_date, items_saved_today,
                                  last_updated_at). Returns an empty list if no
                                  history is found for the given criteria.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query with a JOIN operation.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT
                fh.{FetchHistory.SOURCE_ID},
                ns.{NewsSource.NAME} AS source_name,
                fh.{FetchHistory.RECORD_DATE},
                fh.{FetchHistory.ITEMS_SAVED_TODAY},
                fh.{FetchHistory.LAST_UPDATED_AT},
                fh.{FetchHistory.LAST_BATCH_TASK_GROUP_ID}
            FROM {FetchHistory.TABLE_NAME} fh
            JOIN {NewsSource.TABLE_NAME} ns ON fh.{FetchHistory.SOURCE_ID} = ns.{NewsSource.ID}
            WHERE fh.{FetchHistory.USER_ID} = $1
              AND fh.{FetchHistory.RECORD_DATE} = $2
              AND ns.{NewsSource.USER_ID} = $1 -- Ensure the source also belongs to the user
            ORDER BY fh.{FetchHistory.LAST_UPDATED_AT} DESC
        """
        params = (user_id, record_date)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting fetch history for user {user_id}, date {record_date}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting fetch history for user {user_id}, date {record_date}: {e}",
                exc_info=True,
            )
            raise

    async def get_history_by_date_range(
        self, user_id: int, start_date: date, end_date: date
    ) -> List[asyncpg.Record]:
        """
        Retrieves fetch history records for a user within a specified date range.

        Results include source names and are ordered by record date (descending)
        and then by last update time (descending).

        Args:
            user_id (int): The ID of the user.
            start_date (date): The start date of the range (inclusive).
            end_date (date): The end date of the range (inclusive).

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects with history
                                  details. Returns an empty list if no history
                                  is found in the range.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query with a JOIN and date range filter.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT
                fh.{FetchHistory.SOURCE_ID},
                ns.{NewsSource.NAME} AS source_name,
                fh.{FetchHistory.RECORD_DATE},
                fh.{FetchHistory.ITEMS_SAVED_TODAY},
                fh.{FetchHistory.LAST_UPDATED_AT},
                fh.{FetchHistory.LAST_BATCH_TASK_GROUP_ID}
            FROM {FetchHistory.TABLE_NAME} fh
            JOIN {NewsSource.TABLE_NAME} ns ON fh.{FetchHistory.SOURCE_ID} = ns.{NewsSource.ID}
            WHERE fh.{FetchHistory.USER_ID} = $1
              AND fh.{FetchHistory.RECORD_DATE} >= $2
              AND fh.{FetchHistory.RECORD_DATE} <= $3
              AND ns.{NewsSource.USER_ID} = $1 -- Ensure source also belongs to user
            ORDER BY fh.{FetchHistory.RECORD_DATE} DESC, fh.{FetchHistory.LAST_UPDATED_AT} DESC
        """
        params = (user_id, start_date, end_date)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting fetch history for user {user_id}, range {start_date}-{end_date}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting fetch history for user {user_id}, range {start_date}-{end_date}: {e}",
                exc_info=True,
            )
            raise
