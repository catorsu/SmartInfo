"""
Celery Application Configuration
Configures Celery to use Redis as both message broker and result backend.
Used for background task processing of news fetching and analysis.
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
logger = logging.getLogger(__name__)


BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
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
