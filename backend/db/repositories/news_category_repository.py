"""
News Category Repository Module for SmartInfo.

This module handles database operations for news categories, allowing users
to organize their news sources. It interacts with the `news_category` table.

@module_purpose: To provide a persistent storage interface for user-defined
                 news categories.
@primary_consumers: `services.news_service.NewsService`.
@primary_dependencies: `db.repositories.base_repository.BaseRepository`,
                       `db.schema_constants.NewsCategory`,
                       `db.schema_constants.NewsSource` (for counts), `asyncpg`.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
import asyncpg

from db.schema_constants import NewsCategory, NewsSource  # NewsSource for join in count
from db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NewsCategoryRepository(BaseRepository):
    """
    Repository for news_category table operations.

    Provides methods for adding, retrieving, updating, and deleting news
    categories for users. It also includes a method to get categories along
    with a count of associated news sources.

    @class_responsibility: To encapsulate all database interactions related to
                           the `news_category` table.
    @typical_usage_pattern: Instantiated and used by `NewsService` to manage
                            news categories based on user actions.
    """

    async def add(self, name: str, user_id: int) -> Optional[int]:
        """
        Adds a new news category for a user.

        If a category with the same name already exists for the user, this
        method attempts to retrieve and return the ID of the existing category.
        Uses `ON CONFLICT DO NOTHING` to handle potential race conditions or
        duplicate additions gracefully.

        Args:
            name (str): The name of the category to add.
            user_id (int): The ID of the user for whom the category is being added.

        Returns:
            Optional[int]: The ID of the newly added or existing category if
                           successful, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs that is not a
                                   handled conflict.

        Side Effects:
            - Inserts a new record into the `news_category` table if the category
              does not already exist for the user.
            - May execute a SELECT query to fetch the ID if a conflict occurs.
            - Logs the operation status or any errors.
        """
        # Attempt to insert, if conflict (name, user_id unique constraint), do nothing.
        # Then, select the ID. This is more robust than select-then-insert for concurrency.
        query_insert = f"""
            INSERT INTO {NewsCategory.TABLE_NAME} ({NewsCategory.NAME}, {NewsCategory.USER_ID})
            VALUES ($1, $2)
            ON CONFLICT ({NewsCategory.NAME}, {NewsCategory.USER_ID}) DO NOTHING
            RETURNING {NewsCategory.ID}
        """
        # Query to select the ID, used if INSERT returns nothing (due to conflict or other reasons)
        query_select = f"""
            SELECT {NewsCategory.ID} FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.NAME} = $1 AND {NewsCategory.USER_ID} = $2
        """
        params = (name, user_id)

        try:
            # First, try to insert and get the ID directly
            inserted_record = await self._fetchone(query_insert, params)
            if inserted_record and inserted_record[0] is not None:
                inserted_id = int(inserted_record[0])
                logger.info(
                    f"Added news category '{name}' with ID {inserted_id} for user {user_id}."
                )
                return inserted_id
            else:
                # If INSERT returned nothing (e.g., ON CONFLICT DO NOTHING triggered, or some other issue)
                # try to select the existing category's ID.
                logger.debug(
                    f"Category '{name}' for user {user_id} insert returned no ID (likely exists or failed). "
                    "Attempting to fetch existing ID."
                )
                existing_record = await self._fetchone(query_select, params)
                if existing_record and existing_record[0] is not None:
                    existing_id = int(existing_record[0])
                    logger.debug(
                        f"Found existing category '{name}' with ID {existing_id} for user {user_id}."
                    )
                    return existing_id
                else:
                    # This case means INSERT failed to return ID AND SELECT also failed to find it.
                    # This could happen if the INSERT failed for reasons other than conflict
                    # and the record truly doesn't exist.
                    logger.error(
                        f"Failed to add or find category '{name}' for user {user_id} after insert attempt."
                    )
                    return None

        except asyncpg.PostgresError as e:
            logger.error(
                f"Error adding news category '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error adding news category '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_id(
        self, category_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific news category by its ID, ensuring it belongs to the
        specified user.

        Args:
            category_id (int): The ID of the category to retrieve.
            user_id (int): The ID of the user who is expected to own the category.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      category details if found and owned by the
                                      user, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query against the `news_category` table.
            - Logs errors if any occur.
        """
        query_str = f"""
            SELECT {NewsCategory.ID}, {NewsCategory.NAME}, {NewsCategory.USER_ID}
            FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.ID} = $1 AND {NewsCategory.USER_ID} = $2
        """
        params = (category_id, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting category by ID {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting category by ID {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_by_name(self, name: str, user_id: int) -> Optional[asyncpg.Record]:
        """
        Retrieves a specific news category by its name, ensuring it belongs to
        the specified user.

        Args:
            name (str): The name of the category to retrieve.
            user_id (int): The ID of the user who is expected to own the category.

        Returns:
            Optional[asyncpg.Record]: An `asyncpg.Record` object containing the
                                      category details if found and owned by the
                                      user, otherwise `None`.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {NewsCategory.ID}, {NewsCategory.NAME}, {NewsCategory.USER_ID}
            FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.NAME} = $1 AND {NewsCategory.USER_ID} = $2
        """
        params = (name, user_id)
        try:
            return await self._fetchone(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting category by name '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting category by name '{name}' for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def exists_by_name(self, name: str, user_id: int) -> bool:
        """
        Checks if a news category with the given name exists for a specific user.

        Args:
            name (str): The name of the category to check.
            user_id (int): The ID of the user.

        Returns:
            bool: `True` if a category with that name exists for the user,
                  `False` otherwise or if an error occurs.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT 1 ... LIMIT 1 query.
            - Logs errors.
        """
        query_str = f"""
            SELECT 1 FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.NAME} = $1 AND {NewsCategory.USER_ID} = $2
            LIMIT 1
        """
        params = (name, user_id)
        try:
            record = await self._fetchone(query_str, params)
            return record is not None
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error checking if category '{name}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False
        except Exception as e:
            logger.error(
                f"Unexpected error checking if category '{name}' exists for user {user_id}: {e}",
                exc_info=True,
            )
            raise  # Or return False

    async def get_all(self, user_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all news categories for a specific user, ordered by name.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects, each
                                  representing a category. Returns an empty list
                                  if no categories are found.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query.
            - Logs errors.
        """
        query_str = f"""
            SELECT {NewsCategory.ID}, {NewsCategory.NAME}, {NewsCategory.USER_ID}
            FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.USER_ID} = $1
            ORDER BY {NewsCategory.NAME} ASC
        """
        params = (user_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting all categories for user {user_id}: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting all categories for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def get_with_source_count(self, user_id: int) -> List[asyncpg.Record]:
        """
        Retrieves all categories for a user, along with a count of associated
        news sources that also belong to that user.

        Args:
            user_id (int): The ID of the user.

        Returns:
            List[asyncpg.Record]: A list of `asyncpg.Record` objects. Each record
                                  includes category ID, name, and `source_count`.
                                  Returns an empty list if no categories are found.

        Raises:
            asyncpg.PostgresError: If a database error occurs.

        Side Effects:
            - Executes a SELECT query with a LEFT JOIN and GROUP BY.
            - Logs errors.
        """
        query_str = f"""
            SELECT
                c.{NewsCategory.ID},
                c.{NewsCategory.NAME},
                COUNT(s.{NewsSource.ID}) as source_count
            FROM {NewsCategory.TABLE_NAME} c
            LEFT JOIN {NewsSource.TABLE_NAME} s
                ON c.{NewsCategory.ID} = s.{NewsSource.CATEGORY_ID}
                AND s.{NewsSource.USER_ID} = c.{NewsCategory.USER_ID} -- Crucial: source must also belong to user
            WHERE c.{NewsCategory.USER_ID} = $1
            GROUP BY c.{NewsCategory.ID}, c.{NewsCategory.NAME}
            ORDER BY c.{NewsCategory.NAME} ASC
        """
        params = (user_id,)
        try:
            return await self._fetchall(query_str, params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error getting categories with source count for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error getting categories with source count for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def update(self, category_id: int, user_id: int, name: str) -> bool:
        """
        Updates the name of a news category for a specific user.

        Args:
            category_id (int): The ID of the category to update.
            user_id (int): The ID of the user who owns the category.
            name (str): The new name for the category.

        Returns:
            bool: `True` if the update was successful (one row affected),
                  `False` otherwise (e.g., category not found, not owned,
                  or name conflict with another category of the same user).

        Raises:
            asyncpg.IntegrityConstraintViolationError: If the new name conflicts
                with an existing category name for the same user.
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Updates a record in the `news_category` table.
            - Logs status or errors.
        """
        query_str = f"""
            UPDATE {NewsCategory.TABLE_NAME}
            SET {NewsCategory.NAME} = $1
            WHERE {NewsCategory.ID} = $2 AND {NewsCategory.USER_ID} = $3
        """
        params = (name, category_id, user_id)
        try:
            status = await self._execute(query_str, params)
            updated = status is not None and status.lower().startswith("update 1")
            if updated:
                logger.info(
                    f"Updated category ID {category_id} to '{name}' for user {user_id}."
                )
            else:
                logger.warning(
                    f"Update command for category ID {category_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Category might not exist or belong to user."
                )
            return updated
        except (
            asyncpg.IntegrityConstraintViolationError
        ) as e:  # Catches unique constraint violation
            logger.error(
                f"Error updating category ID {category_id} for user {user_id} "
                f"(potential duplicate name '{name}'): {e}",
                exc_info=True,
            )
            # This specific error is often a client-side validation issue (duplicate name)
            # Depending on desired behavior, could return False or re-raise a custom exception.
            # For now, re-raising to let service layer handle it.
            raise
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error updating category ID {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error updating category ID {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, category_id: int, user_id: int) -> bool:
        """
        Deletes a news category for a specific user.

        Note: This operation might fail if there are news sources associated
        with this category, depending on the foreign key constraint's `ON DELETE`
        behavior (e.g., `RESTRICT` would prevent deletion). The current schema
        uses `ON DELETE CASCADE` for `news_sources.category_id`, so deleting
        a category will also delete its associated news sources.

        Args:
            category_id (int): The ID of the category to delete.
            user_id (int): The ID of the user who owns the category.

        Returns:
            bool: `True` if deletion was successful (one row affected),
                  `False` otherwise (e.g., category not found or not owned).

        Raises:
            asyncpg.ForeignKeyViolationError: If deletion is blocked by foreign
                key constraints (though less likely with `ON DELETE CASCADE`).
            asyncpg.PostgresError: For other database errors.

        Side Effects:
            - Deletes a record from `news_category`.
            - May delete associated records in `news_sources` if `ON DELETE CASCADE`
              is in effect.
            - Logs status or errors.
        """
        query_str = f"""
            DELETE FROM {NewsCategory.TABLE_NAME}
            WHERE {NewsCategory.ID} = $1 AND {NewsCategory.USER_ID} = $2
        """
        params = (category_id, user_id)
        try:
            status = await self._execute(query_str, params)
            deleted = status is not None and status.lower().startswith("delete 1")
            if deleted:
                logger.info(f"Deleted category ID {category_id} for user {user_id}.")
            else:
                logger.warning(
                    f"Delete command for category ID {category_id} (User: {user_id}) "
                    f"executed but status was '{status}'. Category might not exist or not belong to user."
                )
            return deleted
        except (
            asyncpg.ForeignKeyViolationError
        ) as e:  # Should be less common with ON DELETE CASCADE
            logger.error(
                f"Cannot delete category ID {category_id} for user {user_id} "
                f"due to existing dependent records (this suggests ON DELETE RESTRICT or similar): {e}",
                exc_info=True,
            )
            raise  # Or return False
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error deleting category {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error deleting category {category_id} for user {user_id}: {e}",
                exc_info=True,
            )
            raise
