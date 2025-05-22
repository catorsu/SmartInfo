"""
Router for task management and monitoring endpoints.
Provides WebSocket connection for real-time task progress updates.
"""

import logging
import asyncio
import json
from starlette.websockets import WebSocketState
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path, Query, Depends
from celery.result import AsyncResult
from typing import Optional
import redis.asyncio as redis

from core.ws_manager import ws_manager
from core.security import decode_access_token
from db.repositories.user_repository import UserRepository
from api.dependencies.dependencies import get_user_repository, get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


async def redis_message_listener(
    websocket: WebSocket, pubsub: redis.client.PubSub, task_group_id: str
):
    """
    Continuously listen for messages from Redis PubSub channel and forward them to WebSocket clients.

    Args:
        websocket: The WebSocket connection object
        pubsub: Redis PubSub instance already subscribed to the channel
        task_group_id: Task group ID for logging and identifying the connection
    """
    try:
        while True:
            # Wait for messages with a timeout to prevent blocking forever
            message = await pubsub.get_message(
                timeout=1.0
            )  # This timeout allows the loop to iterate

            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info(
                    f"WebSocket for {task_group_id} is no longer connected. Exiting listener loop."
                )
                break

            if message is not None and message["type"] == "message":
                try:
                    update_data = json.loads(message["data"])

                    if websocket.client_state == WebSocketState.CONNECTED:
                        await ws_manager.send_update(task_group_id, update_data)
                    else:
                        # This case might be redundant due to the check at the start of the loop,
                        # but kept for safety if state changes between get_message and send_update.
                        logger.warning(
                            f"WebSocket for {task_group_id} disconnected before sending update: {update_data.get('event')}"
                        )
                        break  # Exit the loop if WebSocket is disconnected

                    # Cleanup task group data after sending the final message
                    if update_data.get("event") == "overall_batch_completed":
                        logger.info(
                            f"Overall completion message received for {task_group_id}. Cleaning up metadata and listener."
                        )
                        ws_manager.cleanup_task_group_data(task_group_id)
                        break  # Exit the listener loop as the task group is complete

                except json.JSONDecodeError:
                    logger.error(
                        f"Failed to decode JSON message from Redis for {task_group_id}: {message['data']}"
                    )
                except Exception as send_err:
                    logger.error(
                        f"Error sending WebSocket update for {task_group_id}: {send_err}",
                        exc_info=True,
                    )

            # No need for aggressive asyncio.sleep(0.01) here as get_message has a timeout.
            # If get_message returns None (timeout), the loop continues and checks websocket state.
            # A small sleep can still be useful to prevent a tight loop if get_message always times out quickly
            # and the websocket is still connected, but 1.0s timeout on get_message is the main pacer.
            # await asyncio.sleep(0.1) # Optional: if get_message timeout is very short.

    except asyncio.CancelledError:
        logger.info(f"Redis listener for {task_group_id} was cancelled.")
    except redis.RedisError as redis_err:
        logger.error(
            f"Redis error in listener for {task_group_id}: {redis_err}", exc_info=True
        )
        # Loop will terminate due to exception
    except Exception as e:
        logger.exception(f"Unexpected error in Redis listener for {task_group_id}: {e}")
        # Loop will terminate due to exception
    finally:
        logger.info(f"Exiting Redis listener loop for {task_group_id}.")


@router.websocket("/ws/tasks/group/{task_group_id}")
async def websocket_task_group_endpoint(
    websocket: WebSocket,
    task_group_id: str = Path(..., description="Task group ID to monitor"),
    token: Optional[str] = Query(
        None, description="JWT access token for authentication"
    ),
):
    """
    WebSocket endpoint for monitoring task group progress in real-time.

    Clients connect to this endpoint with a task_group_id and receive
    progress updates for all tasks within that group via Redis Pub/Sub.

    Args:
        websocket: The WebSocket connection
        task_group_id: Task group ID to monitor
        token: JWT access token for authentication
    """
    pubsub = None
    listener_task = None
    channel_name = f"task_progress:{task_group_id}"

    try:

        await websocket.accept()

        # Get dependencies manually since FastAPI's dependency injection might
        # not handle WebSocket context correctly
        user_repo = await get_user_repository()

        app = websocket.scope["app"]
        if not hasattr(app.state, "redis_client"):
            logger.error("Redis client not available in app state")
            await websocket.send_json(
                {"event": "error", "message": "Redis client not available"}
            )
            await websocket.close(code=1011, reason="Internal server error")
            return

        redis_client = app.state.redis_client

        if not token:
            logger.warning(
                f"WebSocket connection attempt without token for task_group_id: {task_group_id}"
            )
            await websocket.close(code=4001, reason="Authentication required")
            return

        payload = decode_access_token(token)
        if not payload:
            logger.warning(
                f"WebSocket connection attempt with invalid token for task_group_id: {task_group_id}"
            )
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

        user_id = payload.get("sub")
        if not user_id:
            logger.warning(
                f"WebSocket connection attempt with token missing user ID for task_group_id: {task_group_id}"
            )
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

        user = await user_repo.get_user_by_id(int(user_id))
        if not user:
            logger.warning(
                f"WebSocket connection attempt with non-existent user ID: {user_id} for task_group_id: {task_group_id}"
            )
            await websocket.close(code=4001, reason="User not found")
            return

        task_group_metadata = ws_manager.get_task_group_metadata(
            task_group_id
        )  # Use new ws_manager method
        if not task_group_metadata:
            logger.warning(
                f"No task group metadata found for task_group_id: {task_group_id}"
            )
            await websocket.send_json(
                {
                    "event": "error",
                    "task_group_id": task_group_id,
                    "message": "No task group found for the specified ID.",
                }
            )
            await websocket.close(code=4004, reason="Task group not found")
            return

        group_user_id = task_group_metadata.get("user_id")
        if group_user_id != int(user_id):
            logger.warning(
                f"Unauthorized WebSocket access attempt: User {user_id} tried to access task group for user {group_user_id} (task_group_id: {task_group_id})"
            )
            await websocket.close(code=4003, reason="Unauthorized access to task group")
            return

        await ws_manager.connect(websocket, task_group_id)
        logger.info(
            f"WebSocket connection established for task_group_id: {task_group_id}, user_id: {user_id}"
        )

        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to Redis channel: {channel_name}")

        listener_task = asyncio.create_task(
            redis_message_listener(websocket, pubsub, task_group_id)
        )
        logger.info(f"Started Redis listener task for {task_group_id}")

        # listener_task is created before this block
        if listener_task:
            await listener_task  # Wait for the listener to complete or be cancelled
        else:
            # This case should ideally not occur if setup logic is correct
            logger.error(
                f"Listener task was not properly created for {task_group_id}. Closing WebSocket."
            )
            await websocket.close(
                code=1011, reason="Internal error: Listener task setup failed."
            )

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket client disconnected explicitly for task_group_id: {task_group_id}. Listener will be cancelled in finally."
        )
        # The listener_task should be cancelled in the finally block.
    except asyncio.CancelledError:
        logger.info(
            f"WebSocket endpoint task for task_group_id {task_group_id} was cancelled (e.g., server shutting down)."
        )
        # The listener_task should be cancelled in the finally block.
    except Exception as e:
        logger.error(
            f"Unhandled exception in websocket_task_group_endpoint for {task_group_id}: {e}",
            exc_info=True,
        )
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(
                    {
                        "event": "error",
                        "task_group_id": task_group_id,
                        "message": f"Internal server error: {str(e)}",
                    }
                )
        except Exception:
            pass  # Ignore errors sending error message during an existing error condition

    finally:
        logger.warning(
            f"Executing finally block for websocket_task_group_endpoint, task_group_id: {task_group_id}. Cleaning up connection."
        )

        # 1. Cancel the listener task first. This signals intent to stop.
        if listener_task and not listener_task.done():
            logger.info(
                f"Cancelling listener_task for {task_group_id} in endpoint finally."
            )
            listener_task.cancel()

        # 2. Close pubsub. This should help unblock get_message if it's waiting.
        if pubsub:
            try:
                logger.info(
                    f"Attempting to unsubscribe and close pubsub for {task_group_id} in endpoint finally."
                )
                try:
                    await pubsub.unsubscribe(channel_name)
                except Exception as unsub_e:
                    logger.warning(
                        f"Error during pubsub unsubscribe for {task_group_id}: {unsub_e}",
                        exc_info=True,
                    )

                await pubsub.close()
                logger.info(f"PubSub for {task_group_id} closed in endpoint finally.")
            except Exception as e:
                logger.error(
                    f"Error closing Redis PubSub for {task_group_id} in endpoint finally: {e}",
                    exc_info=True,
                )

        # 3. Await the listener task with a timeout.
        if listener_task and not listener_task.done():
            logger.info(
                f"Awaiting listener_task completion for {task_group_id} with timeout in endpoint finally."
            )
            try:
                await asyncio.wait_for(listener_task, timeout=5.0)
                logger.info(
                    f"Listener task for {task_group_id} completed after cancellation/pubsub close."
                )
            except asyncio.CancelledError:
                logger.info(
                    f"Redis listener task for {task_group_id} was successfully cancelled (caught in endpoint finally)."
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout waiting for listener task {task_group_id} to terminate in endpoint finally."
                )
            except Exception as e:
                logger.error(
                    f"Error during await of listener_task for {task_group_id} in endpoint finally: {e}",
                    exc_info=True,
                )
        elif listener_task and listener_task.done():
            logger.info(
                f"Listener task for {task_group_id} was already done when endpoint finally block ran."
            )

        # 4. Disconnect from ws_manager
        await ws_manager.disconnect(websocket, task_group_id)
        logger.info(
            f"WebSocket (client: {websocket.client}) disconnected from ws_manager for {task_group_id} in endpoint finally."
        )

        # 5. Ensure metadata cleanup (idempotent)
        # This is important if the 'overall_batch_completed' message wasn't processed by the listener
        # or if the WebSocket disconnected prematurely.
        ws_manager.cleanup_task_group_data(task_group_id)  # Already logs internally
        logger.info(
            f"Ensured cleanup of task group metadata for {task_group_id} in endpoint finally."
        )
