"""
Base Repository Module for SmartInfo.

This module provides a common base class (`BaseRepository`) for all database
repository classes in the SmartInfo application. It encapsulates common
asynchronous database operations using `asyncpg`, such as executing queries,
fetching single or multiple rows, and managing database connection contexts.
Subclasses will inherit these helper methods to interact with specific tables.
"""

import logging
import asyncpg  # Keep this for asyncpg.Record and asyncpg.PostgresError
from typing import Any, List, Tuple, Optional, Union, TYPE_CHECKING, AsyncIterator
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from db.connection import get_db_connection_context

if TYPE_CHECKING:
    from asyncpg.pool import PoolConnectionProxy
    from asyncpg.connection import (
        Connection as AsyncpgConnection,
    )  # Explicit import for Connection

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Base repository providing common asynchronous database operations using asyncpg.

    This class is intended to be subclassed by specific entity repositories.
    It handles acquiring database connections via an async context manager and
    provides helper methods for executing various types of SQL queries.

    Attributes:
        _connection_override (Optional[AsyncpgConnection]): An optional,
            externally provided database connection. Primarily used for testing
            to inject a mock or specific connection instance, bypassing the
            default connection context manager.
    """

    def __init__(self, connection: Optional["AsyncpgConnection"] = None) -> None:
        """
        Initializes the BaseRepository.

        Args:
            connection (Optional[AsyncpgConnection]): An optional asyncpg
                connection object. If provided, this connection will be used
                for all database operations. Defaults to None.

        Side Effects:
            - Sets `self._connection_override`.
        """
        self._connection_override = connection

    def _get_connection_context(
        self,
    ) -> AbstractAsyncContextManager[Union["AsyncpgConnection", "PoolConnectionProxy"]]:
        """
        Gets the appropriate asynchronous database connection context manager.

        Returns:
            AbstractAsyncContextManager yielding a DB connection.

        Side Effects:
            - May trigger lazy initialization of the global DB connection manager.
        """
        if self._connection_override:

            @asynccontextmanager
            async def override_context_manager() -> AsyncIterator["AsyncpgConnection"]:
                if self._connection_override is None:
                    raise RuntimeError("Connection override was None when expected.")
                yield self._connection_override

            return override_context_manager()
        else:
            return get_db_connection_context()

    async def _execute(self, query: str, params: Tuple[Any, ...] = ()) -> Optional[str]:
        """
        Executes a SQL query (INSERT, UPDATE, DELETE).

        Args:
            query (str): SQL query string.
            params (Tuple[Any, ...]): Parameters for the query.

        Returns:
            Optional[str]: Status string from `asyncpg`.

        Raises:
            asyncpg.PostgresError: For database errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Executes SQL query, may modify database state.
            - Logs errors.
        """
        try:
            async with self._get_connection_context() as conn:
                status_string: Optional[str] = await conn.execute(query, *params)
                return status_string
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error executing query: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during query execution: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise

    async def _executemany(
        self, query: str, params_list: List[Tuple[Any, ...]]
    ) -> bool:
        """
        Executes a batch query with multiple parameter sets.

        Args:
            query (str): SQL query string.
            params_list (List[Tuple[Any, ...]]): List of parameter tuples.

        Returns:
            bool: `True` if execution was successful.

        Raises:
            asyncpg.PostgresError: For database errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Executes SQL query multiple times, may modify database state.
            - Logs errors.
        """
        try:
            async with self._get_connection_context() as conn:
                await conn.executemany(query, params_list)
                return True
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error executing batch query: {query}. Error: {e}", exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during batch query execution: {query}. Error: {e}",
                exc_info=True,
            )
            raise

    async def _fetchval(
        self, query: str, params: Tuple[Any, ...] = ()
    ) -> Optional[Any]:
        """
        Executes a query and fetches a single scalar value.

        Args:
            query (str): SQL query string.
            params (Tuple[Any, ...]): Parameters for the query.

        Returns:
            Optional[Any]: Single value or `None`.

        Raises:
            asyncpg.PostgresError: For database errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Executes SQL query.
            - Logs errors.
        """
        try:
            async with self._get_connection_context() as conn:
                return await conn.fetchval(query, *params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error fetching value: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching value: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise

    async def _fetchone(
        self, query: str, params: Tuple[Any, ...] = ()
    ) -> Optional[asyncpg.Record]:
        """
        Executes a query and fetches one result as an `asyncpg.Record`.

        Args:
            query (str): SQL query string.
            params (Tuple[Any, ...]): Parameters for the query.

        Returns:
            Optional[asyncpg.Record]: Single row or `None`.

        Raises:
            asyncpg.PostgresError: For database errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Executes SQL query.
            - Logs errors.
        """
        try:
            async with self._get_connection_context() as conn:
                return await conn.fetchrow(query, *params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error fetching one row: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching one row: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise

    async def _fetchall(
        self, query: str, params: Tuple[Any, ...] = ()
    ) -> List[asyncpg.Record]:
        """
        Executes a query and fetches all results as a list of `asyncpg.Record`.

        Args:
            query (str): SQL query string.
            params (Tuple[Any, ...]): Parameters for the query.

        Returns:
            List[asyncpg.Record]: List of rows or empty list.

        Raises:
            asyncpg.PostgresError: For database errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Executes SQL query.
            - Logs errors.
        """
        try:
            async with self._get_connection_context() as conn:
                return await conn.fetch(query, *params)
        except asyncpg.PostgresError as e:
            logger.error(
                f"Error fetching all rows: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error fetching all rows: {query} with params {params}. Error: {e}",
                exc_info=True,
            )
            raise
