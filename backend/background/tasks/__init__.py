"""
Defines the tasks sub-package for SmartInfo's background processing.

This package groups all Celery task definitions. Modules within this package
contain the actual implementation of asynchronous operations managed by Celery,
such as news fetching, data processing, and other long-running jobs.

This `__init__.py` primarily serves to mark the directory as a Python package.
Specific tasks are imported and registered within their respective modules (e.g.,
`news_tasks.py`).
"""
