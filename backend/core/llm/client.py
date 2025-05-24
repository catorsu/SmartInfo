"""Manages client connections and interactions with LLM APIs.

This module provides base and concrete implementations for synchronous and
asynchronous clients to communicate with Large Language Models (LLMs) that
adhere to an OpenAI-compatible API interface. It handles API requests for
completions (both streaming and non-streaming), authentication, and basic
error handling.

Key Components/Exports:
    - LLMClientBase: Abstract base class defining the LLM client interface.
    - AsyncLLMClient: Asynchronous client using `openai.AsyncOpenAI`.
    - SyncLLMClient: Synchronous client using `openai.OpenAI`.
"""

import abc
import logging
from builtins import BaseException  # For type hinting in __exit__ / __aexit__
from typing import (
    AsyncGenerator,
    AsyncIterator,
    Coroutine,
    Generator,
    Iterator,
    List,
    Dict,
    Any,
    Optional,
    Union,
    Type,
    cast,
)


from openai import (
    APIError,
    AsyncOpenAI,
    OpenAI,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
)

logger = logging.getLogger(__name__)


class LLMClientBase(abc.ABC):
    """Abstract base class for LLM clients.

    This class defines the common interface and core attributes for clients
    that interact with Large Language Models. It handles shared configuration
    such as API endpoint details, model preferences, and timeout settings.
    Subclasses must implement methods for actual client creation and API calls.

    Attributes:
        base_url (str): The base URL of the LLM API endpoint.
        api_key (str): The API key for authentication.
        model (str): LLM model name to use for requests (e.g., "gpt-3.5-turbo").
        context (int): The total context window size supported by the model
            (e.g., 4096 tokens).
        max_output_tokens (int): The maximum number of tokens to generate in a
            response.
        max_input_tokens (int): The calculated maximum number of tokens allowed
            for input, derived from `context` and `max_output_tokens`.
        timeout (int): Request timeout in seconds for API calls.
        max_retries (int): Max retries for transient errors by the OpenAI client
            (primarily for `AsyncOpenAI`).
        _client (Optional[Union[OpenAI, AsyncOpenAI]]): The underlying OpenAI or
            AsyncOpenAI client instance. Initialized by `_ensure_client`.
        _is_closed (bool): Flag indicating if the client has been closed and
            should not be used.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: Optional[str] = None,
        context: int = 4096,
        max_output_tokens: int = 2048,
        timeout: int = 900,
        max_retries: int = 3,
    ) -> None:
        """Initializes the LLMClientBase with common configuration.

        Args:
            base_url (str): The base URL of the LLM API (e.g.,
                "https://api.openai.com/v1"). Must not be empty.
            api_key (str): The API key for authentication. Must not be empty.
            model (str): Model name to use for requests (e.g., "gpt-3.5-turbo").
            context (int): The total context window size (input + output)
                supported by the targeted LLM, in tokens.
            max_output_tokens (int): The maximum number of tokens to reserve for
                the LLM's generation/output. This is subtracted from `context`
                to determine `max_input_tokens`.
            timeout (int): Default request timeout in seconds for API calls.
            max_retries (int): Default maximum number of retries for transient
                API errors. The `openai` library's `AsyncOpenAI` client uses this
                for its internal retry mechanism. For `SyncOpenAI`, retries might
                need to be handled more explicitly or by the caller.

        Raises:
            ValueError: If `base_url` is empty.

        Side Effects:
            - Initializes instance attributes: `base_url`, `api_key`,
              `default_model`, `context`, `max_output_tokens`,
              `max_input_tokens`, `timeout`, `max_retries`.
            - Sets `_client` to `None`.
            - Sets `_is_closed` to `False`.
            - Logs a warning if `api_key` is not provided.
        """
        if not api_key:
            logger.warning(
                f"Initializing LLMClient for {base_url} without an explicit API key."
            )
        if not base_url:
            raise ValueError("LLMClient requires a non-empty base_url.")

        self.base_url = base_url
        self.api_key = api_key
        self.default_model = model
        self.context = context
        self.max_output_tokens = max_output_tokens
        # Ensure max_input_tokens is not negative if context is smaller than max_output_tokens
        self.max_input_tokens = max(1024, context - max_output_tokens)
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[Union[OpenAI, AsyncOpenAI]] = None
        self._is_closed = False

    @abc.abstractmethod
    def _create_client(self) -> Union[OpenAI, AsyncOpenAI]:
        """Creates and returns the specific OpenAI client instance.

        This method must be implemented by concrete subclasses (`AsyncLLMClient`,
        `SyncLLMClient`) to instantiate and configure their respective
        `AsyncOpenAI` or `OpenAI` client.

        Returns:
            Union[OpenAI, AsyncOpenAI]: The initialized LLM client object.

        Raises:
            RuntimeError: If called on an already closed `LLMClientBase` instance
                          (though typically checked before this in `_ensure_client`).

        Side Effects:
            - May log information about client creation.
        """
        pass

    def _ensure_client(self) -> None:
        """Ensures the underlying LLM client is initialized.

        If the client has not been initialized yet (`self._client` is None)
        and the main client instance is not closed, this method calls
        `_create_client()` to instantiate it.

        Raises:
            RuntimeError: If the `LLMClientBase` instance has already been closed
                          (i.e., `self._is_closed` is True).

        Side Effects:
            - If `self._client` is None and `self._is_closed` is False,
              `self._create_client()` is called, which initializes `self._client`.
            - Logs a debug message upon auto-initialization.
        """
        if self._is_closed:
            raise RuntimeError("Cannot use client: LLMClient instance has been closed.")
        if self._client is None:
            self._client = self._create_client()
            logger.debug(
                f"Auto-initialized LLM client for {self.__class__.__name__} "
                f"targeting {self.base_url}"
            )

    @abc.abstractmethod
    def close(
        self,
    ) -> Union[None, Coroutine[Any, Any, None]]:
        """Closes the client connection and releases resources.

        Implementations in subclasses should ensure that the underlying HTTP
        client or connections are properly closed. This method should mark the
        client as closed to prevent further use.

        This method should be idempotent.

        Side Effects:
            - (In subclasses) Closes the underlying API client.
            - (In subclasses) Sets `self._client` to `None`.
            - (In subclasses) Sets `self._is_closed` to `True`.
        """
        pass

    @abc.abstractmethod
    def get_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> Union[str, Coroutine[Any, Any, str]]:
        """Retrieves the full completion content from the LLM (non-streaming).

        Subclasses must implement this method to make a non-streaming API call
        to the LLM and return the complete generated text.

        Args:
            messages (List[Dict[str, str]]): A list of message objects, where
                each dictionary must contain 'role' (e.g., 'user', 'assistant',
                'system') and 'content' (the message text).
            model (Optional[str]): The specific LLM model to use for this request.
                If None, the client's `default_model` is used.
            max_output_tokens (Optional[int]): The maximum number of tokens to
                generate in the completion. If None, the client's
                `max_output_tokens` setting is used.
            temperature (float): Sampling temperature for generation (e.g., 0.0 to 2.0).
                Lower values are more deterministic, higher values more creative.
            top_p (Optional[float]): Nucleus sampling parameter. Considers tokens
                with `top_p` probability mass. (e.g., 0.1 to 1.0).
            **kwargs (Any): Additional valid parameters to be passed directly to
                the underlying LLM API's completions endpoint.

        Returns:
            Optional[str]: The generated text content as a single string, or None
                           if no content was generated or an error occurred that
                           results in no content. An empty string `""` may be
                           returned if the LLM generates empty content.

        Raises:
            (In subclasses) Various API-specific exceptions (e.g., `openai.APIError`,
            `openai.RateLimitError`) or `RuntimeError` for operational issues.
            ValueError: If no model is specified (neither in args nor as default).
        """
        pass

    @abc.abstractmethod
    def stream_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> Union[Iterator[str], AsyncIterator[str]]:
        """Retrieves the completion content from the LLM in streaming mode.

        Subclasses must implement this method to make a streaming API call
        to the LLM and yield chunks of the generated text as they arrive.

        Args:
            messages (List[Dict[str, str]]): A list of message objects, where
                each dictionary must contain 'role' (e.g., 'user', 'assistant',
                'system') and 'content' (the message text).
            model (Optional[str]): The specific LLM model to use for this request.
                If None, the client's `default_model` is used.
            max_output_tokens (Optional[int]): The maximum number of tokens to
                generate in the completion. If None, the client's
                `max_output_tokens` setting is used.
            temperature (float): Sampling temperature for generation (e.g., 0.0 to 2.0).
            top_p (Optional[float]): Nucleus sampling parameter.
            **kwargs (Any): Additional valid parameters to be passed directly to
                the underlying LLM API's streaming completions endpoint.

        Yields:
            str: Chunks of the generated text content.

        Raises:
            (In subclasses) Various API-specific exceptions (e.g., `openai.APIError`,
            `openai.RateLimitError`) or `RuntimeError` for operational issues.
            ValueError: If no model is specified (neither in args nor as default).
        """
        pass


class AsyncLLMClient(LLMClientBase):
    """Asynchronous client for interacting with OpenAI-compatible LLMs.

    This client utilizes `openai.AsyncOpenAI` to perform non-blocking API calls
    for chat completions, supporting both full responses and streaming.
    It is suitable for use in asynchronous applications (e.g., FastAPI).
    The client can be used as an asynchronous context manager.

    Attributes:
        _client (Optional[AsyncOpenAI]): The underlying `openai.AsyncOpenAI`
            client instance. Inherited from `LLMClientBase` but specifically typed.
    """

    def _create_client(self) -> AsyncOpenAI:
        """Creates and configures an `openai.AsyncOpenAI` client instance.

        This method is called by `_ensure_client` when the underlying client
        needs to be initialized. It uses the `base_url`, `api_key`, `timeout`,
        and `max_retries` attributes from the `AsyncLLMClient` instance.

        Returns:
            AsyncOpenAI: The newly created `AsyncOpenAI` client.

        Raises:
            RuntimeError: If the `AsyncLLMClient` instance has already been closed.

        Side Effects:
            - Instantiates an `AsyncOpenAI` object.
            - Logs a debug message indicating client creation.
        """
        if self._is_closed:  # Should be caught by _ensure_client, but defensive check.
            raise RuntimeError(
                "Cannot create client: AsyncLLMClient instance has been closed."
            )

        logger.debug(f"Creating AsyncOpenAI client for {self.base_url}")
        return AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    async def close(self) -> None:
        """Asynchronously closes the underlying `AsyncOpenAI` client connection.

        This method should be called to release resources when the client is
        no longer needed, especially if not used as an async context manager.
        Sets `self._is_closed` to True and `self._client` to None.
        This method is idempotent.

        Side Effects:
            - Calls `self._client.close()` if the client exists and is not closed.
            - Sets `self._client` to `None`.
            - Sets `self._is_closed` to `True`.
            - Logs information about closing the client and any errors during closure.
        """
        client = cast(Optional[AsyncOpenAI], self._client)
        if client and not self._is_closed:
            logger.info(f"Closing AsyncLLMClient connection to {self.base_url}")
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing AsyncLLMClient: {e}", exc_info=True)
            finally:
                self._client = None
                self._is_closed = True
        elif not self._is_closed:
            self._is_closed = True

    async def __aenter__(self) -> "AsyncLLMClient":
        """Initializes the client for use as an asynchronous context manager.

        Ensures the underlying `AsyncOpenAI` client is created.

        Returns:
            AsyncLLMClient: The client instance itself.

        Side Effects:
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
        """
        self._ensure_client()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],  # traceback.TracebackType
    ) -> None:
        """Closes the client connection when exiting the async context manager.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of exception raised, if any.
            exc_val (Optional[BaseException]): The exception instance raised, if any.
            exc_tb (Optional[Any]): The traceback object, if any.

        Side Effects:
            - Calls `await self.close()`.
        """
        await self.close()

    async def get_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        """Asynchronously retrieves the full completion content from the LLM.

        This method makes a non-streaming API call to the configured LLM endpoint.

        Args:
            messages (List[Dict[str, str]]): A list of message objects representing
                the conversation history or prompt. Each dictionary must contain:
                - 'role' (str): The role of the message sender (e.g., 'system',
                  'user', 'assistant').
                - 'content' (str): The content of the message.
                Example: `[{"role": "user", "content": "Hello!"}]`
            model (Optional[str]): The specific LLM model to use for this request
                (e.g., "gpt-4", "claude-3-opus-20240229"). If None,
                the client's `default_model` is used.
            max_output_tokens (Optional[int]): The maximum number of tokens to
                generate in the completion. If None, the client's
                `self.max_output_tokens` setting is used.
            temperature (float): Sampling temperature for generation, typically
                between 0.0 and 2.0. Lower values (e.g., 0.2) make the output
                more focused and deterministic, while higher values (e.g., 0.8)
                make it more random and creative.
            top_p (Optional[float]): Nucleus sampling parameter, typically between
                0.0 and 1.0. The model considers only the tokens comprising the
                top `top_p` probability mass. E.g., 0.1 means only tokens from
                the top 10% probability mass are considered. If None, it's not used.
            **kwargs (Any): Additional valid parameters to be passed directly to
                the `openai.AsyncOpenAI.chat.completions.create` method.
                Refer to the OpenAI API documentation for available options
                (e.g., `frequency_penalty`, `presence_penalty`, `stop`).

        Returns:
            str: The generated text content as a single string. Returns an empty
                 string (`""`) if the LLM provides no content in its response message.

        Raises:
            ValueError: If no model is specified (neither in `model` argument
                        nor as `self.default_model`).
            RuntimeError: If the `AsyncLLMClient` instance has been closed, or if
                          the LLM response is received but contains no valid choice
                          or message content.
            openai.RateLimitError: If the API rate limit is exceeded.
            openai.APITimeoutError: If the API request times out.
            openai.APIConnectionError: If there's an issue connecting to the API.
            openai.APIError: For other non-retryable API errors from the LLM provider.
            Exception: For other unexpected errors during the LLM call.

        Side Effects:
            - Makes an external HTTP POST request to the LLM API endpoint.
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
            - Logs request details, API usage (prompt, completion, total tokens),
              and finish reason.

        Examples:
            ```python
            client = AsyncLLMClient(base_url="...", api_key="...")
            async with client:
                messages = [{"role": "user", "content": "Translate 'hello' to French."}]
                translation = await client.get_completion_content(messages, model="gpt-3.5-turbo")
                print(translation) # Output might be: "Bonjour"
            ```
        """
        model_to_use = model or self.default_model
        if not model_to_use:
            raise ValueError("No model specified for LLM completion request.")

        self._ensure_client()
        client = cast(AsyncOpenAI, self._client)

        request_params = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
            **kwargs,
        }
        # Remove None values to avoid sending them in the API request
        request_params = {k: v for k, v in request_params.items() if v is not None}

        logger.debug(f"Requesting async completion from model '{model_to_use}'...")

        try:
            completion = await client.chat.completions.create(**request_params)

            if completion.usage:
                logger.info(
                    f"LLM Usage (Model: {model_to_use}): "
                    f"Prompt={completion.usage.prompt_tokens}, "
                    f"Completion={completion.usage.completion_tokens}, "
                    f"Total={completion.usage.total_tokens}"
                )

            if completion.choices and completion.choices[0].message:
                response_content = completion.choices[0].message.content
                finish_reason = completion.choices[0].finish_reason
                logger.debug(f"Completion received. Finish reason: {finish_reason}")
                return response_content if response_content is not None else ""
            else:
                logger.warning(
                    "LLM response received but no valid choice or message content found."
                )
                # Ensure a string is returned as per type hint, even in this error case
                # before raising, though the raise is more prominent.
                # However, the current logic raises, which is fine.
                raise RuntimeError(
                    "LLM response received but no valid choice or message content found."
                )

        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
        ) as transient_error:
            logger.warning(f"Transient LLM API error: {transient_error}", exc_info=True)
            raise
        except APIError as api_error:  # Non-retryable by default by underlying client
            logger.error(f"Non-retryable LLM API error: {api_error}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during LLM call: {e}", exc_info=True)
            raise

    async def stream_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Asynchronously streams the completion content from the LLM.

        This method makes a streaming API call to the configured LLM endpoint
        and yields chunks of text as they are received.

        Args:
            messages (List[Dict[str, str]]): A list of message objects representing
                the conversation history or prompt. Each dictionary must contain:
                - 'role' (str): The role of the message sender (e.g., 'system',
                  'user', 'assistant').
                - 'content' (str): The content of the message.
                Example: `[{"role": "user", "content": "Tell me a story."}]`
            model (Optional[str]): The specific LLM model to use for this request
                (e.g., "gpt-4", "claude-3-opus-20240229"). If None,
                the client's `default_model` is used.
            max_output_tokens (Optional[int]): The maximum number of tokens to
                generate in the completion. If None, the client's
                `self.max_output_tokens` setting is used.
            temperature (float): Sampling temperature for generation, typically
                between 0.0 and 2.0.
            top_p (Optional[float]): Nucleus sampling parameter, typically between
                0.0 and 1.0. If None, it's not used.
            **kwargs (Any): Additional valid parameters to be passed directly to
                the `openai.AsyncOpenAI.chat.completions.create` method with
                `stream=True`. Refer to the OpenAI API documentation.

        Yields:
            str: Chunks of the generated text content from the LLM.

        Raises:
            ValueError: If no model is specified (neither in `model` argument
                        nor as `self.default_model`).
            RuntimeError: If the `AsyncLLMClient` instance has been closed.
            openai.RateLimitError: If the API rate limit is exceeded when initiating
                                   or during the stream.
            openai.APITimeoutError: If the API request times out.
            openai.APIConnectionError: If there's an issue connecting to the API.
            openai.APIError: For other non-retryable API errors from the LLM provider.
            Exception: For other unexpected errors during the streaming process.

        Side Effects:
            - Makes an external HTTP POST request to the LLM API endpoint.
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
            - Logs request details, stream initiation, finish reason, and total chunks.
            - May log API usage if provided in the final chunk of the stream.

        Examples:
            ```python
            client = AsyncLLMClient(base_url="...", api_key="...")
            async with client:
                messages = [{"role": "user", "content": "Write a short poem."}]
                async for chunk in client.stream_completion_content(messages):
                    print(chunk, end="")
            # Output will be the poem, printed chunk by chunk.
            ```
        """
        model_to_use = model or self.default_model
        if not model_to_use:
            raise ValueError("No model specified for LLM streaming request.")

        self._ensure_client()
        client = cast(AsyncOpenAI, self._client)

        request_params = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            **kwargs,
        }
        request_params = {k: v for k, v in request_params.items() if v is not None}

        logger.debug(
            f"Requesting async streaming completion from model '{model_to_use}'..."
        )

        try:
            stream = await client.chat.completions.create(**request_params)
            logger.debug("Async LLM stream initiated.")

            total_chunks = 0
            async for chunk in stream:
                total_chunks += 1
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason
                    if delta and delta.content:
                        yield delta.content
                    if finish_reason:
                        logger.info(
                            f"LLM stream finished for model {model_to_use}. "
                            f"Reason: {finish_reason}. Total chunks: {total_chunks}"
                        )
                        if hasattr(chunk, "usage") and chunk.usage:
                            logger.info(
                                f"LLM API Usage (final chunk for {model_to_use}): "
                                f"Prompt={chunk.usage.prompt_tokens}, "
                                f"Completion={chunk.usage.completion_tokens}, "
                                f"Total={chunk.usage.total_tokens}"
                            )
                        break  # Exit loop once finish_reason is encountered

            logger.debug(
                f"Async stream completed for model {model_to_use}, total chunks: {total_chunks}"
            )
            # No explicit return needed for AsyncGenerator if loop finishes or breaks

        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
        ) as transient_error:
            logger.warning(
                f"Transient LLM API error initiating/during stream: {transient_error}",
                exc_info=True,
            )
            raise
        except APIError as api_error:
            logger.error(
                f"Non-retryable LLM API error initiating/during stream: {api_error}",
                exc_info=True,
            )
            raise
        except (
            Exception
        ) as e:  # Includes StopAsyncIteration if not handled by openai lib
            logger.error(
                f"Unexpected error initiating/during stream: {e}", exc_info=True
            )
            raise


class SyncLLMClient(LLMClientBase):
    """Synchronous client for interacting with OpenAI-compatible LLMs.

    This client utilizes `openai.OpenAI` to perform blocking API calls
    for chat completions, supporting both full responses and streaming.
    It is suitable for use in synchronous applications or scripts.
    The client can be used as a context manager.

    Note: The underlying `openai.OpenAI` client's `max_retries` is set to 0
    by default in this implementation, meaning automatic retries for transient
    errors are disabled. Retries should be handled by the caller or by adjusting
    this client's configuration if needed.

    Attributes:
        _client (Optional[OpenAI]): The underlying `openai.OpenAI` client instance.
            Inherited from `LLMClientBase` but specifically typed.
    """

    def _create_client(self) -> OpenAI:
        """Creates and configures an `openai.OpenAI` client instance.

        This method is called by `_ensure_client` when the underlying client
        needs to be initialized. It uses the `base_url`, `api_key`, and `timeout`
        attributes from the `SyncLLMClient` instance. `max_retries` is explicitly
        set to 0 for the `OpenAI` client, disabling its automatic retries.

        Returns:
            OpenAI: The newly created `OpenAI` client.

        Raises:
            RuntimeError: If the `SyncLLMClient` instance has already been closed.

        Side Effects:
            - Instantiates an `OpenAI` object.
            - Logs a debug message indicating client creation.
        """
        if self._is_closed:
            raise RuntimeError(
                "Cannot create client: SyncLLMClient instance has been closed."
            )

        logger.debug(f"Creating OpenAI client for {self.base_url}")
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0,
        )

    def close(self) -> None:
        """Closes the underlying `OpenAI` client connection.

        This method should be called to release resources when the client is
        no longer needed, especially if not used as a context manager.
        Sets `self._is_closed` to True and `self._client` to None.
        This method is idempotent.

        Side Effects:
            - Calls `self._client.close()` if the client exists and is not closed.
            - Sets `self._client` to `None`.
            - Sets `self._is_closed` to `True`.
            - Logs information about closing the client and any errors during closure.
        """
        client = cast(Optional[OpenAI], self._client)
        if client and not self._is_closed:
            logger.info(f"Closing SyncLLMClient connection to {self.base_url}")
            try:
                client.close()
            except Exception as e:
                logger.error(f"Error closing SyncLLMClient: {e}", exc_info=True)
            finally:
                self._client = None
                self._is_closed = True
        elif not self._is_closed:
            self._is_closed = True

    def __enter__(self) -> "SyncLLMClient":
        """Initializes the client for use as a context manager.

        Ensures the underlying `OpenAI` client is created.

        Returns:
            SyncLLMClient: The client instance itself.

        Side Effects:
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
        """
        self._ensure_client()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],  # traceback.TracebackType
    ) -> None:
        """Closes the client connection when exiting the context manager.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of exception raised, if any.
            exc_val (Optional[BaseException]): The exception instance raised, if any.
            exc_tb (Optional[Any]): The traceback object, if any.

        Side Effects:
            - Calls `self.close()`.
        """
        self.close()

    def get_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        """Synchronously retrieves the full completion content from the LLM.

        This method makes a blocking, non-streaming API call to the
        configured LLM endpoint.

        Args:
            messages (List[Dict[str, str]]): A list of message objects representing
                the conversation history or prompt. Each dictionary must contain:
                - 'role' (str): The role of the message sender (e.g., 'system',
                  'user', 'assistant').
                - 'content' (str): The content of the message.
                Example: `[{"role": "user", "content": "Hello!"}]`
            model (Optional[str]): The specific LLM model to use for this request
                (e.g., "gpt-3.5-turbo"). If None, the client's `default_model`
                is used.
            max_output_tokens (Optional[int]): The maximum number of tokens to
                generate in the completion. If None, the client's
                `self.max_output_tokens` setting is used.
            temperature (float): Sampling temperature for generation (0.0-2.0).
            top_p (Optional[float]): Nucleus sampling parameter (0.0-1.0).
                If None, it's not used.
            **kwargs (Any): Additional valid parameters to be passed directly to
                the `openai.OpenAI.chat.completions.create` method.
                Refer to the OpenAI API documentation.

        Returns:
            str: The generated text content as a single string. Returns an empty
                 string (`""`) if the LLM provides no content in its response message.

        Raises:
            ValueError: If no model is specified.
            RuntimeError: If the `SyncLLMClient` instance has been closed, or if
                          the LLM response is received but contains no valid choice
                          or message content.
            openai.RateLimitError: If the API rate limit is exceeded.
            openai.APITimeoutError: If the API request times out.
            openai.APIConnectionError: If there's an issue connecting to the API.
            openai.APIError: For other non-retryable API errors from the LLM provider.
            Exception: For other unexpected errors during the LLM call.

        Side Effects:
            - Makes an external HTTP POST request to the LLM API endpoint.
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
            - Logs request details, API usage, and finish reason.

        Examples:
            ```python
            client = SyncLLMClient(base_url="...", api_key="...")
            with client:
                messages = [{"role": "user", "content": "What is 2+2?"}]
                result = client.get_completion_content(messages)
                print(result) # Output might be: "2+2 equals 4."
            ```
        """
        model_to_use = model or self.default_model
        if not model_to_use:
            raise ValueError("No model specified for LLM completion request.")

        self._ensure_client()
        client = cast(OpenAI, self._client)

        request_params = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
            **kwargs,
        }
        request_params = {k: v for k, v in request_params.items() if v is not None}

        logger.debug(f"Requesting sync completion from model '{model_to_use}'...")

        try:
            completion = client.chat.completions.create(**request_params)

            if completion.usage:
                logger.info(
                    f"LLM Usage (Model: {model_to_use}): "
                    f"Prompt={completion.usage.prompt_tokens}, "
                    f"Completion={completion.usage.completion_tokens}, "
                    f"Total={completion.usage.total_tokens}"
                )

            if completion.choices and completion.choices[0].message:
                response_content = completion.choices[0].message.content
                finish_reason = completion.choices[0].finish_reason
                logger.debug(f"Completion received. Finish reason: {finish_reason}")
                return response_content if response_content is not None else ""
            else:
                logger.warning(
                    "LLM response received but no valid choice or message content found."
                )
                raise RuntimeError(
                    "LLM response received but no valid choice or message content found."
                )

        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
        ) as transient_error:  # Retries for these are not handled by default by OpenAI sync client
            logger.warning(f"Transient LLM API error: {transient_error}", exc_info=True)
            raise
        except APIError as api_error:
            logger.error(f"Non-retryable LLM API error: {api_error}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during LLM call: {e}", exc_info=True)
            raise

    def stream_completion_content(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: Optional[float] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Synchronously streams the completion content from the LLM.

        This method makes a blocking, streaming API call to the configured
        LLM endpoint and yields chunks of text as they are received.

        Args:
            messages (List[Dict[str, str]]): A list of message objects representing
                the conversation history or prompt. Each dictionary must contain:
                - 'role' (str): The role of the message sender.
                - 'content' (str): The content of the message.
                Example: `[{"role": "user", "content": "Recite the alphabet."}]`
            model (Optional[str]): The specific LLM model to use. If None,
                the client's `default_model` is used.
            max_output_tokens (Optional[int]): Max tokens for the response. If None,
                `self.max_output_tokens` is used.
            temperature (float): Sampling temperature (0.0-2.0).
            top_p (Optional[float]): Nucleus sampling parameter (0.0-1.0).
                If None, it's not used.
            **kwargs (Any): Additional valid parameters for the OpenAI API
                completions endpoint with `stream=True`.

        Yields:
            str: Chunks of the generated text content from the LLM.

        Raises:
            ValueError: If no model is specified.
            RuntimeError: If the `SyncLLMClient` instance has been closed.
            openai.RateLimitError: If API rate limit is exceeded.
            openai.APITimeoutError: If API request times out.
            openai.APIConnectionError: If connection issue occurs.
            openai.APIError: For other non-retryable API errors.
            Exception: For other unexpected errors during streaming.

        Side Effects:
            - Makes an external HTTP POST request to the LLM API endpoint.
            - Calls `self._ensure_client()`, potentially initializing `self._client`.
            - Logs request details, stream initiation, finish reason, and total chunks.
            - May log API usage if provided in the final chunk.

        Examples:
            ```python
            client = SyncLLMClient(base_url="...", api_key="...")
            with client:
                messages = [{"role": "user", "content": "Count to 3."}]
                for chunk in client.stream_completion_content(messages):
                    print(chunk, end="")
            # Output will be "123" or similar, printed chunk by chunk.
            ```
        """
        model_to_use = model or self.default_model
        if not model_to_use:
            raise ValueError("No model specified for LLM streaming request.")

        self._ensure_client()
        client = cast(OpenAI, self._client)

        request_params = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_output_tokens or self.max_output_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            **kwargs,
        }
        request_params = {k: v for k, v in request_params.items() if v is not None}

        logger.debug(
            f"Requesting sync streaming completion from model '{model_to_use}'..."
        )

        try:
            stream = client.chat.completions.create(**request_params)
            logger.debug("Sync LLM stream initiated.")

            total_chunks = 0
            for chunk in stream:
                total_chunks += 1
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason
                    if delta and delta.content:
                        yield delta.content
                    if finish_reason:
                        logger.info(
                            f"LLM stream finished for model {model_to_use}. "
                            f"Reason: {finish_reason}. Total chunks: {total_chunks}"
                        )
                        if hasattr(chunk, "usage") and chunk.usage:
                            logger.info(
                                f"LLM API Usage (final chunk for {model_to_use}): "
                                f"Prompt={chunk.usage.prompt_tokens}, "
                                f"Completion={chunk.usage.completion_tokens}, "
                                f"Total={chunk.usage.total_tokens}"
                            )
                        break
            logger.debug(
                f"Sync stream completed for model {model_to_use}, total chunks: {total_chunks}"
            )
            # No explicit return needed for Generator if loop finishes or breaks

        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
        ) as transient_error:
            logger.warning(
                f"Transient LLM API error initiating/during stream: {transient_error}",
                exc_info=True,
            )
            raise
        except APIError as api_error:
            logger.error(
                f"Non-retryable LLM API error initiating/during stream: {api_error}",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error initiating/during stream: {e}", exc_info=True
            )
            raise
