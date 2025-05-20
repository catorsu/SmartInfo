# backend/tests/core/llm/test_client.py

"""
Integration tests for backend.core.llm.client.py

IMPORTANT:
These tests interact with a live LLM API endpoint.
They require the following environment variables to be set, typically in a .env file
at the project root:
    - TEST_LLM_BASE_URL: The base URL of the LLM API.
    - TEST_LLM_API_KEY: The API key for authentication.
    - TEST_LLM_MODEL_NAME: A valid model name to use for testing (optional for some tests).

These tests can incur API costs and may be slow depending on network and API response times.
Tests are skipped if the required environment variables are not found.
"""

import os
import pytest
import asyncio  # Required for pytest.mark.asyncio even if not directly used in test function
from dotenv import load_dotenv
from typing import List, Dict, AsyncGenerator, Generator

# Load environment variables from .env file if present
load_dotenv()

# Attempt to import client classes
try:
    from core.llm.client import AsyncLLMClient, SyncLLMClient
    from openai import (
        APIError,
    )  # For potential future tests catching specific API errors
except ImportError as e:
    pytest.fail(
        f"Failed to import LLM clients. Ensure PYTHONPATH is set correctly or tests are run from a suitable directory. Error: {e}"
    )


# --- Test Configuration ---
BASE_URL = os.getenv("TEST_LLM_BASE_URL")
API_KEY = os.getenv("TEST_LLM_API_KEY")
MODEL_NAME = os.getenv("TEST_LLM_MODEL_NAME")

# Skip all tests in this module if essential core configuration (URL, Key) is missing
pytestmark = pytest.mark.skipif(
    not (BASE_URL and API_KEY),  # Checks if both are non-None and non-empty strings
    reason="TEST_LLM_BASE_URL or TEST_LLM_API_KEY environment variables not set or empty. These are required for all tests in this module.",
)

# --- Helper Data ---
SIMPLE_MESSAGES: List[Dict[str, str]] = [
    {"role": "user", "content": "Hello! Please respond with the word 'TestResponse'."}
]
# Using a more specific keyword to check in response, though LLM creativity can still vary.
EXPECTED_RESPONSE_KEYWORD = "TestResponse"

# --- Tests for AsyncLLMClient ---


@pytest.mark.asyncio
class TestAsyncLLMClient:
    """Tests for the AsyncLLMClient."""

    async def test_initialization(self):
        """Test successful initialization of AsyncLLMClient."""
        # This test needs BASE_URL, API_KEY, and MODEL_NAME to be set for full validation.
        # Module-level skipif ensures BASE_URL and API_KEY are set.
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it for validating default_model."
            )

        # Assertions act as type guards for Pylance and runtime checks.
        assert BASE_URL  # Ensures it's a non-empty string
        assert API_KEY  # Ensures it's a non-empty string
        assert MODEL_NAME  # Ensures it's a non-empty string

        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        assert client.base_url == BASE_URL
        assert client.api_key == API_KEY
        assert client.default_model == MODEL_NAME
        assert client._client is None  # Client is lazy-loaded
        assert not client._is_closed
        await client.close()  # Ensure cleanup

    async def test_initialization_without_model(self):
        """Test initialization without a default model."""
        # Module-level skipif ensures BASE_URL and API_KEY are set.
        # Assertions act as type guards for Pylance.
        assert BASE_URL  # Ensures it's a non-empty string
        assert API_KEY  # Ensures it's a non-empty string

        client = AsyncLLMClient(
            base_url=BASE_URL, api_key=API_KEY
        )  # model parameter is Optional[str]
        assert client.default_model is None
        await client.close()

    async def test_get_completion_content_success(self):
        """Test successful non-streaming completion."""
        # This test requires MODEL_NAME.
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards and runtime check
        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        async with client:
            response = await client.get_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(response, str)
            assert len(response) > 0
            # assert EXPECTED_RESPONSE_KEYWORD.lower() in response.lower()

    async def test_get_completion_content_no_default_model_error(self):
        """Test ValueError if no model is specified and no default model."""
        assert BASE_URL and API_KEY  # Type guards and runtime check
        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY)  # No default model
        async with client:
            with pytest.raises(ValueError, match="No model specified"):
                await client.get_completion_content(messages=SIMPLE_MESSAGES)

    async def test_get_completion_content_model_override(self):
        """Test non-streaming completion with model override."""
        # This test requires a valid MODEL_NAME to override with.
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it for model override."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards and runtime check
        client = AsyncLLMClient(
            base_url=BASE_URL,
            api_key=API_KEY,
            model="some-other-model-should-be-ignored",
        )
        async with client:
            response = await client.get_completion_content(
                messages=SIMPLE_MESSAGES, model=MODEL_NAME
            )
            assert isinstance(response, str)
            assert len(response) > 0

    async def test_stream_completion_content_success(self):
        """Test successful streaming completion."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards and runtime check
        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        full_response_parts = []
        async with client:
            stream = client.stream_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(stream, AsyncGenerator)
            async for chunk in stream:
                assert isinstance(chunk, str)
                full_response_parts.append(chunk)

        full_response = "".join(full_response_parts)
        assert len(full_response) > 0
        # assert EXPECTED_RESPONSE_KEYWORD.lower() in full_response.lower()

    async def test_stream_completion_content_no_default_model_error(self):
        """Test ValueError for streaming if no model is specified and no default."""
        assert BASE_URL and API_KEY  # Type guards and runtime check
        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY)
        async with client:
            with pytest.raises(ValueError, match="No model specified"):
                async for _ in client.stream_completion_content(
                    messages=SIMPLE_MESSAGES
                ):
                    pass  # pragma: no cover

    async def test_context_manager_usage(self):
        """Test client usage with async context manager."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards and runtime check
        async with AsyncLLMClient(
            base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME
        ) as client:
            assert client._client is not None
            assert not client._is_closed
            response = await client.get_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(response, str)
        assert client._is_closed

    async def test_manual_close(self):
        """Test manual closing of the client."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards and runtime check
        client = AsyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        await client.get_completion_content(messages=SIMPLE_MESSAGES)
        assert client._client is not None
        assert not client._is_closed

        await client.close()
        assert client._is_closed
        assert client._client is None

        await client.close()
        assert client._is_closed

        with pytest.raises(RuntimeError, match="LLMClient instance has been closed."):
            await client.get_completion_content(messages=SIMPLE_MESSAGES)


# --- Tests for SyncLLMClient ---


class TestSyncLLMClient:
    """Tests for the SyncLLMClient."""

    def test_initialization(self):
        """Test successful initialization of SyncLLMClient."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        assert client.base_url == BASE_URL
        assert client.api_key == API_KEY
        assert client.default_model == MODEL_NAME
        assert client._client is None
        assert not client._is_closed
        client.close()

    def test_initialization_without_model(self):
        """Test initialization without a default model."""
        assert BASE_URL and API_KEY  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY)
        assert client.default_model is None
        client.close()

    def test_get_completion_content_success(self):
        """Test successful non-streaming completion."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        with client:
            response = client.get_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(response, str)
            assert len(response) > 0
            # assert EXPECTED_RESPONSE_KEYWORD.lower() in response.lower()

    def test_get_completion_content_no_default_model_error(self):
        """Test ValueError if no model is specified and no default model."""
        assert BASE_URL and API_KEY  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY)
        with client:
            with pytest.raises(ValueError, match="No model specified"):
                client.get_completion_content(messages=SIMPLE_MESSAGES)

    def test_get_completion_content_model_override(self):
        """Test non-streaming completion with model override."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it for model override."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        client = SyncLLMClient(
            base_url=BASE_URL,
            api_key=API_KEY,
            model="some-other-model-should-be-ignored",
        )
        with client:
            response = client.get_completion_content(
                messages=SIMPLE_MESSAGES, model=MODEL_NAME
            )
            assert isinstance(response, str)
            assert len(response) > 0

    def test_stream_completion_content_success(self):
        """Test successful streaming completion."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        full_response_parts = []
        with client:
            stream = client.stream_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(stream, Generator)
            for chunk in stream:
                assert isinstance(chunk, str)
                full_response_parts.append(chunk)

        full_response = "".join(full_response_parts)
        assert len(full_response) > 0
        # assert EXPECTED_RESPONSE_KEYWORD.lower() in full_response.lower()

    def test_stream_completion_content_no_default_model_error(self):
        """Test ValueError for streaming if no model is specified and no default."""
        assert BASE_URL and API_KEY  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY)
        with client:
            with pytest.raises(ValueError, match="No model specified"):
                for _ in client.stream_completion_content(messages=SIMPLE_MESSAGES):
                    pass  # pragma: no cover

    def test_context_manager_usage(self):
        """Test client usage with context manager."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        with SyncLLMClient(
            base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME
        ) as client:
            assert client._client is not None
            assert not client._is_closed
            response = client.get_completion_content(messages=SIMPLE_MESSAGES)
            assert isinstance(response, str)
        assert client._is_closed

    def test_manual_close(self):
        """Test manual closing of the client."""
        if not MODEL_NAME:
            pytest.skip(
                "TEST_LLM_MODEL_NAME environment variable not set. This test requires it."
            )

        assert BASE_URL and API_KEY and MODEL_NAME  # Type guards
        client = SyncLLMClient(base_url=BASE_URL, api_key=API_KEY, model=MODEL_NAME)
        client.get_completion_content(messages=SIMPLE_MESSAGES)
        assert client._client is not None
        assert not client._is_closed

        client.close()
        assert client._is_closed
        assert client._client is None

        client.close()
        assert client._is_closed

        with pytest.raises(RuntimeError, match="LLMClient instance has been closed."):
            client.get_completion_content(messages=SIMPLE_MESSAGES)
