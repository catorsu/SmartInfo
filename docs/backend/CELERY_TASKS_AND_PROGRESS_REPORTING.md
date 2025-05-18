# SmartInfo Backend: Celery Tasks & Progress Reporting

## 1. Introduction

This document describes how SmartInfo utilizes Celery for asynchronous background task processing, with a primary focus on the news fetching and analysis workflow. It also details the real-time progress reporting mechanism that allows the frontend to display updates to the user via WebSockets.

Understanding this system is crucial for developers and AI assistants working on background processes, adding new asynchronous tasks, or debugging issues related to task execution and progress updates.

## 2. Celery Setup (`backend/background/celery_app.py`)

SmartInfo uses Celery to offload long-running operations from the main API request-response cycle.

*   **Celery Application:** Defined in `backend/background/celery_app.py`.
*   **Broker:** Redis is used as the message broker. Connection URL is configured via the `REDIS_URL` environment variable (e.g., `redis://localhost:6379/0`).
*   **Result Backend:** Redis is also used as the result backend. Connection URL is configured via `REDIS_BACKEND_URL` (e.g., `redis://localhost:6379/1`).
*   **Task Discovery:** Tasks are automatically discovered from modules listed in `celery_app.conf.include` (e.g., `background.tasks.news_tasks`).
*   **Serialization:** Tasks and results use JSON serialization.
*   **Key Configurations:**
    *   `task_track_started=True`: Enables tasks to report a 'STARTED' state.
    *   `worker_prefetch_multiplier=1`: Recommended for long-running tasks to prevent workers from buffering too many tasks.

To run a Celery worker:
```bash
cd backend
poetry run celery -A background.celery_app worker --loglevel=info
```

## 3. Key Celery Tasks for News Fetching (`backend/background/tasks/news_tasks.py`)

The primary background workflow for fetching news is orchestrated using Celery tasks.

### 3.1. `process_single_batch_task`
*   **Decorator:** `@shared_task(bind=True, name="process_single_batch_task")`
*   **Purpose:** Processes a single batch of news source IDs for a specific user within a larger task group. This is the main workhorse for fetching and processing content from multiple sources concurrently (within the task's async event loop).
*   **Key Parameters:**
    *   `self` (Celery.Task): The Celery task instance (due to `bind=True`).
    *   `source_ids` (List[int]): A list of news source IDs to process in this specific batch.
    *   `user_id` (int): The ID of the user who owns these sources.
    *   `task_group_id` (str): A unique UUID identifying the overall fetch operation this batch belongs to. Used for progress reporting.
*   **Core Logic:**
    1.  Initializes its own database connection manager, repositories (`NewsRepository`, `NewsSourceRepository`, `ApiKeyRepository`, `FetchHistoryRepository`), and a Redis client for publishing progress.
    2.  Retrieves the user's API key(s) via `ApiKeyRepository` and initializes an `LLMClientPool` (via `_get_user_llm_pool`). If no valid key is found, it publishes a `batch_task_failed` event to Redis and raises an exception, marking the Celery task as `FAILURE`.
    3.  For each `source_id` in its batch:
        *   Verifies source ownership and retrieves its URL.
        *   Calls `core.workflow.news_fetch.fetch_news()` to perform the actual crawling, link extraction, and LLM summarization for that source.
        *   A `progress_callback` function is passed to `fetch_news`, which publishes detailed step-wise progress for *that source* to a Redis channel (see Section 5). These steps use integer codes from `backend/background/tasks/step_codes.py`.
    4.  Saves successfully processed articles to the database using `NewsRepository.add_batch()`.
    5.  Records the number of items saved for each source in the `fetch_history` table using `FetchHistoryRepository.record_completion()`.
    6.  Publishes a `batch_task_completed` event to Redis indicating the outcome of its batch (items saved, affected source IDs).
*   **Return Value:** A dictionary summarizing the batch processing results (e.g., `{"task_id": ..., "status": "SUCCESS", "items_saved_in_batch": 10, ...}`).
*   **Error Handling:** Catches exceptions during individual source processing, reports them via the progress callback (as an `ERROR` step for that source), and attempts to continue with other sources in the batch. Critical failures (like LLM pool initialization) will cause the entire Celery task to fail.

### 3.2. `finalize_news_fetch_group` (Chord Callback)
*   **Decorator:** `@shared_task(name="finalize_news_fetch_group")`
*   **Purpose:** This task acts as the callback in a Celery `chord`. It executes only after all `process_single_batch_task` instances (the "header" tasks) in a given `task_group_id` have completed.
*   **Key Parameters:**
    *   `results` (List[Dict]): A list containing the return values from all the preceding `process_single_batch_task` instances in the chord.
    *   `task_group_id` (str): The unique ID for the overall task group.
    *   `user_id` (int): The ID of the user for whom the fetch was performed.
*   **Core Logic:**
    1.  Aggregates the `results` from all batch tasks to determine an overall status for the `task_group_id` (e.g., `SUCCESS`, `PARTIAL_SUCCESS`, `FAILURE`).
    2.  Publishes a final `overall_batch_completed` event to the Redis channel `task_progress:{task_group_id}`. This message signals the frontend that all processing for this group is finished.
*   **Return Value:** A dictionary summarizing the overall task group results.

## 4. Task Grouping, Batching, and `chord`

When a user initiates a fetch for multiple news sources (e.g., via `POST /api/news/tasks/fetch/batch-group`):

1.  A unique **`task_group_id`** (UUID string) is generated by the API router. This ID links all subsequent operations for this fetch request.
2.  The `ws_manager.store_task_group_metadata()` is called to associate this `task_group_id` with the `user_id` and other initial metadata. This is crucial for authenticating WebSocket connections later.
3.  The list of `source_ids` is divided into smaller batches (size defined by `config.fetch_batch_size`).
4.  A Celery **`chord`** is constructed:
    *   The **header** of the chord consists of a group of `process_single_batch_task` calls, one for each batch of `source_ids`.
    *   The **body** (callback) of the chord is a single call to `finalize_news_fetch_group`.
5.  This `chord` is then applied (`chord(...)(...)`). Celery ensures that `finalize_news_fetch_group` only runs after all `process_single_batch_task` instances in the header have completed.

This batching and chord approach allows for:
*   Controlled parallelism: Processing multiple sources concurrently within each batch task's async loop, and multiple batch tasks concurrently across Celery workers.
*   Resource management: Prevents overwhelming the system or external LLM APIs.
*   Clear finalization: A single point (`finalize_news_fetch_group`) to signal the end of the entire multi-source fetch operation.

## 5. Real-Time Progress Reporting Mechanism

SmartInfo uses a Redis Pub/Sub and WebSocket mechanism for real-time progress updates:

**Step 1: Celery Task Publishes to Redis**
*   Within `process_single_batch_task`, the `progress_callback` function is invoked at various stages of processing a single news source.
*   This callback constructs a JSON message detailing the progress.
*   It then publishes this JSON message to a specific Redis Pub/Sub channel.
    *   **Channel Name:** `task_progress:{task_group_id}` (e.g., `task_progress:abc-123-def-456`)
*   **Key Message Formats (JSON):**
    *   **Source Progress Update:**
        ```json
        {
            "event": "source_progress",
            "source_id": 123, // ID of the news source
            "step": 2,        // Integer code from step_codes.py (e.g., CRAWLING)
            "progress": 25.0, // Percentage completion for this step/source
            // "items_saved": 5, // Only included if step is COMPLETE and items were saved
            // "error": true,    // Only included if step is ERROR
            // "skipped": true   // Only included if step is SKIPPED
        }
        ```
    *   **Batch Task Completion (from `process_single_batch_task`):**
        ```json
        {
            "event": "batch_task_completed",
            "task_id": "celery_task_id_of_batch",
            "message": "Batch processing completed. Successful: X, Errors: Y",
            "items_saved": 15, // Total items saved by this batch
            "affected_source_ids": // Source IDs in this batch
        }
        ```
    *   **Batch Task Failure (from `process_single_batch_task` if critical error):**
        ```json
        {
            "event": "batch_task_failed",
            "task_id": "celery_task_id_of_batch",
            "affected_source_ids":,
            "message": "Celery task failed: No valid LLM API key found..."
        }
        ```
    *   **Overall Group Completion (from `finalize_news_fetch_group`):**
        ```json
        {
            "event": "overall_batch_completed",
            "task_group_id": "abc-123-def-456",
            "status": "SUCCESS" // or "PARTIAL_SUCCESS", "FAILURE"
        }
        ```

**Step 2: WebSocket Endpoint Listens to Redis (`backend/api/routers/tasks.py`)**
*   The frontend connects to the WebSocket endpoint `WS /api/tasks/ws/tasks/group/{task_group_id}`.
*   The endpoint authenticates the user and verifies they own the `task_group_id` by checking metadata stored in `ws_manager`.
*   Upon successful connection, an asynchronous task (`redis_message_listener`) is started.
*   This listener subscribes to the Redis Pub/Sub channel `task_progress:{task_group_id}` using the application's shared Redis client (`app.state.redis_client`).

**Step 3: WebSocket Manager Forwards to Client (`backend/core/ws_manager.py`)**
*   When the `redis_message_listener` receives a message from the subscribed Redis channel:
    *   It parses the JSON data.
    *   It calls `ws_manager.send_update(task_group_id, update_data)`.
    *   The `ws_manager` looks up all active WebSocket connections associated with that `task_group_id` and sends the `update_data` JSON to each connected client.
*   If the `overall_batch_completed` event is received, `ws_manager.cleanup_task_group_data(task_group_id)` is also called by the `redis_message_listener` (or if the WebSocket disconnects prematurely) to remove the stored metadata for that group.

This decouples the Celery workers (which might be on different machines) from direct WebSocket communication, using Redis as an intermediary message bus.

## 6. Role of `ws_manager.py`

The `ConnectionManager` instance (`ws_manager`) in `core/ws_manager.py` plays a vital role:
*   `active_connections`: A dictionary mapping `task_group_id` to a set of active `WebSocket` objects.
*   `task_group_metadata`: A dictionary mapping `task_group_id` to metadata such as `user_id`, `total_sources`. This is used to:
    *   Authenticate WebSocket connection attempts (ensure the connecting user initiated this task group).
    *   Potentially provide initial state or context to a newly connecting WebSocket.
*   `connect()`: Adds a new WebSocket to track for a group.
*   `disconnect()`: Removes a WebSocket. If a group has no more connections, the group entry is removed from `active_connections`.
*   `send_update()`: Broadcasts a JSON message to all WebSockets connected to a specific `task_group_id`.
*   `store_task_group_metadata()` / `get_task_group_metadata()` / `cleanup_task_group_data()`: Manage the lifecycle of metadata associated with a task group.

## 7. Guidelines for Adding New Asynchronous Tasks with Progress

If new asynchronous operations requiring progress reporting are added:

1.  **Define Celery Task(s):** Create new Celery task functions in an appropriate `tasks` module.
2.  **Task Grouping:** If the operation involves multiple sub-steps or items, use a `task_group_id` to link them.
3.  **Progress Publishing:**
    *   The task(s) must acquire a Redis client.
    *   Publish JSON progress messages to a Redis channel named `task_progress:{your_task_group_id}`.
    *   Define clear `event` types and payload structures for your messages. Consider reusing `step_codes.py` if applicable.
4.  **WebSocket Endpoint:**
    *   A new WebSocket endpoint might be needed if the monitoring logic or authentication context is significantly different.
    *   Alternatively, the existing `/ws/tasks/group/{task_group_id}` endpoint could be generalized if the `task_group_id` concept and metadata stored in `ws_manager` are sufficient.
5.  **Frontend Handling:** The frontend needs to be updated to connect to the appropriate WebSocket endpoint and handle the new progress message formats.
6.  **Documentation:** Update this guide and any relevant workflow documents.

This system provides a robust and scalable way to handle background processing and keep users informed of progress in real-time.
