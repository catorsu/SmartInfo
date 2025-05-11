"""
Main application file for the SmartInfo Backend.
Sets up the FastAPI application, manages application lifespan (DB connection, LLM pool),
and includes the main API router.
"""

import sys
import os
from contextlib import asynccontextmanager
from typing import Optional
import asyncpg
from dotenv import load_dotenv
import logging
import argparse
import redis.asyncio as redis


load_dotenv()


from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
if not isinstance(log_level, int):  # Fallback if getattr fails or returns non-int
    print(
        f"Warning: Invalid LOG_LEVEL '{log_level_name}'. Defaulting to INFO.",
        file=sys.stderr,
    )
    log_level = logging.INFO


logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


from config import config
from db.connection import (
    init_db_connection,
    get_db_connection_context,
)
from db.repositories import UserPreferenceRepository
from core.llm import LLMClientPool
from api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown events.
    - Initializes Database Connection Manager & loads persistent config.
    - Initializes LLM Client Pool.
    - Initializes Redis Connection Pool for WebSocket communication.
    - Sets global LLM pool for dependency injection.
    - Cleans up resources on shutdown.
    """
    logger.info("Application lifespan starting...")
    db_manager = None

    try:

        logger.info("Initializing Database Connection Manager...")
        db_manager = await init_db_connection()
        logger.info("Database Connection Manager initialized successfully.")

        logger.info("Initializing Redis connection pool...")
        app.state.redis_pool = redis.ConnectionPool.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            decode_responses=True,
        )
        app.state.redis_client = redis.Redis(connection_pool=app.state.redis_pool)
        logger.info("Async Redis client initialized.")

    except Exception as e:
        logger.critical(f"Application startup failed: {e}", exc_info=True)

        if db_manager:
            await db_manager._cleanup()

        if hasattr(app.state, "redis_client"):
            await app.state.redis_client.close()
        if hasattr(app.state, "redis_pool"):
            await app.state.redis_pool.disconnect()

        raise RuntimeError("Application startup failed.") from e

    yield

    logger.info("Application lifespan shutting down...")

    if hasattr(app.state, "redis_client"):
        try:
            await app.state.redis_client.close()
            logger.info("Async Redis client closed.")
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}", exc_info=True)

    if hasattr(app.state, "redis_pool"):
        try:
            await app.state.redis_pool.disconnect()
            logger.info("Async Redis connection pool disconnected.")
        except Exception as e:
            logger.error(f"Error disconnecting Redis pool: {e}", exc_info=True)

    if db_manager:
        logger.info("Closing database connection...")
        try:

            await db_manager._cleanup()
            logger.info("Database connection resources released.")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}", exc_info=True)
    else:
        logger.info(
            "Database connection manager was not initialized, skipping cleanup."
        )

    logger.info("Application lifespan finished.")


app = FastAPI(
    title="SmartInfo Backend",
    description="API for news aggregation, analysis, and chat features.",
    version="1.0.0",
    lifespan=lifespan,
)


origins = [
    "http://localhost:3000",
    "http://172.18.0.1:3000",
    "http://192.168.0.107:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="/api")


@app.get("/", tags=["General"], summary="Root Endpoint")
async def read_root():
    """Provides a simple welcome message indicating the backend is running."""
    return {"message": "Welcome to the SmartInfo Backend API!"}


@app.get("/health", tags=["General"], summary="Health Check")
async def health_check(
    db_context=Depends(get_db_connection_context),
):
    """
    Health check endpoint to verify the API is running and the database is reachable.
    """
    db_status = "unknown"
    try:

        async with db_context as conn:

            await conn.fetchval("SELECT 1")
            db_status = "connected"
            logger.debug("Database health check successful.")
    except (asyncpg.PostgresError, OSError, TimeoutError) as e:

        db_status = f"error: {type(e).__name__} - {str(e)}"
        logger.error(f"Database health check failed: {db_status}", exc_info=False)
    except Exception as e:

        db_status = f"unexpected_error: {type(e).__name__} - {str(e)}"
        logger.error(
            f"Unexpected error during database health check: {db_status}", exc_info=True
        )

    return {"api_status": "healthy", "database_status": db_status}


@app.get("/redis-test", tags=["General"], summary="Redis Connection Test")
async def redis_test(request: Request):
    """
    Test endpoint to verify the Redis connection is working correctly.
    """
    try:

        redis_client = request.app.state.redis_client

        await redis_client.ping()

        test_channel = "redis_test_channel"
        test_message = "Hello Redis!"

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(test_channel)

        await redis_client.publish(test_channel, test_message)

        message = await pubsub.get_message(timeout=1.0)
        message = await pubsub.get_message(timeout=1.0)

        await pubsub.unsubscribe(test_channel)
        await pubsub.close()

        return {
            "redis_status": "connected",
            "pubsub_test": (
                "success" if message and message["data"] == test_message else "failed"
            ),
            "message_received": message["data"] if message else None,
        }
    except Exception as e:
        return {"redis_status": "error", "error": str(e)}


def start_api():
    """
    Function to start the API directly (used when run as module).
    Can be configured with environment variables:
    - HOST: The host to bind to (default: 0.0.0.0)
    - PORT: The port to bind to (default: 8000)
    - RELOAD: Whether to auto-reload on code changes (default: False)
    - LOG_LEVEL: Logging level (e.g., DEBUG, INFO, WARNING) - Handled globally now
    """
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    reload_enabled = os.environ.get("RELOAD", "").lower() in (
        "true",
        "1",
        "t",
        "y",
        "yes",
    )

    uvicorn_log_level = logging.getLevelName(log_level).lower()

    logger.info(
        f"Starting SmartInfo API on {host}:{port} (reload: {reload_enabled}, log level: {uvicorn_log_level})"
    )
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=uvicorn_log_level,
    )


if __name__ == "__main__":

    start_api()
