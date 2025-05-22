"""Celery tasks for asynchronous news fetching, processing, and analysis.

This module defines Celery tasks responsible for handling the background
processing of news sources and articles. It orchestrates the workflow involving
fetching data from URLs, extracting content using LLMs, analyzing articles,
saving them to the database, and reporting progress through a Redis Pub/Sub
mechanism.

Key Tasks:
    process_single_batch_task: Processes a batch of news sources concurrently.
    finalize_news_fetch_group: A Celery chord callback that finalizes the
                               overall news fetching operation for a task group.
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, List, Union, Callable, Awaitable
import os
import redis.asyncio as redis
import redis as sync_redis  # For synchronous operations like in chord callback

from celery import shared_task, Task

from core.llm.client import AsyncLLMClient  # Changed from LLMClientPool
from db.repositories import (
    NewsRepository,
    NewsSourceRepository,
    ApiKeyRepository,
    FetchHistoryRepository,
)
from models import ApiKey  # Pydantic model for API Key data

from core.workflow.news_fetch import fetch_news  # Core news fetching logic
from db.connection import init_db_connection, DatabaseConnectionManager

# from core.ws_manager import ws_manager # WebSocket manager, if direct updates were needed

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

# Maximum number of news sources to process concurrently within a single Celery task worker.
# This helps manage resource utilization (CPU, network, LLM API rate limits).
MAX_CONCURRENT_SOURCES = 3


async def _run_batch_processing(
    task: Task,
    source_ids: List[int],
    user_id: int,
    task_group_id: str,
) -> Dict[str, Any]:
    """Manages the asynchronous processing of a batch of news sources.

    This function is the core asynchronous logic executed within the
    `process_single_batch_task` Celery task. It initializes database connections,
    repositories, and an LLM client. It then processes a list of news
    sources concurrently, using a semaphore to limit concurrency. Progress
    updates and error notifications for each source and the batch itself are
    published to a Redis channel specific to the `task_group_id`.

    Args:
        task (celery.Task): The Celery task instance (self).
        source_ids (List[int]): A list of news source IDs to be processed in this batch.
        user_id (int): The ID of the user who owns these news sources.
        task_group_id (str): A unique identifier for the overall task group this
                             batch belongs to, used for Redis Pub/Sub communication.

    Returns:
        Dict[str, Any]: A dictionary summarizing the batch processing results,
                        including status, counts of processed, successful, and
                        failed sources, and any relevant messages.

    Raises:
        Exception: Propagates exceptions from underlying operations, particularly
                   if critical setup like LLM client initialization fails, to ensure
                   the Celery task is marked as FAILED.

    Side Effects:
        - Initializes and closes database connections.
        - Retrieves LLM client configuration.
        - Publishes multiple messages to a Redis Pub/Sub channel
          (e.g., `task_progress:{task_group_id}`) for:
            - Individual source progress updates.
            - Batch completion or failure notifications.
        - Potentially modifies the database by saving news articles and fetch history
          (delegated to `_process_single_source_concurrently`).
        - Logs extensively to track progress and errors.
    """
    pid = os.getpid()
    db_manager: Optional[DatabaseConnectionManager] = None
    llm_client: Optional[AsyncLLMClient] = None  # Changed from llm_pool
    news_repo: Optional[NewsRepository] = None
    source_repo: Optional[NewsSourceRepository] = None
    api_key_repo: Optional[ApiKeyRepository] = None
    fetch_history_repo: Optional[FetchHistoryRepository] = None
    redis_pubsub_client: Optional[redis.Redis] = None

    async def progress_callback(
        source_id: int,
        source_name: str,
        step: Union[int, str],
        progress: float,
        details: str = "",
        items_count: int = 0,
    ) -> None:
        """Publishes progress updates for a single source to Redis.

        Args:
            source_id (int): The ID of the news source.
            source_name (str): The name of the news source (for logging).
            step (Union[int, str]): The current processing step code (e.g., CRAWLING, COMPLETE).
            progress (float): The progress percentage (0-100).
            details (str, optional): Additional details about the current step. Defaults to "".
            items_count (int, optional): For the COMPLETE step, this indicates the number
                                         of items saved for this source. Defaults to 0.
        Side Effects:
            - Publishes a JSON message to the Redis channel `task_progress:{task_group_id}`.
            - Logs the progress update.
        """
        update_data: Dict[str, Any] = {
            "event": "source_progress",
            "source_id": source_id,
            "step": step,
            "progress": round(progress, 1),
        }

        is_complete = step == COMPLETE
        is_error = step == ERROR
        is_skipped = step == SKIPPED

        if is_complete and items_count > 0:
            update_data["items_saved"] = items_count
        elif is_error:
            update_data["error"] = True
            update_data["details"] = details if details else "An error occurred."
        elif is_skipped:
            update_data["skipped"] = True
            update_data["details"] = details if details else "Source skipped."

        channel = f"task_progress:{task_group_id}"
        if redis_pubsub_client:
            try:
                json_message = json.dumps(update_data)
                await redis_pubsub_client.publish(channel, json_message)
                if is_complete or is_error or is_skipped:
                    logger.info(
                        f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) "
                        f"Published final status for source {source_id}: {update_data}"
                    )
                else:
                    logger.debug(
                        f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) "
                        f"Published progress to {channel}: {update_data}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to publish progress update to Redis: {e}", exc_info=True
                )
        else:
            logger.warning("Redis client not available for progress updates.")

        log_level = (
            logging.INFO if (is_complete or is_error or is_skipped) else logging.DEBUG
        )
        logger.log(
            log_level,
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}) "
            f"Progress: Source {source_id} ({source_name}): Step '{step}', "
            f"{progress:.1f}%, Details: '{details}', Items: {items_count}",
        )

    try:
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        redis_pubsub_client = await redis.Redis.from_url(
            redis_url, decode_responses=True
        )
        logger.info(
            f"[PID:{pid}] Task {task.request.id}: Redis Pub/Sub client initialized."
        )

        db_manager = await init_db_connection(
            db_connection_mode="pool",
            min_size=MAX_CONCURRENT_SOURCES,
            max_size=MAX_CONCURRENT_SOURCES,
        )
        logger.info(
            f"[PID:{pid}] Task {task.request.id}: Database connection manager initialized."
        )

        news_repo = NewsRepository()
        source_repo = NewsSourceRepository()
        api_key_repo = ApiKeyRepository()
        fetch_history_repo = FetchHistoryRepository()
        logger.info(f"[PID:{pid}] Task {task.request.id}: Repositories initialized.")

        source_details_to_process: List[Dict[str, Any]] = []
        for source_id_item in source_ids:
            source_record = await source_repo.get_by_id(source_id_item, user_id)
            if not source_record:
                logger.warning(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
                    f"Source ID {source_id_item} not found or not owned by user {user_id}. Skipping."
                )
                await progress_callback(
                    source_id=source_id_item,
                    source_name=f"Unknown (ID:{source_id_item})",
                    step=SKIPPED,
                    progress=100,
                    details=f"Source ID {source_id_item} not found or does not belong to user.",
                )
                continue
            source_details_to_process.append(dict(source_record))

        if not source_details_to_process:
            logger.warning(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
                f"No valid sources to process for user {user_id} in this batch."
            )
            completion_data = {
                "event": "batch_task_completed",
                "task_id": task.request.id,
                "message": "No valid sources to process in this batch.",
                "items_saved": 0,
                "affected_source_ids": source_ids,
            }
            if redis_pubsub_client:
                await redis_pubsub_client.publish(
                    f"task_progress:{task_group_id}", json.dumps(completion_data)
                )
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

        llm_client = await _get_user_llm_client(
            user_id, api_key_repo
        )  # Changed from _get_user_llm_pool
        if llm_client is None:
            err_msg = (
                f"No valid LLM API key found for user {user_id}. Cannot process batch."
            )
            logger.error(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): {err_msg}"
            )
            failure_data = {
                "event": "batch_task_failed",
                "task_id": task.request.id,
                "affected_source_ids": source_ids,
                "message": err_msg,
            }
            if redis_pubsub_client:
                await redis_pubsub_client.publish(
                    f"task_progress:{task_group_id}", json.dumps(failure_data)
                )
            raise Exception(err_msg)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOURCES)
        processing_tasks: List[asyncio.Task] = []
        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
            f"Creating tasks for {len(source_details_to_process)} sources."
        )

        for source_data in source_details_to_process:
            coro = _process_single_source_concurrently(
                semaphore=semaphore,
                task=task,
                source_details=source_data,
                llm_client=llm_client,  # Changed from llm_pool
                news_repo=news_repo,
                fetch_history_repo=fetch_history_repo,
                user_id=user_id,
                progress_callback=progress_callback,
                task_group_id=task_group_id,
            )
            processing_tasks.append(asyncio.create_task(coro))

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
            f"Starting processing of {len(processing_tasks)} source tasks."
        )

        results = []
        for future in asyncio.as_completed(processing_tasks):
            try:
                result = await future
                results.append(result)
            except Exception as e:
                logger.error(
                    f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
                    f"Error in awaited source processing task: {e}",
                    exc_info=True,
                )
                results.append(
                    {
                        "source_id": "unknown_due_to_task_error",
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
        items_saved_total = sum(
            r.get("items_saved", 0)
            for r in results
            if isinstance(r, dict) and r.get("status") == "success"
        )

        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): Batch summary - "
            f"Successful: {successful_count}, Errors: {error_count}, Items Saved: {items_saved_total}"
        )

        batch_completion_event = {
            "event": "batch_task_completed",
            "task_id": task.request.id,
            "message": f"Batch processing completed. Successful: {successful_count}, Errors: {error_count}",
            "items_saved": items_saved_total,
            "affected_source_ids": source_ids,
        }
        if redis_pubsub_client:
            await redis_pubsub_client.publish(
                f"task_progress:{task_group_id}", json.dumps(batch_completion_event)
            )

        return {
            "task_id": task.request.id,
            "task_group_id": task_group_id,
            "status": "SUCCESS" if error_count == 0 else "COMPLETED_WITH_ERRORS",
            "processed_sources_count": len(source_details_to_process),
            "successful_sources_count": successful_count,
            "failed_sources_count": error_count,
            "items_saved_in_batch": items_saved_total,
            "message": f"Batch processing completed. Successful: {successful_count}, Errors: {error_count}",
        }

    except Exception as e:
        logger.exception(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
            f"Unhandled error in _run_batch_processing for user {user_id}: {e}"
        )
        batch_failure_event = {
            "event": "batch_task_failed",
            "task_id": task.request.id,
            "affected_source_ids": source_ids,
            "message": f"Celery task failed: {str(e)}",
        }
        if redis_pubsub_client:
            try:
                await redis_pubsub_client.publish(
                    f"task_progress:{task_group_id}", json.dumps(batch_failure_event)
                )
            except Exception as pub_e:
                logger.error(
                    f"Failed to publish batch failure event to Redis: {pub_e}",
                    exc_info=True,
                )
        raise

    finally:
        if redis_pubsub_client:
            try:
                await redis_pubsub_client.close()
                logger.info(
                    f"[PID:{pid}] Task {task.request.id}: Redis Pub/Sub client closed."
                )
            except Exception as redis_err:
                logger.error(f"Error closing Redis client: {redis_err}", exc_info=True)

        if llm_client:  # Changed from llm_pool
            try:
                await llm_client.close()  # Changed from llm_pool.close()
                logger.info(f"[PID:{pid}] Task {task.request.id}: LLM client closed.")
            except Exception as close_err:
                logger.error(
                    f"Error closing LLM client: {close_err}", exc_info=True
                )  # Changed log message

        if db_manager:
            try:
                await db_manager._cleanup()
                logger.info(
                    f"[PID:{pid}] Task {task.request.id}: Database connections closed via manager."
                )
            except Exception as close_err:
                logger.error(
                    f"Error closing database connections: {close_err}", exc_info=True
                )


async def _process_single_source_concurrently(
    semaphore: asyncio.Semaphore,
    task: Task,
    source_details: Dict[str, Any],
    llm_client: AsyncLLMClient,  # Changed from llm_pool
    news_repo: NewsRepository,
    fetch_history_repo: FetchHistoryRepository,
    user_id: int,
    progress_callback: Callable[
        [int, str, Union[int, str], float, str, int], Awaitable[None]
    ],
    task_group_id: str,
) -> Dict[str, Any]:
    """Processes a single news source, respecting a concurrency semaphore.

    This function fetches news from a given source URL, analyzes content,
    saves new articles to the database, and records fetch history. It uses
    the provided `progress_callback` to report detailed step-by-step progress.

    Args:
        semaphore (asyncio.Semaphore): Semaphore to limit concurrent execution.
        task (Task): The Celery task instance, primarily for logging task ID.
        source_details (Dict[str, Any]): Dictionary containing details of the
                                         news source (id, url, name, category_id, etc.).
        llm_client (AsyncLLMClient): Configured LLM client for content processing. # Changed
        news_repo (NewsRepository): Repository for news article database operations.
        fetch_history_repo (FetchHistoryRepository): Repository for recording fetch history.
        user_id (int): The ID of the user owning this source.
        progress_callback: Async callable to report progress updates.
        task_group_id (str): Identifier for the overall task group (for logging).

    Returns:
        Dict[str, Any]: A dictionary summarizing the processing result for this source,
                        including status, number of items saved/skipped, and messages.

    Side Effects:
        - Acquires and releases the semaphore.
        - Calls `progress_callback` multiple times.
        - Makes external HTTP requests via `fetch_news`.
        - Interacts with LLM APIs via `llm_client`. # Changed
        - Reads from and writes to the database via `news_repo` and `fetch_history_repo`.
        - Logs detailed information about the processing steps and errors.
    """
    pid = os.getpid()
    source_id = source_details["id"]
    url = source_details["url"]
    source_name = source_details["name"]
    category_id = source_details.get("category_id")
    category_name = source_details.get("category_name", "Uncategorized")

    async def _source_progress_update(
        step: Union[int, str],
        progress_val: float,
        details_msg: str = "",
        items_val: int = 0,
    ) -> None:
        await progress_callback(
            source_id, source_name, step, progress_val, details_msg, items_val
        )

    async with semaphore:
        logger.info(
            f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
            f"Acquired semaphore for source {source_id} ({source_name}), User: {user_id}."
        )
        try:
            await _source_progress_update(PREPARING, 5, "Preparing to fetch data...")

            exclude_links = await news_repo.get_all_urls(user_id)
            logger.info(
                f"[PID:{pid}] Task {task.request.id} (Source {source_id}): "
                f"Found {len(exclude_links)} existing URLs for user {user_id}, source {source_id}."
            )

            fetch_result_list: Optional[List[Dict[str, Any]]] = None
            try:
                fetch_result_list = await fetch_news(
                    url=url,
                    llm_client=llm_client,
                    exclude_links=exclude_links,
                    progress_callback=_source_progress_update,
                )
            except Exception as e:
                logger.exception(
                    f"[PID:{pid}] Task {task.request.id} (Source {source_id}): Error during fetch_news: {e}"
                )
                await _source_progress_update(
                    ERROR, 0, f"Fetch and analysis error: {str(e)}"
                )
                return {
                    "source_id": source_id,
                    "status": "error",
                    "message": f"Error during fetch and analysis: {str(e)}",
                    "items_saved": 0,
                }

            if not fetch_result_list:
                await _source_progress_update(
                    COMPLETE, 100, "No new content found or extracted.", 0
                )
                return {
                    "source_id": source_id,
                    "status": "success",
                    "message": "No new content found or extracted.",
                    "items_saved": 0,
                }

            for item in fetch_result_list:
                item["source_name"] = source_name
                item["category_name"] = category_name
                item["source_id"] = source_id
                item["category_id"] = category_id
                item["user_id"] = user_id

            await _source_progress_update(
                SAVING,
                95,
                f"Saving {len(fetch_result_list)} news items...",
                len(fetch_result_list),
            )

            saved_count, skipped_count = await news_repo.add_batch(
                fetch_result_list, user_id
            )

            if saved_count > 0:
                await fetch_history_repo.record_completion(
                    user_id=user_id,
                    source_id=source_id,
                    items_saved_this_run=saved_count,
                    task_group_id=task_group_id,
                )
                final_message = f"Successfully processed. Saved {saved_count} new items, skipped {skipped_count}."
            elif skipped_count > 0:
                final_message = f"Processing complete. No new items saved, {skipped_count} items already existed or were invalid."
            else:
                final_message = "Processing complete. No new content found or all content was filtered out before saving."

            await _source_progress_update(COMPLETE, 100, final_message, saved_count)
            logger.info(
                f"[PID:{pid}] Task {task.request.id} (Source {source_id}): "
                f"Processing complete. Saved: {saved_count}, Skipped: {skipped_count}."
            )
            return {
                "source_id": source_id,
                "status": "success",
                "items_saved": saved_count,
                "items_skipped": skipped_count,
                "message": final_message,
            }

        except Exception as e:
            logger.exception(
                f"[PID:{pid}] Task {task.request.id} (Source {source_id}): "
                f"Unhandled error during concurrent processing: {e}"
            )
            try:
                await _source_progress_update(
                    ERROR, 100, f"Internal processing error: {str(e)}"
                )
            except Exception as cb_e:
                logger.error(
                    f"[PID:{pid}] Task {task.request.id} (Source {source_id}): "
                    f"Failed to update error state via callback: {cb_e}",
                    exc_info=True,
                )
            return {
                "source_id": source_id,
                "status": "error",
                "message": f"Error processing source {source_name}: {str(e)}",
                "items_saved": 0,
            }
        finally:
            logger.info(
                f"[PID:{pid}] Task {task.request.id} (Group: {task_group_id}): "
                f"Released semaphore for source {source_id} ({source_name})."
            )


async def _get_user_llm_client(  # Renamed from _get_user_llm_pool
    user_id: int, api_key_repo: ApiKeyRepository
) -> Optional[AsyncLLMClient]:  # Return type changed
    """Fetches the user's API key configuration and initializes an AsyncLLMClient.

    Retrieves API key details for the given user from the database.
    It uses the first valid API key found to configure and return an
    `AsyncLLMClient`. If no valid keys are found or an error occurs during
    initialization, it returns `None`.

    Args:
        user_id (int): The ID of the user whose API key is to be fetched.
        api_key_repo (ApiKeyRepository): Repository for API key database operations.

    Returns:
        Optional[AsyncLLMClient]: An initialized `AsyncLLMClient` if a valid API key
                                 is found and successfully configured; otherwise, `None`.

    Side Effects:
        - Reads from the database via `api_key_repo`.
        - Logs warnings or errors related to API key fetching and validation.
    """
    api_keys_data = await api_key_repo.get_all(user_id)

    if not api_keys_data:
        logger.warning(f"No API keys found for user {user_id}.")
        return None

    for key_data_row in api_keys_data:
        try:
            api_key = ApiKey.model_validate(dict(key_data_row))
            logger.info(
                f"Using API key ID {api_key.id} (model: {api_key.model}) for user {user_id} to create LLM client."
            )
            # Instantiate AsyncLLMClient directly
            return AsyncLLMClient(
                base_url=str(api_key.base_url),
                api_key=api_key.api_key,
                model=api_key.model,
                context=api_key.context,
                max_output_tokens=api_key.max_output_tokens,
                timeout=600,  # Consistent with previous LLMClientPool default for internal AsyncLLMClients
                max_retries=3,  # Consistent with previous LLMClientPool default for internal AsyncLLMClients
            )
        except Exception as e:
            logger.error(
                f"Failed to validate or instantiate LLM client for API key data "
                f"(ID: {key_data_row.get('id', 'N/A')}, User: {user_id}). Error: {e}",
                exc_info=True,
            )
            continue

    logger.warning(
        f"No *valid* and usable API key configuration found for user {user_id} after checking all entries."
    )
    return None


# --- Celery Task Definitions ---


@shared_task(bind=True, name="process_single_batch_task")
def process_single_batch_task(
    self: Task, source_ids: List[int], user_id: int, task_group_id: str
) -> Dict[str, Any]:
    """Celery task to process a single batch of news source IDs for a user.

    This task orchestrates the asynchronous processing of a list of news sources.
    It sets up the necessary environment (database connections, LLM clients)
    and then runs the `_run_batch_processing` coroutine.

    Args:
        self (celery.Task): The Celery task instance, automatically injected due to `bind=True`.
        source_ids (List[int]): A list of news source IDs to process in this batch.
        user_id (int): The ID of the user who owns these news sources.
        task_group_id (str): A unique identifier for the overall task group this
                             batch belongs to. Used for progress reporting via Redis.

    Returns:
        Dict[str, Any]: A dictionary containing the summary of results for this batch,
                        as returned by `_run_batch_processing`.

    Raises:
        Exception: If `_run_batch_processing` raises an unhandled exception,
                   it will propagate, causing Celery to mark this task instance
                   as FAILED.

    Side Effects:
        - Executes the `_run_batch_processing` coroutine, which has its own side effects
          (database operations, LLM calls, Redis Pub/Sub).
        - Logs the initiation and completion/failure of the batch task.
    """
    pid = os.getpid()
    logger.info(
        f"[PID:{pid}] Celery task {self.request.id} received for 'process_single_batch_task'. "
        f"Source IDs: {source_ids}, User: {user_id}, Group: {task_group_id}"
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
        logger.info(
            f"[PID:{pid}] Celery task {self.request.id} (Group: {task_group_id}) "
            f"completed successfully. Result: {result.get('status')}"
        )
        return result
    except Exception as e:
        logger.exception(
            f"[PID:{pid}] Celery task {self.request.id} (Group: {task_group_id}) "
            f"failed ultimately: {e}"
        )
        raise


@shared_task(name="finalize_news_fetch_group")
def finalize_news_fetch_group(
    results: List[Dict[str, Any]], task_group_id: str, user_id: int
) -> Dict[str, Any]:
    """Celery chord callback task to finalize a news fetch task group.

    This task is executed after all `process_single_batch_task` instances
    in a Celery chord complete. It aggregates results from all batches and
    sends a final completion or failure event for the entire task group
    via Redis Pub/Sub.

    Args:
        results (List[Dict[str, Any]]): A list of dictionaries, where each dictionary
                                       is the return value of a completed
                                       `process_single_batch_task`.
        task_group_id (str): The unique identifier for the overall task group.
        user_id (int): The ID of the user for whom the task group was run.

    Returns:
        Dict[str, Any]: A dictionary summarizing the overall results of the task group.

    Side Effects:
        - Publishes a final JSON message (e.g., `overall_batch_completed` or
          `overall_batch_failed`) to the Redis channel `task_progress:{task_group_id}`.
        - Logs the aggregation process and the final outcome.
    """
    pid = os.getpid()
    logger.info(
        f"[PID:{pid}] Chord callback 'finalize_news_fetch_group' executing for "
        f"task_group_id: {task_group_id}, user_id: {user_id}"
    )

    total_batches = len(results)
    batch_statuses: List[str] = []
    all_batches_succeeded_without_errors = True
    any_batch_had_success = False

    for i, batch_result in enumerate(results):
        if not isinstance(batch_result, dict):
            logger.warning(
                f"[PID:{pid}] Invalid batch result type in task_group {task_group_id} "
                f"at index {i}: {type(batch_result)}. Content: {str(batch_result)[:200]}"
            )
            batch_statuses.append("UNKNOWN_OR_FAILED_TASK")
            all_batches_succeeded_without_errors = False
            continue

        status = batch_result.get("status", "ERROR")
        batch_statuses.append(status)

        if status != "SUCCESS":
            all_batches_succeeded_without_errors = False
        if status == "SUCCESS" or status == "COMPLETED_WITH_ERRORS":
            any_batch_had_success = True

        logger.info(
            f"[PID:{pid}] Group {task_group_id}: Batch {i+1}/{total_batches} "
            f"(Task ID: {batch_result.get('task_id', 'N/A')}) finished with status: {status}. "
            f"Processed: {batch_result.get('processed_sources_count', 0)}, "
            f"Successful: {batch_result.get('successful_sources_count', 0)}, "
            f"Failed: {batch_result.get('failed_sources_count', 0)}, "
            f"Items Saved: {batch_result.get('items_saved_in_batch', 0)}."
        )

    overall_status_summary: str
    if all_batches_succeeded_without_errors:
        overall_status_summary = "SUCCESS"
    elif any_batch_had_success:
        overall_status_summary = "PARTIAL_SUCCESS"
    else:
        overall_status_summary = "FAILURE"

    final_message_data = {
        "event": "overall_task_group_completed",
        "task_group_id": task_group_id,
        "status": overall_status_summary,
        "total_batches_processed": total_batches,
        "batch_statuses": batch_statuses,
    }

    redis_client_sync: Optional[sync_redis.Redis] = None
    try:
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        redis_client_sync = sync_redis.Redis.from_url(redis_url, decode_responses=True)
        channel = f"task_progress:{task_group_id}"
        json_message = json.dumps(final_message_data)

        redis_client_sync.publish(channel, json_message)
        logger.info(
            f"[PID:{pid}] Published overall completion message to Redis channel {channel} "
            f"for task_group_id: {task_group_id}. Status: {overall_status_summary}"
        )
    except Exception as e:
        logger.exception(
            f"[PID:{pid}] Failed to publish overall completion message to Redis "
            f"for task_group_id: {task_group_id}: {e}"
        )
    finally:
        if redis_client_sync:
            try:
                redis_client_sync.close()
            except Exception as rc_e:
                logger.error(
                    f"Error closing synchronous Redis client: {rc_e}", exc_info=True
                )

    final_return_value = {
        "task_group_id": task_group_id,
        "overall_status": overall_status_summary,
        "total_batches_processed": total_batches,
        "batch_statuses": batch_statuses,
        "message": f"Task group {task_group_id} processing finalized with status: {overall_status_summary}.",
    }
    logger.info(
        f"[PID:{pid}] Chord callback for group {task_group_id} finished. Result: {final_return_value}"
    )
    return final_return_value
