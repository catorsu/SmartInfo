"""
Background task processing for SmartInfo.

This package initializes and exports the Celery application instance,
making it available for use by other parts of the application, primarily for
defining and dispatching asynchronous tasks.

Key Components/Exports:
    celery_app (Celery): The configured Celery application instance.
"""

from .celery_app import celery_app

__all__ = ("celery_app",)
