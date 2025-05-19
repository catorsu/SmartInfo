"""
LLM Interaction Package.

This package contains modules for interacting with Large Language Models,
including sync and async clients for API communication and a pool for managing
multiple async client instances.
"""

from .client import AsyncLLMClient, SyncLLMClient

# Import the pool implementation (now works with AsyncLLMClient)
from .pool import LLMClientPool


__all__ = [
    "AsyncLLMClient",  # Async-specific implementation
    "SyncLLMClient",  # Sync-specific implementation
    "LLMClientPool",  # Client pool (works with AsyncLLMClient)
]
