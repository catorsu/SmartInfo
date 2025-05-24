"""
Manages a pool of asynchronous LLMClient instances for efficient resource reuse.

This module provides the `LLMClientPool` class, which is designed to manage
a collection of `AsyncLLMClient` instances. It handles lazy initialization of
the pool, provides an asynchronous context manager for acquiring and
automatically releasing clients, and ensures graceful shutdown of all managed
client connections. This pooling mechanism is crucial for applications that
make frequent calls to LLM services, as it reduces the overhead of establishing
new connections for each request.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, AsyncGenerator, Any  # Added Any for type hints

from .client import AsyncLLMClient

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek-v3-250324"


class LLMClientPool:
    """
    Manages a pool of `AsyncLLMClient` instances for efficient LLM API interaction.

    This class implements a pool of `AsyncLLMClient` objects to allow for reuse,
    reducing connection overhead. It features lazy initialization, meaning the
    clients are only created when the pool is first accessed. It provides an
    async context manager (`.context()`) for safe acquisition and release of
    clients, and also direct `acquire()` and `release()` methods. The pool ensures
    that all managed clients are properly closed upon calling `close()`.
    """

    def __init__(
        self,
        pool_size: int,
        base_url: str,
        api_key: str,
        context: int = 4096,
        max_output_tokens: int = 2048,
        model: Optional[str] = DEFAULT_MODEL,
        timeout: int = 600,
        max_retries_client: int = 3,
    ) -> None:
        """
        Initializes the configuration for the LLMClientPool. The pool itself is initialized lazily.

        Args:
            pool_size (int): The desired number of `AsyncLLMClient` instances in the pool.
                             Must be a positive integer.
            base_url (str): The base URL for the LLM API (e.g., "https://api.openai.com/v1").
                            This is passed to each created `AsyncLLMClient`.
            api_key (str): The API key for authenticating with the LLM service.
                           This is passed to each created `AsyncLLMClient`.
            context (int): The total context window size (input + output) supported by
                           the LLM, in tokens. Defaults to 4096.
            max_output_tokens (int): The maximum number of tokens to reserve for the LLM's
                                     generation. This is used to calculate `max_input_tokens`.
                                     Defaults to 2048.
            model (Optional[str]): The default LLM model name (e.g., "gpt-3.5-turbo") to be
                                   used by clients from this pool. Defaults to `DEFAULT_MODEL`.
            timeout (int): Default request timeout in seconds for API calls made by clients
                           from this pool. Defaults to 600.
            max_retries_client (int): Default maximum number of retries for transient API
                                      errors, configured within each `AsyncLLMClient`.
                                      Defaults to 3.

        Raises:
            ValueError: If `pool_size` is not a positive integer.

        Side Effects:
            - Initializes configuration attributes (_pool_size, _base_url, etc.).
            - Sets internal state attributes (_clients, _queue, _initialized, _initializing, _init_lock).
            - Logs a warning if `api_key` is not provided (though it's a required arg).
        """
        if pool_size <= 0:
            raise ValueError("Pool size must be a positive integer.")
        if not api_key:  # Should not happen due to type hint but good for runtime check
            logger.warning(
                f"LLMClientPool for {base_url} initialized without an API key."
            )

        self._pool_size = pool_size
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._context = context
        self._max_output_tokens = max_output_tokens
        # Ensure max_input_tokens is not negative if context is smaller than max_output_tokens
        self._max_input_tokens = max(1024, context - max_output_tokens)
        self._timeout = timeout
        self._max_retries_client = max_retries_client

        self._clients: List[AsyncLLMClient] = []
        self._queue: Optional[asyncio.Queue[AsyncLLMClient]] = None

        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._initializing = False
        self._permanently_closed = False

    async def _initialize_pool(self) -> None:
        """
        Initializes the client queue and creates `AsyncLLMClient` instances.

        This method is called internally by `_ensure_initialized` under a lock
        to prevent multiple concurrent initializations. It creates `_pool_size`
        number of `AsyncLLMClient` instances and adds them to an `asyncio.Queue`.

        Raises:
            RuntimeError: If any client instance fails to be created, after attempting
                          to clean up already created clients.

        Side Effects:
            - Sets `self._initializing` to `True` during execution and `False` on completion/error.
            - Creates an `asyncio.Queue` and assigns it to `self._queue`.
            - Populates `self._clients` with the created `AsyncLLMClient` instances.
            - Adds all created clients to `self._queue`.
            - Sets `self._initialized` to `True` upon successful completion.
            - Logs detailed information about the initialization process, including
              success or failure of client creation and overall pool initialization.
            - If client creation fails, attempts to close any successfully created clients
              before re-raising the error.
        """
        if self._initialized or self._initializing:
            return

        self._initializing = True
        logger.info(f"Initializing LLMClientPool (Size: {self._pool_size})...")
        try:
            self._queue = asyncio.Queue(maxsize=self._pool_size)
            clients_created: List[AsyncLLMClient] = []
            for i in range(self._pool_size):
                try:
                    client = AsyncLLMClient(
                        base_url=self._base_url,
                        api_key=self._api_key,
                        model=self._model,
                        context=self._context,
                        max_output_tokens=self._max_output_tokens,
                        timeout=self._timeout,
                        max_retries=self._max_retries_client,
                    )
                    clients_created.append(client)
                    if self._queue is not None:
                        await self._queue.put(client)
                    else:
                        logger.error(
                            "LLMClientPool queue is None during client creation, aborting."
                        )
                        raise RuntimeError(
                            "LLMClientPool queue became None unexpectedly."
                        )
                    logger.debug(
                        f"Created AsyncLLMClient {i+1}/{self._pool_size} and added to pool queue."
                    )
                except Exception as client_error:
                    logger.error(
                        f"Failed to create AsyncLLMClient instance {i+1}: {client_error}",
                        exc_info=True,
                    )
                    for created_client in clients_created:
                        await created_client.close()
                    self._queue = None
                    self._initializing = False
                    self._permanently_closed = False
                    raise RuntimeError(
                        "Failed to create all clients for the pool."
                    ) from client_error

            self._clients = clients_created
            self._initialized = True
            logger.info("LLMClientPool initialized successfully.")

        except Exception as e:
            logger.error(f"LLMClientPool initialization failed: {e}", exc_info=True)
            # Ensure state is reset on failure
            self._clients = []
            self._queue = None
            self._initialized = False
            raise  # Re-raise the exception that caused initialization to fail
        finally:
            self._initializing = False
        self._permanently_closed = False

    async def _ensure_initialized(self) -> None:
        """
        Ensures the pool is initialized, performing lazy initialization if needed.

        This method uses a lock to make the initialization process thread-safe.
        If the pool is already initialized, it returns immediately. Otherwise, it
        acquires the lock and calls `_initialize_pool()`.

        Side Effects:
            - If the pool is not initialized, `_initialize_pool()` is called,
              which has its own side effects (client creation, queue population).
        """
        if self._permanently_closed:
            raise RuntimeError("LLMClientPool has been permanently closed.")
        if self._initialized:
            return

        async with self._init_lock:
            # Double-check after acquiring the lock
            if (
                not self._initialized
            ):  # Also check for permanent closure here again in case state changed while waiting for lock
                if self._permanently_closed:
                    raise RuntimeError("LLMClientPool has been permanently closed.")
                await self._initialize_pool()

    async def acquire(self) -> AsyncLLMClient:
        if self._permanently_closed:
            raise RuntimeError("LLMClientPool has been permanently closed.")
        """
        Acquires an `AsyncLLMClient` instance from the pool.

        This method first ensures the pool is initialized. It then attempts to
        get a client from the internal queue, waiting if the queue is empty.

        Returns:
            AsyncLLMClient: An available `AsyncLLMClient` instance from the pool.

        Raises:
            RuntimeError: If the pool is not initialized or fails to initialize,
                          or if an error occurs while getting a client from the queue.

        Side Effects:
            - Calls `_ensure_initialized()`.
            - Removes a client from `self._queue`.
            - Logs acquisition details.
        """
        await self._ensure_initialized()

        if not self._queue:  # Check if queue is None (initialization failed)
            logger.error(
                "LLMClientPool queue is not available, likely due to initialization failure."
            )
            raise RuntimeError(
                "LLMClientPool is not initialized or initialization failed."
            )

        logger.debug("Acquiring AsyncLLMClient from pool...")
        try:
            client = await self._queue.get()
            self._queue.task_done()  # Notify queue that the item is processed
            logger.debug(
                f"AsyncLLMClient acquired. Pool availability: {self._queue.qsize()}/{self._pool_size}"
            )
            return client
        except Exception as e:  # Catch any error during queue.get()
            logger.exception("Error acquiring AsyncLLMClient from pool", exc_info=True)
            # This indicates a deeper issue with the queue or pool state.
            raise RuntimeError("Failed to acquire AsyncLLMClient from pool.") from e

    async def release(self, client: AsyncLLMClient) -> None:
        """
        Releases an `AsyncLLMClient` instance back into the pool.

        If the pool is not initialized or the queue is unavailable (e.g., during
        shutdown or due to an error), this method will close the provided client
        instead of returning it to the pool.

        Args:
            client (AsyncLLMClient): The `AsyncLLMClient` instance to release.

        Side Effects:
            - Adds the `client` back to `self._queue` if the pool is healthy.
            - If adding to queue fails or pool is unhealthy, calls `client.close()`.
            - Logs release details or warnings.
        """
        if self._permanently_closed or not self._initialized or not self._queue:
            logger.warning(
                "Attempting to release client to a permanently closed, uninitialized, or errored pool. Closing client instead."
            )
            await client.close()
            return

        try:
            await self._queue.put(client)
            logger.debug(
                f"AsyncLLMClient released back to pool. Pool availability: {self._queue.qsize()}/{self._pool_size}"
            )
        except Exception as e:  # Catch errors during queue.put()
            logger.error(
                f"Failed to release AsyncLLMClient back to pool: {e}. Attempting to close client.",
                exc_info=True,
            )
            # If putting back to queue fails, ensure the client is closed to prevent leaks
            await client.close()

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[AsyncLLMClient, None]:
        """
        Provides an asynchronous context manager for using a client from the pool.

        This is the recommended way to use clients from the pool as it handles
        acquisition and release automatically, ensuring clients are always
        returned to the pool even if errors occur.

        Yields:
            AsyncLLMClient: An `AsyncLLMClient` instance from the pool.

        Side Effects:
            - Calls `self.acquire()` to get a client.
            - Calls `self.release()` in a `finally` block to ensure the client
              is returned to the pool.

        Example:
            ```python
            # llm_pool is an instance of LLMClientPool
            async with llm_pool.context() as client:
                response = await client.get_completion_content(...)
            # client is automatically released here
            ```
        """
        client: Optional[AsyncLLMClient] = None  # Initialize to None
        try:
            client = await self.acquire()
            yield client
        finally:
            if client:  # Ensure client is not None before releasing
                await self.release(client)

    async def close(self) -> None:
        """
        Closes all client connections managed by the pool and resets the pool state.

        This method iterates through all client instances created by the pool and
        attempts to close them asynchronously. It should be called during application
        shutdown to release all resources. This method is idempotent.

        Side Effects:
            - Acquires `self._init_lock` to prevent concurrent modification.
            - Calls `close()` on each `AsyncLLMClient` instance in `self._clients`.
            - Clears `self._clients` list.
            - Sets `self._queue` to `None`.
            - Sets `self._initialized` to `False`.
            - Logs the closing process, including counts of successfully closed
              clients and any errors encountered during closure.
        """
        async with self._init_lock:  # Ensure exclusive access during close
            if not self._initialized:
                logger.info("LLMClientPool already closed or was never initialized.")
                return

            logger.info(
                f"Closing LLMClientPool and {len(self._clients)} client instances..."
            )

            close_tasks = [
                client.close() for client in self._clients if client
            ]  # Ensure client is not None
            results = await asyncio.gather(*close_tasks, return_exceptions=True)

            closed_count = 0
            error_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error closing AsyncLLMClient instance {i+1}: {result}",
                        exc_info=result,  # Log the full traceback of the exception
                    )
                    error_count += 1
                else:
                    closed_count += 1

            logger.info(
                f"LLMClientPool closed. Clients closed: {closed_count}, Errors: {error_count}"
            )

            self._clients.clear()
            self._queue = None
            self._initialized = False  # Mark as not initialized
            self._permanently_closed = True

    async def get_completion_content(self, *args: Any, **kwargs: Any) -> str:
        """
        Convenience method to acquire a client, perform a non-streaming completion, and release the client.

        Args:
            *args (Any): Positional arguments to be passed to `AsyncLLMClient.get_completion_content`.
            **kwargs (Any): Keyword arguments to be passed to `AsyncLLMClient.get_completion_content`.

        Returns:
            str: The completion content from the LLM.

        Side Effects:
            - Acquires and releases a client from the pool.
            - Delegates to `AsyncLLMClient.get_completion_content`.

        Example:
            ```python
            # llm_pool is an instance of LLMClientPool
            messages = [{"role": "user", "content": "Hello?"}]
            response = await llm_pool.get_completion_content(messages=messages)
            ```
        """
        async with self.context() as client:
            return await client.get_completion_content(*args, **kwargs)

    async def stream_completion_content(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Convenience method to acquire a client, perform a streaming completion,
        and release the client upon generator exhaustion or closure.

        Note: The acquired client is held for the entire duration of the stream.
        It is released only when the consuming code finishes iterating through
        the generator or the generator is explicitly closed.

        Args:
            *args (Any): Positional arguments to be passed to `AsyncLLMClient.stream_completion_content`.
            **kwargs (Any): Keyword arguments to be passed to `AsyncLLMClient.stream_completion_content`.

        Yields:
            str: Chunks of the completion content from the LLM.

        Raises:
            Exception: Propagates exceptions from `acquire` or client methods.

        Side Effects:
            - Acquires a client from the pool.
            - Delegates to `AsyncLLMClient.stream_completion_content`.
            - Releases the client when the returned generator is exhausted or closed.

        Example:
            ```python
            # llm_pool is an instance of LLMClientPool
            messages = [{"role": "user", "content": "Tell me a story."}]
            async for chunk in llm_pool.stream_completion_content(messages=messages):
                print(chunk, end="")
            ```
        """
        client: Optional[AsyncLLMClient] = None
        try:
            client = await self.acquire()
            # The client.stream_completion_content itself is an async generator
            async for chunk in client.stream_completion_content(*args, **kwargs):
                yield chunk
        except Exception as e:
            # Log error before potentially releasing client and re-raising
            logger.error(
                "Error during stream_completion_content in pool convenience method.",
                exc_info=True,
            )
            raise e  # Re-raise the original exception
        finally:
            if client:
                await self.release(client)
                logger.debug(
                    "AsyncLLMClient released after stream_completion_content (pool method)."
                )

    def get_pool_size(self) -> int:
        """
        Returns the configured maximum size of the client pool.

        Returns:
            int: The maximum number of clients the pool can hold.
        """
        return self._pool_size

    def get_available_count(self) -> int:
        """
        Returns the number of currently available (idle) clients in the pool's queue.

        If the pool is not initialized, this will return 0.

        Returns:
            int: The number of clients currently in the queue, ready for use.
        """
        if not self._queue:
            return 0
        return self._queue.qsize()

    def is_initialized(self) -> bool:
        """
        Checks if the client pool has been successfully initialized and is not permanently closed.

        Returns:
            bool: `True` if the pool has been initialized and is usable, `False` otherwise.
        """
        return self._initialized and not self._permanently_closed
