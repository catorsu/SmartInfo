"""
Celery tasks for news processing
Handles background processing of news sources and articles,
while reporting progress through Redis Pub/Sub mechanism.
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, List, Union
import os
import redis.asyncio as redis
import redis as sync_redis

from celery import shared_task


from core.llm.pool import LLMClientPool
from db.repositories import (
    NewsRepository,
    NewsSourceRepository,
    ApiKeyRepository,
    FetchHistoryRepository,
)
from models import ApiKey


from core.workflow.news_fetch import fetch_news


from db.connection import init_db_connection, DatabaseConnectionManager


from core.ws_manager import ws_manager


from .step_codes import (
    PREPARING,
    CRAWLING,
    EXTRACTING_LINKS,
    ANALYZING,
    SAVING,
    COMPLETE,
    ERROR,
    SKIPPED,
)


logger = logging.getLogger(__name__)


MAX_CONCURRENT_SOURCES = 3


async def _run_batch_processing(
    task,
    source_ids: List[int],
    user_id: int,
    task_group_id: str,
):
    """
    Main async function executed by asyncio.run() within the Celery task.
    Manages database connection, repositories, LLM client, and processes a batch of sources concurrently.
    Sends progress updates and errors via Redis Pub/Sub using the task_group_id as channel name.
    """
    pid = os.getpid()
    db_manager: Optional[DatabaseConnectionManager] = None
    llm_pool: Optional[LLMClientPool] = None
    news_repo: Optional[NewsRepository] = None
    source_repo: Optional[NewsSourceRepository] = None
    api_key_repo: Optional[ApiKeyRepository] = None
    fetch_history_repo: Optional[FetchHistoryRepository] = None
    redis_client = None

    # Define progress callback that publishes updates via Redis
    async def progress_callback(
        source_id: int,
        source_name: str,  # Kept for internal logging but not included in update_data
        step: Union[int, str],
        progress: float,
        details: str = "",
        items_count: int = 0,  # This now represents items_saved_this_run for the final COMPLETE step
    ):
        update_data = {
            "event": "source_progress",  # Event type for frontend
            "source_id": source_id,
            "step": step,
            "progress": round(progress, 1),  # Round progress to one decimal
        }

        is_complete = step == COMPLETE
        is_error = step == ERROR
        is_skipped = step == SKIPPED

        if is_complete and items_count > 0:
            update_data["items_saved"] = items_count
        elif is_error:
            update_data["error"] = (
                True  # Simplified to boolean instead of detailed message
            )
        elif is_skipped:
            update_data["skipped"] = True

        # Publish update to Redis
        channel = f"task_progress:{task_group_id}"
        if redis_client:
            try:

                json_message = json.dumps(update_data)

                await redis_client.publish(channel, json_message)
                # Reduce logging frequency for non-error/completion updates
                if is_complete or is_error:
                    logger.info(
                        f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) Published final status for source {source_id}: {update_data}"
                    )
                else:
                    logger.debug(
                        f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) Published progress update to {channel}: {update_data}"
                    )
            except Exception as e:
                logger.error(f"Failed to publish progress update to Redis: {e}")
        else:
            logger.warning("Redis client not available for progress updates")

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) Progress: Source {source_id} ({source_name}): {step} - {progress:.1f}% - {details}"
        )

    try:

        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        redis_client = await redis.Redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Redis client initialized for task {task.request.id}")

        # 1. Initialize DB connection manager and acquire connection context
        # Using "pool" mode with min/max size 1 is appropriate for a single task needing a connection.
        db_manager = await init_db_connection(
            db_connection_mode="pool",
            min_size=MAX_CONCURRENT_SOURCES,
            max_size=MAX_CONCURRENT_SOURCES,
        )

        # 2. Initialize Repositories with the acquired connection
        news_repo = NewsRepository()
        source_repo = NewsSourceRepository()
        api_key_repo = ApiKeyRepository()
        fetch_history_repo = FetchHistoryRepository()
        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Repositories initialized."
        )

        # 3. Fetch and Validate Source Details
        source_details_to_process: List[Dict[str, Any]] = []
        for source_id in source_ids:
            source_record = await source_repo.get_by_id(source_id, user_id)
            if not source_record:
                logger.warning(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Source ID {source_id} not found or not owned by user {user_id}. Skipping."
                )

                await progress_callback(
                    source_id=source_id,
                    source_name=f"Unknown Source (ID: {source_id})",
                    step=SKIPPED,
                    progress=100,
                    details=f"Source ID {source_id} not found or does not belong to user {user_id}",
                )
                continue
            source_details_to_process.append(dict(source_record))

        if not source_details_to_process:
            logger.warning(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): No valid sources to process for user {user_id} in this batch."
            )

            completion_data = {
                "event": "batch_task_completed",
                "task_id": task.request.id,
                "message": "No valid sources to process in this batch.",
                "items_saved": 0,
                "affected_source_ids": source_ids,
            }
            channel = f"task_progress:{task_group_id}"
            if redis_client:
                await redis_client.publish(channel, json.dumps(completion_data))

            return {
                "task_id": task.request.id,
                "task_group_id": task_group_id,
                "status": "SUCCESS",
                "processed_sources_count": 0,
                "successful_sources_count": 0,
                "failed_sources_count": 0,
                "items_saved_in_batch": 0,
                "message": "No valid sources to process in this batch.",
            }

        # 4. Initialize a single LLM Client for the batch
        llm_pool = await _get_user_llm_pool(user_id, api_key_repo)
        if llm_pool is None:
            logger.error(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): No valid LLM API key found for user {user_id}. Cannot process batch."
            )

            failure_data = {
                "event": "batch_task_failed",
                "task_id": task.request.id,
                "affected_source_ids": source_ids,
                "message": f"Celery task failed: No valid LLM API key found for user {user_id}",
            }
            channel = f"task_progress:{task_group_id}"
            if redis_client:
                await redis_client.publish(channel, json.dumps(failure_data))

            # Re-raise to mark the Celery task as FAILED
            raise Exception(f"No valid LLM API key found for user {user_id}")

        # 5. Process sources concurrently using asyncio.create_task and asyncio.as_completed
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOURCES)
        results = []
        tasks_to_run = []

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Creating tasks for {len(source_details_to_process)} sources."
        )

        for source_details_item in source_details_to_process:

            coro = _process_single_source_concurrently(
                semaphore=semaphore,
                task=task,  # Pass task instance
                source_details=source_details_item,
                llm_pool=llm_pool,
                news_repo=news_repo,
                fetch_history_repo=fetch_history_repo,
                user_id=user_id,
                progress_callback=progress_callback,  # Pass the modified callback
                task_group_id=task_group_id,
            )
            tasks_to_run.append(asyncio.create_task(coro))

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Starting processing of {len(tasks_to_run)} source tasks."
        )

        for future in asyncio.as_completed(tasks_to_run):
            try:
                result = await future
                results.append(result)
            except Exception as e:

                # The actual source_id would be tricky to get here if the task failed early
                # We rely on logging within _process_single_source_concurrently for specific source errors
                logger.error(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
                    f"Error in awaited source processing task: {e}",
                    exc_info=True,
                )
                # Append a generic error placeholder; specific source error should have been reported by callback
                results.append(
                    {
                        "source_id": "unknown_due_to_task_error",  # Cannot reliably get source_id here
                        "status": "error",
                        "message": str(e),
                    }
                )

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): All source processing tasks completed."
        )

        successful_count = sum(
            1 for r in results if isinstance(r, dict) and r.get("status") == "success"
        )
        error_count = len(results) - successful_count
        items_saved = sum(
            r.get("items_saved", 0)
            for r in results
            if isinstance(r, dict) and r.get("status") == "success"
        )

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Batch processing summary - Successful: {successful_count}, Errors: {error_count}, Items saved: {items_saved}"
        )

        completion_data = {
            "event": "batch_task_completed",
            "task_id": task.request.id,
            "message": f"Batch processing completed. Successful: {successful_count}, Errors: {error_count}",
            "items_saved": items_saved,
            "affected_source_ids": source_ids,
        }
        channel = f"task_progress:{task_group_id}"
        if redis_client:
            await redis_client.publish(channel, json.dumps(completion_data))

        return {
            "task_id": task.request.id,
            "task_group_id": task_group_id,
            "status": "SUCCESS" if error_count == 0 else "COMPLETED_WITH_ERRORS",
            "processed_sources_count": len(source_details_to_process),
            "successful_sources_count": successful_count,
            "failed_sources_count": error_count,
            "message": f"Batch processing completed. Successful: {successful_count}, Errors: {error_count}",
        }

    except Exception as e:
        logger.exception(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Unhandled error during batch async processing for user {user_id}: {e}"
        )

        failure_data = {
            "event": "batch_task_failed",
            "task_id": task.request.id,
            "affected_source_ids": source_ids,
            "message": f"Celery task failed: {str(e)}",
        }
        try:
            channel = f"task_progress:{task_group_id}"
            if redis_client:
                await redis_client.publish(channel, json.dumps(failure_data))
        except Exception as cb_e:
            logger.error(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Failed to send batch error state via Redis: {cb_e}"
            )
        # Re-raise to let the sync wrapper handle FAILURE state
        raise  # Crucially re-raise the exception

    finally:

        if redis_client:
            try:
                await redis_client.close()
                logger.info(f"Redis client closed for task {task.request.id}")
            except Exception as redis_err:
                logger.error(f"Error closing Redis client: {redis_err}")

        if llm_pool:
            try:
                await llm_pool.close()
                logger.info(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): LLM pool closed in finally block."
                )
            except Exception as close_err:
                logger.error(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Error closing LLM pool in finally block: {close_err}"
                )

        if db_manager:
            try:
                await db_manager._cleanup()
                logger.info(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Database connection closed in finally block."
                )
            except Exception as close_err:
                logger.error(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Error closing database connection in finally block: {close_err}"
                )


async def _process_single_source_concurrently(
    semaphore: asyncio.Semaphore,
    task,
    source_details: Dict[str, Any],
    llm_pool: LLMClientPool,
    news_repo: NewsRepository,
    fetch_history_repo: FetchHistoryRepository,
    user_id: int,
    progress_callback: callable,
    task_group_id: str,
) -> Dict[str, Any]:
    """
    Processes a single news source within the batch, managed by a semaphore.
    Calls the core workflow function and handles saving results.
    """
    pid = os.getpid()
    source_id = source_details["id"]
    url = source_details["url"]
    source_name = source_details["name"]
    category_id = source_details.get("category_id")
    category_name = source_details.get("category_name", "未知分类")

    async def source_progress_callback(
        step: Union[int, str], progress: float, details: str = "", items_count: int = 0
    ):
        # Only pass items_count when step is COMPLETE
        items_to_send = items_count if step == COMPLETE else 0

        await progress_callback(
            source_id=source_id,
            source_name=source_name,
            step=step,
            progress=progress,
            details=details,
            items_count=items_to_send,
        )

    async with semaphore:
        logger.info(
            f"[PID:{pid}] Task {task.request.id}: Starting processing for source {source_id} ({source_name}, User: {user_id})."
        )
        try:
            await source_progress_callback(PREPARING, 5, "Preparing to fetch data...")

            exclude_links = await news_repo.get_all_urls(user_id)
            logger.info(
                f"[PID:{pid}] Task {task.request.id}: Source {source_id}: Found {len(exclude_links)} existing URLs for user {user_id}."
            )

            fetch_result = None
            try:
                fetch_result = await fetch_news(
                    url=url,
                    llm_pool=llm_pool,
                    exclude_links=exclude_links,
                    progress_callback=source_progress_callback,
                )

            except Exception as e:
                logger.exception(
                    f"[PID:{pid}] Task {task.request.id}: Source {source_id}: Error during fetch_news: {e}"
                )
                await source_progress_callback(
                    ERROR, 0, f"Fetch and analysis error: {str(e)}"
                )
                return {
                    "source_id": source_id,
                    "status": "error",
                    "message": f"Error during fetch and analysis: {str(e)}",
                }

            # --- Process fetch_result ---
            if not fetch_result:
                await source_progress_callback(
                    COMPLETE, 100, "Processing complete, but no new content found"
                )
                return {
                    "source_id": source_id,
                    "status": "success",
                    "message": "No new content found",
                    "items_saved": 0,
                }

            for result_item in fetch_result:
                result_item["source_name"] = source_name
                result_item["category_name"] = category_name
                result_item["source_id"] = source_id
                result_item["category_id"] = category_id

            await source_progress_callback(
                SAVING,
                95,
                f"Saving {len(fetch_result)} news items...",
                len(fetch_result),
            )

            saved_count, skipped_count = await news_repo.add_batch(
                fetch_result, user_id
            )

            # --- Record History ONLY if saved_count > 0 ---
            if saved_count > 0:
                await fetch_history_repo.record_completion(
                    user_id=user_id,
                    source_id=source_id,
                    items_saved_this_run=saved_count,
                    task_group_id=task_group_id,
                )

            success_message = (
                "Successfully processed and saved 0 news items, no valid content found or content already exists"
                if saved_count == 0
                else f"Successfully processed and saved {saved_count} news items, skipped {skipped_count} news items"
            )

            await source_progress_callback(
                COMPLETE,
                100,
                success_message,
                saved_count,
            )

            logger.info(
                f"[PID:{pid}] Task {task.request.id}: Source {source_id}: Successfully processed and saved {saved_count} items."
            )

            return {
                "source_id": source_id,
                "status": "success",
                "items_saved": saved_count,
                "items_skipped": skipped_count,
                "message": f"Successfully processed {saved_count} news items",
            }

        except Exception as e:
            logger.exception(
                f"[PID:{pid}] Task {task.request.id}: Source {source_id}: Unhandled error during concurrent processing: {e}"
            )

            try:
                await source_progress_callback(
                    ERROR, 100, f"Internal processing error: {str(e)}"
                )
            except Exception as cb_e:
                logger.error(
                    f"[PID:{pid}] Task {task.request.id}: Source {source_id}: Failed to update error state via callback: {cb_e}"
                )
            return {
                "source_id": source_id,
                "status": "error",
                "progress": 100,
                "message": f"Error processing source {source_details['source_name']}: {str(e)}",
            }


async def _get_user_llm_pool(
    user_id: int, api_key_repo: ApiKeyRepository
) -> Optional[LLMClientPool]:
    """
    Fetches user's API key configuration and instantiates an AsyncLLMClient.
    Returns None if no valid key is found.
    (Moved outside the main processing function for clarity)
    """
    # This repo instance uses the connection from the current task's context
    api_keys_data = await api_key_repo.get_all(user_id)

    if not api_keys_data:
        logger.warning(f"No API keys found for user {user_id}.")
        return None

    for key_data in api_keys_data:
        try:
            api_key = ApiKey.model_validate(dict(key_data))
            logger.info(f"Using API key ID {api_key.id} for user {user_id}")
            return LLMClientPool(
                pool_size=MAX_CONCURRENT_SOURCES,  # Match the semaphore limit
                base_url=api_key.base_url,
                api_key=api_key.api_key,
                model=api_key.model,
                context=api_key.context,
                max_output_tokens=api_key.max_output_tokens,
            )
        except Exception as e:
            logger.error(
                f"Failed to validate or instantiate LLM client for API key data: {key_data}. Error: {e}",
                exc_info=True,
            )
            continue

    logger.warning(f"No valid API key configuration found for user {user_id}.")
    return None


# --- Celery Task Definition ---
@shared_task(bind=True, name="process_single_batch_task")
def process_single_batch_task(
    self, source_ids: List[int], user_id: int, task_group_id: str
):
    """
    Celery task to process a single batch of news source IDs for a specific user
    within a larger task group.
    Initializes dependencies and runs the async batch processing logic.

    Args:
        self: Celery task instance (injected by bind=True)
        source_ids: List of IDs of the news sources to process in this batch
        user_id: ID of the user who owns these sources
        task_group_id: The ID of the overall task group this batch belongs to

    Returns:
        Dict with summary of results for this batch
    """
    pid = os.getpid()
    logger.info(
        f"[PID:{pid}] Received single batch task {self.request.id} for source IDs: {source_ids} (User: {user_id}, Group: {task_group_id})"
    )

    try:

        result = asyncio.run(
            _run_batch_processing(
                task=self,
                source_ids=source_ids,
                user_id=user_id,
                task_group_id=task_group_id,
            )
        )

        return result
    except Exception as e:
        # Error logging and sending the "batch_task_failed" event via Redis Pub/Sub
        # are handled within _run_batch_processing.
        # We just need to ensure the exception propagates to Celery
        # so it marks this specific task as FAILED.
        logger.exception(
            f"[PID:{pid}] Single batch task {self.request.id} (Group: {task_group_id}) failed ultimately: {e}"
        )
        # Re-raise so Celery marks this task as FAILED
        raise


@shared_task(name="finalize_news_fetch_group")
def finalize_news_fetch_group(results, task_group_id: str, user_id: int):
    """
    Chord callback task that runs after all batch tasks complete.
    Aggregates results from all batches and sends the final completion event.

    Args:
        results: List of dictionaries returned by each batch task
        task_group_id: The ID of the overall task group
        user_id: ID of the user who owns the sources

    Returns:
        Dictionary with summary of overall task group results
    """
    pid = os.getpid()
    logger.info(
        f"[PID:{pid}] Executing chord callback for task_group_id: {task_group_id}, user_id: {user_id}"
    )

    total_batches = len(results)
    total_processed_sources = 0
    total_successful_sources = 0
    total_failed_sources = 0
    batch_statuses = []

    for batch_result in results:

        if not isinstance(batch_result, dict):
            logger.warning(
                f"[PID:{pid}] Invalid batch result in task_group {task_group_id}: {batch_result}"
            )
            continue

        total_processed_sources += batch_result.get("processed_sources_count", 0)
        total_successful_sources += batch_result.get("successful_sources_count", 0)
        total_failed_sources += batch_result.get("failed_sources_count", 0)
        batch_statuses.append(batch_result.get("status", "UNKNOWN"))

    overall_status = "FAILURE"
    if all(status == "SUCCESS" for status in batch_statuses):
        overall_status = "SUCCESS"
    elif any(
        status == "SUCCESS" or status == "COMPLETED_WITH_ERRORS"
        for status in batch_statuses
    ):
        overall_status = "PARTIAL_SUCCESS"

    final_message_data = {
        "event": "overall_batch_completed",
        "task_group_id": task_group_id,
        "status": overall_status,
        # Removed successful, failed, and saved keys
    }

    try:
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        redis_client = sync_redis.Redis.from_url(redis_url, decode_responses=True)
        channel = f"task_progress:{task_group_id}"

        json_message = json.dumps(final_message_data)
        redis_client.publish(channel, json_message)

        logger.info(
            f"[PID:{pid}] Published overall completion message to Redis channel {channel} for task_group_id: {task_group_id}"
        )

        redis_client.close()
    except Exception as e:
        logger.exception(
            f"[PID:{pid}] Failed to publish overall completion message to Redis for task_group_id: {task_group_id}: {e}"
        )

    return {
        "task_group_id": task_group_id,
        "overall_status": overall_status,
        "total_batches": total_batches,
        "message": f"Task group {task_group_id} completed with status: {overall_status}",
    }
