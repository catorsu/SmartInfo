"""
WebSocket connection manager for real-time progress updates.
Manages active WebSocket connections for task groups and handles message broadcasting.
"""

import logging
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for task progress updates.
    Maps task_group_ids to active WebSocket connections.
    Handles connection, disconnection, and broadcasting of progress updates.
    """

    def __init__(self):
        """Initialize an empty connection manager."""

        self.active_connections: Dict[str, Set[WebSocket]] = {}

        self.task_group_metadata: Dict[str, Dict[str, Any]] = {}  # Renamed task_data
        logger.info("WebSocket ConnectionManager initialized")

    async def connect(self, websocket: WebSocket, task_group_id: str):
        """
        Accept a new WebSocket connection and associate it with a task_group_id.

        Args:
            websocket: The WebSocket connection to accept and track
            task_group_id: Identifier for the task group this connection is monitoring
        """

        if task_group_id not in self.active_connections:
            self.active_connections[task_group_id] = set()

        self.active_connections[task_group_id].add(websocket)
        logger.info(
            f"Client connected to task_group_id: {task_group_id}, active connections: {len(self.active_connections[task_group_id])}"
        )

    async def disconnect(self, websocket: WebSocket, task_group_id: str):
        """
        Remove a WebSocket connection from the tracked connections.

        Args:
            websocket: The WebSocket connection to remove
            task_group_id: The task group ID this connection was monitoring
        """

        if task_group_id in self.active_connections:
            try:
                self.active_connections[task_group_id].remove(websocket)
                logger.info(
                    f"Client disconnected from task_group_id: {task_group_id}, remaining connections: {len(self.active_connections[task_group_id])}"
                )

                if not self.active_connections[task_group_id]:
                    del self.active_connections[task_group_id]
                    logger.info(f"Removed empty task_group_id: {task_group_id}")
            except KeyError:

                pass

    async def send_update(self, task_group_id: str, data: Dict[str, Any]):
        """
        Send a progress update to all clients monitoring a specific task group.

        Args:
            task_group_id: The task group ID to broadcast to
            data: Dictionary containing the update data to send
        """
        if task_group_id not in self.active_connections:
            logger.warning(f"No active connections for task_group_id: {task_group_id}")
            return

        disconnected_websockets = set()

        for websocket in set(self.active_connections[task_group_id]):
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending update to WebSocket: {e}")
                disconnected_websockets.add(websocket)

        for websocket in disconnected_websockets:
            await self.disconnect(websocket, task_group_id)

    async def store_task_group_metadata(self, task_group_id: str, data: Dict[str, Any]):
        """
        Store task group metadata associated with a task group.

        Args:
            task_group_id: The task group ID
            data: Dictionary containing metadata (user_id, celery_task_ids, etc.)
        """
        self.task_group_metadata[task_group_id] = data
        logger.info(f"Stored task group metadata for task_group_id: {task_group_id}")

    def get_task_group_metadata(self, task_group_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task group metadata for a task group.

        Args:
            task_group_id: The task group ID

        Returns:
            Dictionary containing task group metadata or None if not found
        """
        return self.task_group_metadata.get(task_group_id)

    def cleanup_task_group_data(self, task_group_id: str):
        """
        Remove task group metadata for a completed task group.

        Args:
            task_group_id: The task group ID to clean up
        """
        if task_group_id in self.task_group_metadata:
            del self.task_group_metadata[task_group_id]
            logger.info(
                f"Cleaned up task group metadata for task_group_id: {task_group_id}"
            )


ws_manager = ConnectionManager()
