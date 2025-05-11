"""
LLM Interaction Package.

This package contains modules for interacting with Large Language Models,
including sync and async clients for API communication and a pool for managing
multiple async client instances.
"""

# Import the original factory function for backward compatibility
from .client import LLMClient


from .client import AsyncLLMClient, SyncLLMClient

# Import the pool implementation (now works with AsyncLLMClient)
from .pool import LLMClientPool


__all__ = [
    "LLMClient",  # Factory function (backward compatibility)
    "AsyncLLMClient",  # Async-specific implementation
    "SyncLLMClient",  # Sync-specific implementation
    "LLMClientPool",  # Client pool (works with AsyncLLMClient)
]
