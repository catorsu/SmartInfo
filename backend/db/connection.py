"""
Database Connection Management for SmartInfo.

This module provides a robust, singleton-pattern based connection manager for
the PostgreSQL database used by the SmartInfo application. It handles the
initialization of database resources (either a connection pool or a single
connection), schema creation/verification, and graceful cleanup of connections.
It also offers utility functions for accessing the database connection context,
primarily for dependency injection in FastAPI.
"""

import os
import logging
import asyncpg
from threading import Lock
from typing import Optional, Union, AsyncIterator, TYPE_CHECKING, Any
from contextlib import asynccontextmanager, AbstractAsyncContextManager

from config import config
from db.schema_constants import (
    Users,
    NewsCategory,
    NewsSource,
    News,
    ApiConfig,
    UserPreferences,
    Chats,
    Messages,
    FetchHistory,
)

if TYPE_CHECKING:
    from asyncpg.pool import PoolConnectionProxy
    from asyncpg.connection import Connection as AsyncpgConnection

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """
    Manages the database connection resource (pool or single connection).

    This class implements a singleton pattern to ensure only one instance
    manages the database connection throughout the application's lifecycle.
    It handles initialization, schema creation, and cleanup.

    Attributes:
        _instance (Optional[DatabaseConnectionManager]): The singleton instance.
        _lock (Lock): A threading lock to ensure thread-safe singleton creation.
        _db_resource (Optional[Union[asyncpg.Pool, AsyncpgConnection]]):
            The actual database resource, either a connection pool or a single
            connection object.
        _connection_mode (Optional[str]): Stores the mode of connection,
            either "pool" or "single".
    """

    _instance: Optional["DatabaseConnectionManager"] = None
    _lock: Lock = Lock()
    _db_resource: Optional[Union[asyncpg.Pool, "AsyncpgConnection"]] = None
    _connection_mode: Optional[str] = None

    def __new__(cls) -> "DatabaseConnectionManager":
        """
        Ensures that only one instance of DatabaseConnectionManager is created.

        This method implements the singleton pattern using a thread-safe lock.

        Returns:
            DatabaseConnectionManager: The singleton instance of the class.

        Side Effects:
            - If no instance exists, creates a new `DatabaseConnectionManager`
              instance and assigns it to `cls._instance`.
            - Logs the creation of a new instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info("Creating new DatabaseConnectionManager instance.")
                    cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
        return cls._instance

    async def _initialize(
        self, db_connection_mode: str = "pool", min_size: int = 2, max_size: int = 2
    ) -> None:
        """
        Initializes the database connection resource (pool or single connection).

        Args:
            db_connection_mode (str): "pool" or "single".
            min_size (int): Min pool size for "pool" mode.
            max_size (int): Max pool size for "pool" mode.

        Raises:
            ValueError: If config is missing or mode is invalid.
            asyncpg.PostgresError: For DB connection or table creation errors.
            Exception: For other unexpected errors.

        Side Effects:
            - Sets `self._connection_mode`, `self._db_resource`.
            - Calls `self._create_tables()`.
            - Logs initialization stages.
            - Attempts cleanup on error.
        """
        if self._db_resource is not None:
            logger.warning("Database resource already initialized.")
            return

        self._connection_mode = db_connection_mode
        logger.info(f"Database connection mode set to: {self._connection_mode}")

        try:
            db_user = config.db_user
            db_password = config.db_password
            db_name = config.db_name
            db_host = config.db_host
            db_port = config.db_port

            if not all([db_user, db_password, db_name, db_host, db_port is not None]):
                raise ValueError("Missing required database configuration values.")

            dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            logged_dsn = f"postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}"

            if self._connection_mode == "pool":
                logger.info(f"Initializing database connection pool to: {logged_dsn}")
                self._db_resource = await asyncpg.create_pool(
                    dsn=dsn, min_size=min_size, max_size=max_size
                )
                if not self._db_resource:
                    raise RuntimeError("Failed to create database pool.")
                await self._create_tables(self._db_resource)
                logger.info("Database connection pool initialized successfully.")

            elif self._connection_mode == "single":
                logger.info(f"Initializing single database connection to: {logged_dsn}")
                self._db_resource = await asyncpg.connect(dsn=dsn)
                if not self._db_resource:
                    raise RuntimeError("Failed to create single database connection.")
                await self._create_tables(self._db_resource)
                logger.info("Single database connection initialized successfully.")
            else:
                raise ValueError(
                    f"Invalid DB_CONNECTION_MODE: {self._connection_mode}."
                )

        except ValueError as ve:
            logger.critical(f"Database configuration error: {ve}")
            raise
        except asyncpg.PostgresError as pe:
            logger.error(f"PostgreSQL connection error: {pe}", exc_info=True)
            await self._cleanup()
            raise
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
            await self._cleanup()
            raise

    async def _create_tables(
        self, conn_or_pool: Union[asyncpg.Pool, "AsyncpgConnection"]
    ) -> None:
        """
        Creates database tables if they do not exist.

        Args:
            conn_or_pool: The database connection or pool.

        Raises:
            asyncpg.PostgresError: If schema creation fails.

        Side Effects:
            - Creates tables and indexes in the database.
            - Logs creation status.
        """
        if conn_or_pool is None:
            logger.error("Cannot create tables, DB resource not initialized.")
            return
        logger.info("Verifying/Creating database tables...")

        async def execute_schema(
            conn: Union["AsyncpgConnection", "PoolConnectionProxy"],
        ) -> None:
            async with conn.transaction():  # type: ignore[union-attr]
                try:
                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {Users.TABLE_NAME} ({Users.ID} SERIAL PRIMARY KEY, {Users.USERNAME} TEXT NOT NULL UNIQUE, {Users.HASHED_PASSWORD} TEXT NOT NULL)")  # type: ignore[union-attr]
                    logger.debug(f"Table {Users.TABLE_NAME} checked/created.")
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_users_username ON {Users.TABLE_NAME} ({Users.USERNAME});")  # type: ignore[union-attr]
                    logger.debug("Index idx_users_username checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {NewsCategory.TABLE_NAME} ({NewsCategory.ID} SERIAL PRIMARY KEY, {NewsCategory.NAME} TEXT NOT NULL, {NewsCategory.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, UNIQUE ({NewsCategory.NAME}, {NewsCategory.USER_ID}))")  # type: ignore[union-attr]
                    logger.debug(f"Table {NewsCategory.TABLE_NAME} checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {NewsSource.TABLE_NAME} ({NewsSource.ID} SERIAL PRIMARY KEY, {NewsSource.NAME} TEXT NOT NULL, {NewsSource.URL} TEXT NOT NULL, {NewsSource.CATEGORY_ID} INTEGER NOT NULL REFERENCES {NewsCategory.TABLE_NAME}({NewsCategory.ID}) ON DELETE CASCADE, {NewsSource.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, UNIQUE ({NewsSource.URL}, {NewsSource.USER_ID}), UNIQUE ({NewsSource.NAME}, {NewsSource.USER_ID}))")  # type: ignore[union-attr]
                    logger.debug(f"Table {NewsSource.TABLE_NAME} checked/created.")
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_sources_url ON {NewsSource.TABLE_NAME} ({NewsSource.URL});")  # type: ignore[union-attr]
                    logger.debug("Index idx_news_sources_url checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {News.TABLE_NAME} ({News.ID} BIGSERIAL PRIMARY KEY, {News.TITLE} TEXT NOT NULL, {News.URL} TEXT NOT NULL, {News.SOURCE_NAME} TEXT, {News.CATEGORY_NAME} TEXT, {News.SOURCE_ID} INTEGER REFERENCES {NewsSource.TABLE_NAME}({NewsSource.ID}) ON DELETE SET NULL, {News.CATEGORY_ID} INTEGER REFERENCES {NewsCategory.TABLE_NAME}({NewsCategory.ID}) ON DELETE SET NULL, {News.SUMMARY} TEXT, {News.ANALYSIS} TEXT, {News.DATE} TEXT, {News.CONTENT} TEXT, {News.TOP_IMAGE} TEXT, {News.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, {News.CREATED_AT} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, {News.TASK_GROUP_ID} TEXT, UNIQUE ({News.URL}, {News.USER_ID}))")  # type: ignore[union-attr]
                    logger.debug(f"Table {News.TABLE_NAME} checked/created.")

                    # # Attempt to add task_group_id column if it doesn't exist (for backward compatibility)
                    # try:
                    #     await conn.execute(f"ALTER TABLE {News.TABLE_NAME} ADD COLUMN IF NOT EXISTS {News.TASK_GROUP_ID} TEXT;")  # type: ignore[union-attr]
                    #     logger.debug(
                    #         f"Column {News.TASK_GROUP_ID} checked/added to {News.TABLE_NAME}."
                    #     )
                    # except asyncpg.PostgresError as alter_err:
                    #     # Log error but don't fail the whole schema creation if alter fails (e.g., permissions)
                    #     # The CREATE TABLE already defines it for new setups.
                    #     logger.warning(
                    #         f"Could not ALTER TABLE {News.TABLE_NAME} to add {News.TASK_GROUP_ID}: {alter_err}"
                    #     )

                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_url ON {News.TABLE_NAME} ({News.URL});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_date ON {News.TABLE_NAME} ({News.DATE} DESC);")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_category_id ON {News.TABLE_NAME} ({News.CATEGORY_ID});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_source_id ON {News.TABLE_NAME} ({News.SOURCE_ID});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_user_id ON {News.TABLE_NAME} ({News.USER_ID});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_user_id_created_at ON {News.TABLE_NAME} ({News.USER_ID}, {News.CREATED_AT} DESC);")  # type: ignore[union-attr]

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {ApiConfig.TABLE_NAME} ({ApiConfig.ID} SERIAL PRIMARY KEY, {ApiConfig.MODEL} TEXT NOT NULL, {ApiConfig.BASE_URL} TEXT NOT NULL, {ApiConfig.API_KEY} TEXT NOT NULL, {ApiConfig.CONTEXT} INTEGER, {ApiConfig.MAX_OUTPUT_TOKENS} INTEGER, {ApiConfig.DESCRIPTION} TEXT, {ApiConfig.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, {ApiConfig.CREATED_DATE} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, {ApiConfig.MODIFIED_DATE} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)")  # type: ignore[union-attr]
                    logger.debug(f"Table {ApiConfig.TABLE_NAME} checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {UserPreferences.TABLE_NAME} ({UserPreferences.KEY} TEXT NOT NULL, {UserPreferences.VALUE} TEXT, {UserPreferences.DESCRIPTION} TEXT, {UserPreferences.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, PRIMARY KEY ({UserPreferences.KEY}, {UserPreferences.USER_ID}))")  # type: ignore[union-attr]
                    logger.debug(f"Table {UserPreferences.TABLE_NAME} checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {Chats.TABLE_NAME} ({Chats.ID} BIGSERIAL PRIMARY KEY, {Chats.TITLE} TEXT NOT NULL, {Chats.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, {Chats.CREATED_AT} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, {Chats.UPDATED_AT} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP)")  # type: ignore[union-attr]
                    logger.debug(f"Table {Chats.TABLE_NAME} checked/created.")

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {Messages.TABLE_NAME} ({Messages.ID} BIGSERIAL PRIMARY KEY, {Messages.CHAT_ID} BIGINT NOT NULL REFERENCES {Chats.TABLE_NAME}({Chats.ID}) ON DELETE CASCADE, {Messages.SENDER} TEXT NOT NULL, {Messages.CONTENT} TEXT, {Messages.TIMESTAMP} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, {Messages.SEQUENCE_NUMBER} INTEGER)")  # type: ignore[union-attr]
                    logger.debug(f"Table {Messages.TABLE_NAME} checked/created.")
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_messages_chat_id_sequence ON {Messages.TABLE_NAME} ({Messages.CHAT_ID}, {Messages.SEQUENCE_NUMBER});")  # type: ignore[union-attr]

                    await conn.execute(f"CREATE TABLE IF NOT EXISTS {FetchHistory.TABLE_NAME} ({FetchHistory.ID} BIGSERIAL PRIMARY KEY, {FetchHistory.USER_ID} INTEGER NOT NULL REFERENCES {Users.TABLE_NAME}({Users.ID}) ON DELETE CASCADE, {FetchHistory.SOURCE_ID} INTEGER NOT NULL REFERENCES {NewsSource.TABLE_NAME}({NewsSource.ID}) ON DELETE CASCADE, {FetchHistory.RECORD_DATE} DATE NOT NULL, {FetchHistory.ITEMS_SAVED_TODAY} INTEGER DEFAULT 0, {FetchHistory.LAST_UPDATED_AT} TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, {FetchHistory.LAST_BATCH_TASK_GROUP_ID} TEXT, UNIQUE ({FetchHistory.USER_ID}, {FetchHistory.SOURCE_ID}, {FetchHistory.RECORD_DATE}))")  # type: ignore[union-attr]
                    logger.debug(f"Table {FetchHistory.TABLE_NAME} checked/created.")
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_fetch_history_user_id ON {FetchHistory.TABLE_NAME} ({FetchHistory.USER_ID});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_fetch_history_source_id ON {FetchHistory.TABLE_NAME} ({FetchHistory.SOURCE_ID});")  # type: ignore[union-attr]
                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_fetch_history_date ON {FetchHistory.TABLE_NAME} ({FetchHistory.RECORD_DATE});")  # type: ignore[union-attr]

                    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_news_search_fts ON {News.TABLE_NAME} USING GIN (to_tsvector('simple', COALESCE({News.TITLE}, '') || ' ' || COALESCE({News.SUMMARY}, '') || ' ' || COALESCE({News.SOURCE_NAME}, '') || ' ' || COALESCE({News.CATEGORY_NAME}, '')));")  # type: ignore[union-attr]
                    logger.debug(
                        "Index idx_news_search_fts checked/created (using 'simple')."
                    )

                    logger.info("All DB tables and indexes verified/created.")
                except asyncpg.PostgresError as e:
                    logger.error(f"Error creating schema: {e}", exc_info=True)
                    raise
                except Exception as e:
                    logger.error(
                        f"Unexpected error in schema creation: {e}", exc_info=True
                    )
                    raise

        if isinstance(conn_or_pool, asyncpg.Pool):
            async with conn_or_pool.acquire() as conn:  # conn is PoolConnectionProxy
                await execute_schema(conn)
        else:  # conn_or_pool is AsyncpgConnection
            await execute_schema(conn_or_pool)

    async def _cleanup(self) -> None:
        """Closes the database connection resource."""
        if self._db_resource:
            logger.info(f"Closing database resource ({self._connection_mode} mode)...")
            try:
                if isinstance(
                    self._db_resource, asyncpg.Pool
                ):  # Check type before calling close
                    await self._db_resource.close()
                    logger.info("Database connection pool closed.")
                elif isinstance(self._db_resource, asyncpg.Connection):  # Check type
                    await self._db_resource.close()
                    logger.info("Single database connection closed.")
                else:
                    logger.warning(
                        f"DB resource type mismatch or unknown mode: {type(self._db_resource)}"
                    )
            except Exception as e:
                logger.error(f"Error closing database resource: {e}", exc_info=True)
            finally:
                self._db_resource = None
                self._connection_mode = None
        else:
            logger.info("DB resource not initialized or already cleaned up.")

    def _cleanup_sync(self) -> None:
        """Synchronous wrapper for `_cleanup()`, for `atexit`."""
        import asyncio

        logger.info("Attempting synchronous cleanup for DatabaseConnectionManager...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._cleanup())
        except Exception as e:
            logger.error(f"Error in _cleanup_sync: {e}", exc_info=True)
        finally:
            logger.info("Synchronous cleanup attempt finished.")

    @asynccontextmanager
    async def get_db_connection_context(
        self,
    ) -> AsyncIterator[Union["AsyncpgConnection", "PoolConnectionProxy"]]:
        """
        Provides an async context manager for database connections.

        Yields:
            Union[AsyncpgConnection, PoolConnectionProxy]: An active DB connection.

        Raises:
            RuntimeError: If DB manager fails to initialize or is in invalid mode.
            TypeError: If resource type mismatches connection mode.
        """
        if self._db_resource is None:
            logger.warning("DB manager accessed before init. Attempting lazy init.")
            await self._initialize()

        if self._db_resource is None:
            raise RuntimeError("Database connection manager failed to initialize.")

        if self._connection_mode == "pool":
            if not isinstance(self._db_resource, asyncpg.Pool):
                raise TypeError(
                    f"DB resource not a Pool in 'pool' mode. Type: {type(self._db_resource)}"
                )
            conn_proxy: Optional[PoolConnectionProxy] = None
            try:
                conn_proxy = await self._db_resource.acquire()
                assert (
                    conn_proxy is not None
                ), "Connection proxy should not be None after acquire."
                yield conn_proxy
            finally:
                if conn_proxy:
                    await self._db_resource.release(conn_proxy)
        elif self._connection_mode == "single":
            if not isinstance(
                self._db_resource, asyncpg.Connection
            ):  # Use asyncpg.Connection
                raise TypeError(
                    f"DB resource not a Connection in 'single' mode. Type: {type(self._db_resource)}"
                )
            assert (
                self._db_resource is not None
            ), "DB resource should not be None in single connection mode."  # Ensure it's not None before yielding
            yield self._db_resource  # This is AsyncpgConnection
        else:
            raise RuntimeError(f"DB manager in invalid mode: {self._connection_mode}")


_db_connection_manager: Optional[DatabaseConnectionManager] = None


async def init_db_connection(
    db_connection_mode: str = "pool", min_size: int = 2, max_size: int = 2
) -> DatabaseConnectionManager:
    """
    Initializes the global database connection manager.

    Args:
        db_connection_mode (str): "pool" or "single".
        min_size (int): Min pool size.
        max_size (int): Max pool size.

    Returns:
        DatabaseConnectionManager: The initialized global instance.
    """
    global _db_connection_manager
    if _db_connection_manager is None:
        _db_connection_manager = DatabaseConnectionManager()
    await _db_connection_manager._initialize(db_connection_mode, min_size, max_size)
    return _db_connection_manager


def get_db_connection_manager() -> DatabaseConnectionManager:
    """
    Retrieves the global database connection manager instance.

    Returns:
        DatabaseConnectionManager: The global singleton instance.
    """
    global _db_connection_manager
    if _db_connection_manager is None:
        _db_connection_manager = DatabaseConnectionManager()
    return _db_connection_manager


def get_db_connection_context() -> (
    AbstractAsyncContextManager[Union["AsyncpgConnection", "PoolConnectionProxy"]]
):
    """
    Provides a dependency-injectable async context manager for DB connections.

    Returns:
        AbstractAsyncContextManager yielding a DB connection.
    """
    manager = get_db_connection_manager()
    return manager.get_db_connection_context()
