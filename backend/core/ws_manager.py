"""
WebSocket Connection Manager for Real-Time Task Progress Updates.

This module provides a `ConnectionManager` class responsible for managing
active WebSocket connections. It maps task group IDs to sets of WebSocket
clients, allowing for targeted broadcasting of progress updates related to
specific asynchronous task groups (e.g., news fetching batches).
It also handles storing and retrieving metadata associated with these task groups.

Key Components/Exports:
    - ConnectionManager: Class for managing WebSocket connections and task metadata.
    - ws_manager: A global singleton instance of `ConnectionManager`.
"""

import logging
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and associated task group metadata.

    This class facilitates real-time communication by tracking active WebSocket
    connections for different task groups. It allows broadcasting messages
    (e.g., progress updates) to all clients subscribed to a specific task group.
    It also provides a mechanism to store and retrieve metadata related to
    these task groups, such as user ID, Celery task IDs, and overall progress.

    Attributes:
        active_connections (Dict[str, Set[WebSocket]]): A dictionary mapping
            task group IDs (str) to a set of active WebSocket connections
            monitoring that group.
        task_group_metadata (Dict[str, Dict[str, Any]]): A dictionary mapping
            task group IDs (str) to a dictionary of metadata associated with
            that task group (e.g., user_id, total_items, completed_items).
    """

    def __init__(self) -> None:
        """Initializes the ConnectionManager.

        Sets up empty dictionaries for tracking active connections and task
        group metadata.

        Side Effects:
            - Initializes `self.active_connections` and `self.task_group_metadata`.
            - Logs the initialization of the manager.
        """
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.task_group_metadata: Dict[str, Dict[str, Any]] = {}
        logger.info("WebSocket ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket, task_group_id: str) -> None:
        """Accepts and tracks a new WebSocket connection for a task group.

        If the `task_group_id` is new, a new set for connections is created.
        The provided `websocket` is then added to the set for that group.

        Args:
            websocket (WebSocket): The FastAPI WebSocket object representing the
                new client connection.
            task_group_id (str): The identifier of the task group this client
                is subscribing to.

        Side Effects:
            - Adds the `websocket` to `self.active_connections[task_group_id]`.
            - Logs the connection event, including the number of active
              connections for the group.
        """
        if task_group_id not in self.active_connections:
            self.active_connections[task_group_id] = set()

        self.active_connections[task_group_id].add(websocket)
        logger.info(
            f"Client connected to task_group_id: {task_group_id}, "
            f"active connections for this group: {len(self.active_connections[task_group_id])}"
        )

    async def disconnect(self, websocket: WebSocket, task_group_id: str) -> None:
        """Removes a WebSocket connection from tracking.

        If the `task_group_id` exists in `active_connections`, the `websocket`
        is removed from its set. If this leaves the set empty, the
        `task_group_id` entry is deleted from `active_connections`.

        Args:
            websocket (WebSocket): The WebSocket connection to remove.
            task_group_id (str): The task group ID the connection was monitoring.

        Side Effects:
            - Removes `websocket` from `self.active_connections[task_group_id]`.
            - May delete `self.active_connections[task_group_id]` if it becomes empty.
            - Logs the disconnection event and remaining connections for the group.
        """
        if task_group_id in self.active_connections:
            try:
                self.active_connections[task_group_id].remove(websocket)
                logger.info(
                    f"Client disconnected from task_group_id: {task_group_id}, "
                    f"remaining connections for this group: {len(self.active_connections[task_group_id])}"
                )
                # Clean up the entry for the task_group_id if no connections remain.
                if not self.active_connections[task_group_id]:
                    del self.active_connections[task_group_id]
                    logger.info(
                        f"Removed empty task_group_id '{task_group_id}' from active connections."
                    )
            except KeyError:
                # Websocket was not in the set, which can happen if disconnect is called multiple times
                # or if the websocket was never properly added. Log as a warning.
                logger.warning(
                    f"Attempted to disconnect a websocket not found in task_group_id: {task_group_id}."
                )
                pass  # Ignore if websocket not found in the set.

    async def send_update(self, task_group_id: str, data: Dict[str, Any]) -> None:
        """Sends a JSON message to all WebSockets connected to a task group.

        Iterates over all active connections for the given `task_group_id`
        and attempts to send the `data` as a JSON message. If sending to a
        WebSocket fails (e.g., connection closed by client), that WebSocket
        is scheduled for disconnection.

        Args:
            task_group_id (str): The identifier for the task group whose clients
                should receive the update.
            data (Dict[str, Any]): The data payload to send (must be JSON-serializable).

        Side Effects:
            - Sends JSON data over active WebSockets.
            - Logs warnings if no active connections are found for the group.
            - Logs errors if sending data to a WebSocket fails.
            - Calls `self.disconnect()` for WebSockets that error out during send.
        """
        if task_group_id not in self.active_connections:
            logger.warning(
                f"No active connections found for task_group_id: {task_group_id} to send update."
            )
            return

        disconnected_websockets: Set[WebSocket] = set()
        # Iterate over a copy of the set in case `disconnect` modifies it during iteration.
        for websocket in list(self.active_connections[task_group_id]):
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(
                    f"Error sending update to WebSocket for task_group_id {task_group_id}: {e}"
                )
                disconnected_websockets.add(websocket)

        # Clean up disconnected websockets after iteration.
        for ws_to_remove in disconnected_websockets:
            await self.disconnect(ws_to_remove, task_group_id)

    async def store_task_group_metadata(
        self, task_group_id: str, data: Dict[str, Any]
    ) -> None:
        """Stores metadata associated with a specific task group.

        This metadata can include information like the user ID who initiated
        the task group, Celery task IDs involved, total items to process, etc.
        It overwrites any existing metadata for the same `task_group_id`.

        Args:
            task_group_id (str): The unique identifier for the task group.
            data (Dict[str, Any]): A dictionary containing the metadata to store.

        Side Effects:
            - Stores `data` in `self.task_group_metadata[task_group_id]`.
            - Logs the storage event.
        """
        self.task_group_metadata[task_group_id] = data
        logger.info(f"Stored task group metadata for task_group_id: {task_group_id}.")

    def get_task_group_metadata(self, task_group_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves stored metadata for a specific task group.

        Args:
            task_group_id (str): The identifier of the task group whose
                metadata is to be retrieved.

        Returns:
            Optional[Dict[str, Any]]: The metadata dictionary if found for the
                `task_group_id`, otherwise `None`.
        """
        return self.task_group_metadata.get(task_group_id)

    def cleanup_task_group_data(self, task_group_id: str) -> None:
        """Removes stored metadata for a completed or obsolete task group.

        This is typically called when a task group finishes processing or if
        its associated WebSocket connections are all closed and the metadata
        is no longer needed.

        Args:
            task_group_id (str): The identifier of the task group whose
                metadata should be cleaned up.

        Side Effects:
            - Deletes the entry for `task_group_id` from `self.task_group_metadata`
              if it exists.
            - Logs the cleanup event.
        """
        if task_group_id in self.task_group_metadata:
            del self.task_group_metadata[task_group_id]
            logger.info(
                f"Cleaned up task group metadata for task_group_id: {task_group_id}."
            )
        else:
            logger.debug(
                f"No metadata found to cleanup for task_group_id: {task_group_id} (might have been already cleaned)."
            )


# Global instance of the ConnectionManager.
ws_manager = ConnectionManager()
