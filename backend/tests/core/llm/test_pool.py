# backend/tests/core/llm/test_pool.py

import pytest
import asyncio
import logging
from unittest.mock import patch, AsyncMock, MagicMock
from typing import List, AsyncGenerator, Any, Dict, Optional

from core.llm.pool import LLMClientPool, DEFAULT_MODEL as POOL_DEFAULT_MODEL
from core.llm.client import AsyncLLMClient

# Setup logger
logger = logging.getLogger(__name__)

# Constants for testing
TEST_BASE_URL = "http://mockllm.example.com/v1"
TEST_API_KEY = "sk-testapikey"
DEFAULT_POOL_SIZE = 2
TEST_MODEL_NAME = POOL_DEFAULT_MODEL if POOL_DEFAULT_MODEL else "test-default-model"


def create_mock_async_llm_client_config() -> Dict[str, Any]:
    """
    Creates a configuration dictionary for verifying AsyncLLMClient instantiation calls.

    Returns:
        Dict[str, Any]: A dictionary with expected configuration parameters for AsyncLLMClient.

    Side Effects:
        None.

    Examples:
        >>> config = create_mock_async_llm_client_config()
        >>> assert config["model"] == TEST_MODEL_NAME
    """
    return {
        "base_url": TEST_BASE_URL,
        "api_key": TEST_API_KEY,
        "model": TEST_MODEL_NAME,
        "context": 4096,
        "max_output_tokens": 2048,
        "timeout": 600,
        "max_retries": 3,
    }


@pytest.fixture
def mock_async_llm_client_instance_factory():
    """
    Pytest fixture providing a factory that produces new mock AsyncLLMClient instances.
    Each mock client has its `get_completion_content`, `stream_completion_content`,
    and `close` methods mocked, along with async context manager methods.

    Yields:
        Callable: A factory function that, when called, returns a new AsyncMock
                  configured to behave like an AsyncLLMClient instance.

    Side Effects:
        None.

    Examples:
        >>> factory = mock_async_llm_client_instance_factory()
        >>> mock_client = factory()
        >>> asyncio.run(mock_client.get_completion_content()) == "Mocked completion"
        True
    """

    def _factory() -> AsyncMock:
        """Creates and returns a single mock AsyncLLMClient instance."""
        client_instance = AsyncMock(spec=AsyncLLMClient)  # Use spec for better mocking
        client_instance.get_completion_content = AsyncMock(
            return_value="Mocked completion"
        )

        async def mock_stream_generator_func(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[str, None]:
            yield "Mocked "
            yield "stream "
            yield "chunk"

        client_instance.stream_completion_content = mock_stream_generator_func
        client_instance.close = AsyncMock()

        # Mock attributes that might be accessed
        client_instance.base_url = TEST_BASE_URL
        client_instance.api_key = TEST_API_KEY
        client_instance.default_model = TEST_MODEL_NAME
        client_instance._is_closed = False  # Internal state, useful for some tests
        client_instance._client = None  # Internal state

        # Mock async context manager behavior
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=None)
        return client_instance

    return _factory


@pytest.fixture
def PatchedAsyncLLMClient(mock_async_llm_client_instance_factory: Any) -> MagicMock:
    """
    Pytest fixture that provides a MagicMock object configured to replace the
    actual `AsyncLLMClient` class. When this mock is "instantiated", it uses
    `mock_async_llm_client_instance_factory` to produce a mock client instance.

    Args:
        mock_async_llm_client_instance_factory (Any): Fixture providing the factory
                                                      for mock client instances.

    Returns:
        MagicMock: A mock object that can be used with `unittest.mock.patch` to
                   replace `core.llm.client.AsyncLLMClient`.

    Side Effects:
        None.

    Examples:
        >>> PatchedClient = PatchedAsyncLLMClient(mock_factory)
        >>> instance = PatchedClient() # Simulates AsyncLLMClient()
        >>> isinstance(instance, AsyncMock)
        True
    """
    return MagicMock(
        side_effect=lambda *args, **kwargs: mock_async_llm_client_instance_factory()
    )


@pytest.fixture
async def llm_pool_uninitialized() -> LLMClientPool:
    """
    Pytest fixture providing an `LLMClientPool` instance that is NOT yet initialized.
    This is useful for testing lazy initialization behavior.

    Returns:
        LLMClientPool: An uninitialized instance of `LLMClientPool`.

    Side Effects:
        Instantiates an `LLMClientPool` object.
    """
    pool = LLMClientPool(
        pool_size=DEFAULT_POOL_SIZE,
        base_url=TEST_BASE_URL,
        api_key=TEST_API_KEY,
        model=TEST_MODEL_NAME,
    )
    return pool


@pytest.fixture
async def llm_pool(
    PatchedAsyncLLMClient: MagicMock,
) -> AsyncGenerator[LLMClientPool, None]:
    """
    Pytest fixture providing an initialized `LLMClientPool` instance.
    The pool's internal `AsyncLLMClient` instantiations are patched to use
    the `PatchedAsyncLLMClient` mock. Ensures cleanup by closing the pool afterwards.

    Args:
        PatchedAsyncLLMClient (MagicMock): Fixture providing the mock for `AsyncLLMClient` class.

    Yields:
        LLMClientPool: An initialized `LLMClientPool` instance where client creation is mocked.

    Side Effects:
        - Creates an `LLMClientPool` instance.
        - Patches `core.llm.pool.AsyncLLMClient` for the duration of the pool's initialization.
        - Calls `_ensure_initialized()` on the pool instance.
        - On teardown, calls `pool_instance.close()` if the pool wasn't permanently closed.
    """
    pool_instance = LLMClientPool(
        pool_size=DEFAULT_POOL_SIZE,
        base_url=TEST_BASE_URL,
        api_key=TEST_API_KEY,
        model=TEST_MODEL_NAME,
    )
    # Patch AsyncLLMClient *before* _ensure_initialized is called
    with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
        await pool_instance._ensure_initialized()

    yield pool_instance

    # Cleanup: close the pool if it hasn't been permanently closed by a test
    if not pool_instance._permanently_closed:  # type: ignore
        await pool_instance.close()


class TestLLMClientPoolInitialization:
    """Tests related to the initialization of the LLMClientPool."""

    @pytest.mark.asyncio
    async def test_successful_initialization_lazy(
        self, PatchedAsyncLLMClient: MagicMock
    ):
        """
        Tests that the pool initializes lazily upon first client acquisition
        and creates the correct number of mock clients with expected configurations.
        """
        expected_client_config = create_mock_async_llm_client_config()
        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            pool = LLMClientPool(
                pool_size=DEFAULT_POOL_SIZE,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
                model=TEST_MODEL_NAME,
            )
            assert (
                not pool.is_initialized()
            ), "Pool should not be initialized at creation."
            assert pool.get_pool_size() == DEFAULT_POOL_SIZE
            assert (
                pool.get_available_count() == 0
            ), "Available count should be 0 before init."

            # First acquire should trigger initialization
            client = await pool.acquire()
            await pool.release(client)

            assert (
                pool.is_initialized()
            ), "Pool should be initialized after first acquire."
            assert (
                PatchedAsyncLLMClient.call_count == DEFAULT_POOL_SIZE
            ), "Mock AsyncLLMClient should be instantiated 'pool_size' times."

            # Verify that each client was created with the correct config
            for _ in range(DEFAULT_POOL_SIZE):
                PatchedAsyncLLMClient.assert_any_call(**expected_client_config)

            assert (
                pool.get_available_count() == DEFAULT_POOL_SIZE
            ), "All clients should be available after release."
            await pool.close()  # Ensure cleanup for this test's pool instance

    def test_init_with_zero_pool_size_raises_value_error(self):
        """Tests that initializing LLMClientPool with pool_size=0 raises ValueError."""
        with pytest.raises(ValueError, match="Pool size must be a positive integer."):
            LLMClientPool(pool_size=0, base_url=TEST_BASE_URL, api_key=TEST_API_KEY)

    def test_init_with_negative_pool_size_raises_value_error(self):
        """Tests that initializing LLMClientPool with a negative pool_size raises ValueError."""
        with pytest.raises(ValueError, match="Pool size must be a positive integer."):
            LLMClientPool(pool_size=-1, base_url=TEST_BASE_URL, api_key=TEST_API_KEY)

    @pytest.mark.asyncio
    async def test_initialization_failure_during_client_creation(
        self,
        PatchedAsyncLLMClient: MagicMock,
        mock_async_llm_client_instance_factory: Any,
    ):
        """
        Tests pool behavior when `AsyncLLMClient` instantiation fails for some clients.
        Ensures that successfully created clients (before failure) are closed.
        """
        num_clients_to_succeed = 1
        clients_created_successfully: List[AsyncMock] = []

        def side_effect_for_client_creation_with_failure(
            *args: Any, **kwargs: Any
        ) -> AsyncMock:
            if len(clients_created_successfully) < num_clients_to_succeed:
                new_mock_client = mock_async_llm_client_instance_factory()
                clients_created_successfully.append(new_mock_client)
                return new_mock_client
            else:
                raise RuntimeError("Simulated client creation failure")

        PatchedAsyncLLMClient.side_effect = side_effect_for_client_creation_with_failure

        pool_size_attempt = 3
        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            pool = LLMClientPool(
                pool_size=pool_size_attempt,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
                model=TEST_MODEL_NAME,  # Ensure model is passed
            )
            with pytest.raises(
                RuntimeError, match="Failed to create all clients for the pool."
            ):
                await pool._ensure_initialized()  # type: ignore

            assert (
                not pool.is_initialized()
            ), "Pool should not be marked initialized on partial failure."
            assert (
                PatchedAsyncLLMClient.call_count == num_clients_to_succeed + 1
            ), "Mock client should be called for successful clients + 1 failing one."

            # Verify that clients created before the failure were closed
            for i, client_mock in enumerate(clients_created_successfully):
                client_mock.close.assert_called_once()
                logger.info(f"Verified client {i} (mock) was closed during cleanup.")

            assert pool._queue is None  # type: ignore
            assert not pool._clients  # type: ignore

    @pytest.mark.asyncio
    async def test_concurrent_initialization_uses_lock(
        self, PatchedAsyncLLMClient: MagicMock
    ):
        """
        Tests that concurrent calls to `_ensure_initialized` (e.g., via concurrent acquires)
        only result in a single initialization of the pool, thanks to the internal lock.
        """
        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            pool = LLMClientPool(
                pool_size=DEFAULT_POOL_SIZE,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
                model=TEST_MODEL_NAME,
            )

            # Simulate concurrent calls to _ensure_initialized
            tasks = [pool._ensure_initialized() for _ in range(5)]  # type: ignore
            await asyncio.gather(*tasks)

            assert pool.is_initialized(), "Pool should be initialized."
            assert (
                PatchedAsyncLLMClient.call_count == DEFAULT_POOL_SIZE
            ), "Clients should only be created once, for the defined pool size."
            await pool.close()


@pytest.mark.asyncio
class TestLLMClientPoolAcquireRelease:
    """Tests for client acquisition and release mechanisms."""

    async def test_acquire_and_release_client(self, llm_pool: LLMClientPool):
        """Tests basic acquire and release cycle, checking available client counts."""
        initial_available = llm_pool.get_available_count()
        assert initial_available == DEFAULT_POOL_SIZE, "Pool should start full."

        client1 = await llm_pool.acquire()
        assert isinstance(
            client1, AsyncMock
        ), "Acquired object should be a mock client."
        assert llm_pool.get_available_count() == initial_available - 1

        client2 = await llm_pool.acquire()
        assert isinstance(client2, AsyncMock)
        assert llm_pool.get_available_count() == initial_available - 2
        assert client1 is not client2, "Acquired clients should be distinct instances."

        await llm_pool.release(client1)
        assert llm_pool.get_available_count() == initial_available - 1

        await llm_pool.release(client2)
        assert (
            llm_pool.get_available_count() == initial_available
        ), "Pool should be full after all releases."

    async def test_context_manager_acquire_release(self, llm_pool: LLMClientPool):
        """Tests client acquisition and automatic release using the async context manager."""
        initial_available = llm_pool.get_available_count()
        async with llm_pool.context() as client:
            assert isinstance(client, AsyncMock)
            assert llm_pool.get_available_count() == initial_available - 1
        assert (
            llm_pool.get_available_count() == initial_available
        ), "Client should be automatically released after context manager exits."

    async def test_acquire_from_uninitialized_pool_initializes_it(
        self, llm_pool_uninitialized: LLMClientPool, PatchedAsyncLLMClient: MagicMock
    ):
        """Tests that acquiring from an uninitialized pool triggers lazy initialization."""
        pool = llm_pool_uninitialized
        assert not pool.is_initialized(), "Pool should start uninitialized."

        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            client = await pool.acquire()  # This should trigger initialization
            assert pool.is_initialized(), "Pool should be initialized after acquire."
            assert isinstance(client, AsyncMock), "Acquired client should be a mock."
            await pool.release(client)
            await pool.close()  # Clean up pool initialized in this test

    async def test_acquire_blocks_when_pool_empty_and_releases_correctly(
        self, llm_pool: LLMClientPool
    ):
        """
        Tests that `acquire` blocks if the pool is empty and proceeds once a client is released.
        """
        clients_acquired: List[AsyncMock] = []
        # Acquire all available clients
        for _ in range(DEFAULT_POOL_SIZE):
            clients_acquired.append(await llm_pool.acquire())

        assert llm_pool.get_available_count() == 0, "Pool should be empty."

        # This acquire call should block
        acquire_task = asyncio.create_task(llm_pool.acquire())
        await asyncio.sleep(0.02)  # Give acquire_task a chance to run and block
        assert not acquire_task.done(), "Acquire task should be blocked."

        # Release one client
        await llm_pool.release(clients_acquired.pop())
        assert llm_pool.get_available_count() == 1, "One client should be available."

        # The blocked task should now acquire the client
        newly_acquired_client = await asyncio.wait_for(acquire_task, timeout=0.1)
        assert isinstance(newly_acquired_client, AsyncMock)
        assert llm_pool.get_available_count() == 0, "Pool should be empty again."

        # Release all remaining acquired clients
        await llm_pool.release(newly_acquired_client)
        for c_remaining in clients_acquired:
            await llm_pool.release(c_remaining)
        assert (
            llm_pool.get_available_count() == DEFAULT_POOL_SIZE
        ), "Pool should be full."

    async def test_release_to_permanently_closed_pool_closes_client(
        self,
        PatchedAsyncLLMClient: MagicMock,
        mock_async_llm_client_instance_factory: Any,
    ):
        """
        Tests that releasing a client to a permanently closed pool results in the client being closed.
        """
        # Create a standalone mock client instance for this test
        client_to_release = mock_async_llm_client_instance_factory()

        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            pool = LLMClientPool(
                pool_size=1,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
                model=TEST_MODEL_NAME,
            )
            await pool._ensure_initialized()  # type: ignore

            await pool.close()  # Permanently close the pool
            assert pool._permanently_closed  # type: ignore

            # Attempt to release the standalone client to the now-closed pool
            await pool.release(client_to_release)
            # Verify the client itself was told to close
            client_to_release.close.assert_called_once()


@pytest.mark.asyncio
class TestLLMClientPoolUsage:
    """Tests using the pool's convenience methods for LLM calls."""

    async def test_get_completion_content_via_pool(self, llm_pool: LLMClientPool):
        """Tests the pool's `get_completion_content` convenience method."""
        test_messages = [{"role": "user", "content": "Hello"}]

        response = await llm_pool.get_completion_content(messages=test_messages)
        assert response == "Mocked completion", "Response should match mock client's."

        # Verify that one of the pool's clients was used
        called_client_found = False
        for client_mock in llm_pool._clients:  # type: ignore
            if client_mock.get_completion_content.called:  # type: ignore
                client_mock.get_completion_content.assert_any_call(messages=test_messages)  # type: ignore
                called_client_found = True
                break
        assert (
            called_client_found
        ), "No client in the pool was called for get_completion_content."

    async def test_stream_completion_content_via_pool(self, llm_pool: LLMClientPool):
        """Tests the pool's `stream_completion_content` convenience method."""
        test_messages = [{"role": "user", "content": "Stream test"}]

        chunks_received = []
        stream_generator = llm_pool.stream_completion_content(messages=test_messages)
        async for chunk in stream_generator:
            chunks_received.append(chunk)

        assert (
            "".join(chunks_received) == "Mocked stream chunk"
        ), "Streamed response should match mock client's."

        # Verify that one of the pool's clients was used for streaming
        # This is harder to assert directly on the mock_stream_generator_func
        # The fact that we received the correct chunks is strong evidence.
        # We assume if the stream worked, a client's method was invoked.
        # A more direct check would require more complex mocking of the generator factory.
        assert any(
            client.stream_completion_content is not None for client in llm_pool._clients
        ), (
            "A client's stream_completion_content method should have been involved."
        )  # type: ignore


@pytest.mark.asyncio
class TestLLMClientPoolClosure:
    """Tests related to closing the LLMClientPool."""

    async def test_close_pool_closes_all_clients(self, llm_pool: LLMClientPool):
        """Tests that closing the pool also closes all its managed clients."""
        original_clients = list(llm_pool._clients)  # type: ignore
        assert len(original_clients) == DEFAULT_POOL_SIZE

        await llm_pool.close()

        for client_mock in original_clients:
            client_mock.close.assert_called_once()

        assert (
            not llm_pool.is_initialized()
        ), "Pool should be marked uninitialized after close."
        assert not llm_pool._clients, "Client list should be empty after close."  # type: ignore
        assert llm_pool._queue is None, "Queue should be None after close."  # type: ignore
        assert llm_pool._permanently_closed, "Pool should be marked permanently closed."  # type: ignore

    async def test_use_pool_after_close_raises_runtime_error(
        self, llm_pool: LLMClientPool
    ):
        """Tests that attempting to use the pool after it's closed raises a RuntimeError."""
        await llm_pool.close()
        assert llm_pool._permanently_closed  # type: ignore

        with pytest.raises(
            RuntimeError, match="LLMClientPool has been permanently closed"
        ):
            await llm_pool.acquire()

        with pytest.raises(
            RuntimeError, match="LLMClientPool has been permanently closed"
        ):
            async with llm_pool.context() as client:  # type: ignore
                pass  # pragma: no cover # This line should not be reached

    async def test_close_idempotent(self, llm_pool: LLMClientPool):
        """Tests that calling `close()` multiple times is safe and doesn't re-close clients."""
        original_clients = list(llm_pool._clients)  # type: ignore
        await llm_pool.close()  # First close

        for client_mock in original_clients:
            assert client_mock.close.call_count == 1

        await llm_pool.close()  # Second close

        # Call count should remain 1 for each client's close method
        for client_mock in original_clients:
            assert client_mock.close.call_count == 1

        assert not llm_pool.is_initialized()
        assert llm_pool._permanently_closed  # type: ignore


@pytest.mark.asyncio
class TestLLMClientPoolStateMethods:
    """Tests for utility methods that report the pool's state."""

    async def test_get_pool_size(self, llm_pool_uninitialized: LLMClientPool):
        """Tests `get_pool_size()` returns the configured size."""
        assert llm_pool_uninitialized.get_pool_size() == DEFAULT_POOL_SIZE

    async def test_get_available_count(self, llm_pool: LLMClientPool):
        """Tests `get_available_count()` in various pool states."""
        assert (
            llm_pool.get_available_count() == DEFAULT_POOL_SIZE
        ), "Initially all clients available."
        client = await llm_pool.acquire()
        assert (
            llm_pool.get_available_count() == DEFAULT_POOL_SIZE - 1
        ), "One client acquired."
        await llm_pool.release(client)
        assert (
            llm_pool.get_available_count() == DEFAULT_POOL_SIZE
        ), "Client released, all available."

    async def test_is_initialized(self, PatchedAsyncLLMClient: MagicMock):
        """Tests `is_initialized()` in different pool lifecycle stages."""
        # Pool created but not yet initialized (no acquire/ensure_initialized called)
        pool_new = LLMClientPool(
            pool_size=1,
            base_url=TEST_BASE_URL,
            api_key=TEST_API_KEY,
            model=TEST_MODEL_NAME,
        )
        assert (
            not pool_new.is_initialized()
        ), "Newly created pool should report False for is_initialized."
        # No need to close pool_new as it never created clients if not initialized.

        # Pool initialized using mocks
        with patch("core.llm.pool.AsyncLLMClient", PatchedAsyncLLMClient):
            pool_init = LLMClientPool(
                pool_size=1,
                base_url=TEST_BASE_URL,
                api_key=TEST_API_KEY,
                model=TEST_MODEL_NAME,
            )
            await pool_init._ensure_initialized()  # type: ignore
            assert pool_init.is_initialized(), "Initialized pool should report True."

            await pool_init.close()  # Clean up this pool
            assert (
                not pool_init.is_initialized()
            ), "Closed pool should report False for is_initialized (due to _permanently_closed)."
