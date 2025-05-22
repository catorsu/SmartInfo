"""Standardized step codes for news fetching and processing tasks.

This module defines integer constants representing distinct stages in the
news fetching and analysis workflow. These codes are primarily used for
progress reporting, often sent via mechanisms like Redis Pub/Sub or WebSockets,
to provide a concise and consistent way to communicate task status to clients
or other services.

Using integer codes can be more bandwidth-efficient than sending full string
descriptions for each update, especially in high-frequency update scenarios.
The client-side application is expected to map these codes to user-friendly
status messages or UI elements.
"""

# Indicates the task is initializing, setting up resources, or preparing data.
PREPARING = 1

# Indicates the task is actively crawling a website or fetching initial content.
CRAWLING = 2

# Indicates the task is extracting links from the fetched content for further processing.
EXTRACTING_LINKS = 3

# Indicates the task is analyzing content, often involving LLM processing or data extraction.
ANALYZING = 4

# Indicates the task is saving processed data to the database or other persistent storage.
SAVING = 5

# Indicates the task or a specific sub-step has completed successfully.
COMPLETE = 6

# Indicates an error occurred during the task or a specific sub-step.
ERROR = 7

# Indicates that the processing for a specific item (e.g., a news source) was skipped.
# This could be due to various reasons like the source not being found, already processed,
# or not meeting certain criteria.
SKIPPED = 8
