"""Configures and initializes the Celery application for SmartInfo.

This module sets up Celery with Redis as the message broker and result backend.
It defines the core Celery application instance used for managing and executing
asynchronous background tasks, such as news fetching and content analysis.
The configuration includes task serialization, timezone settings, and worker
behavior.

Key Components/Exports:
    celery_app (Celery): The configured Celery application instance.
"""

import os
from celery import Celery
import logging
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("jieba").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# URL for the Celery message broker (Redis).
# Reads from the REDIS_URL environment variable.
BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
# URL for the Celery result backend (Redis).
# Reads from the REDIS_BACKEND_URL environment variable.
BACKEND_URL = os.getenv("REDIS_BACKEND_URL", "redis://127.0.0.1:6379/1")


celery_app = Celery(
    "background",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["background.tasks.news_tasks"],  # Corrected module path
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Prevents worker from fetching too many tasks at once
)


if __name__ == "__main__":
    celery_app.start()
