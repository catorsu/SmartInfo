"""
Crawlers for fetching web content using different strategies.

This module provides various crawler implementations for asynchronously fetching
web content. It includes:
  - AiohttpCrawler: For fast, lightweight HTTP requests.
  - PlaywrightCrawler: For JavaScript-heavy pages requiring browser rendering.
  - SeleniumCrawler: An alternative for browser automation, also handling
    JavaScript rendering.

Each crawler is designed to be used as an asynchronous context manager and
supports features like rate limiting, retries with exponential backoff,
and user-agent rotation.

Key Components/Exports:
    - AiohttpCrawler: Asynchronous HTTP client-based crawler.
    - PlaywrightCrawler: Playwright-based browser automation crawler.
    - SeleniumCrawler: Selenium-based browser automation crawler.
    - calculate_backoff: Utility function for retry delay calculation.
"""

import asyncio
import logging
import random
import time
import os
import functools
from typing import List, Dict, Optional, AsyncGenerator, Any, Set, Union, Tuple, Type
from dataclasses import dataclass, field
from urllib.parse import urlparse


from playwright.async_api import (
    async_playwright,
    Page,
    Browser,
    Playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    ViewportSize,
)
import aiohttp
import charset_normalizer


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


DEFAULT_MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # Base delay in seconds.
DEFAULT_JITTER_FACTOR = 0.1
DEFAULT_MAX_CONCURRENT_REQUESTS = 10


def calculate_backoff(
    attempt: int, base_delay: float = DEFAULT_RETRY_BASE_DELAY
) -> float:
    """Calculates an exponential backoff delay with jitter.

    This function is used to determine how long to wait before retrying a
    failed operation. The delay increases exponentially with each attempt,
    and jitter is added to prevent thundering herd problems.

    Args:
        attempt (int): The current retry attempt number (0-indexed for the
            first retry, so an initial failed attempt would lead to `attempt=0`
            for the first retry).
        base_delay (float): The base delay in seconds for the first retry.
            Defaults to `DEFAULT_RETRY_BASE_DELAY`.

    Returns:
        float: The calculated delay in seconds.

    Examples:
        >>> calculate_backoff(0, 1.0)  # Approx 1.0 +/- 0.1
        # Example output: 1.05
        >>> calculate_backoff(1, 1.0)  # Approx 2.0 +/- 0.2
        # Example output: 2.10
        >>> calculate_backoff(2, 0.5)  # Approx 2.0 +/- 0.2 (0.5 * 2^2)
        # Example output: 1.95
    """
    delay = base_delay * (2**attempt)
    jitter = delay * DEFAULT_JITTER_FACTOR
    return delay + random.uniform(-jitter, jitter)


class AiohttpCrawler:
    """
    Asynchronous web crawler using `aiohttp` for fetching HTML content.

    This crawler is designed for efficient, non-blocking I/O operations,
    making it suitable for fetching content from multiple URLs concurrently.
    It supports rate limiting per domain, configurable user-agents, and
    can be used as an asynchronous context manager.

    Attributes:
        max_concurrent_requests (int): Maximum number of concurrent requests.
        session (aiohttp.ClientSession): The active aiohttp client session.
        domain_timestamps (Dict[str, float]): Tracks last access time per domain.
        domain_locks (Dict[str, asyncio.Lock]): Locks for per-domain rate limiting.
        semaphore (asyncio.Semaphore): Controls overall concurrency.

    Examples:
        >>> async def main():
        ...     urls_to_crawl = ["http://example.com", "http://example.org"]
        ...     async with AiohttpCrawler() as crawler:
        ...         async for result in crawler.process_urls(urls_to_crawl):
        ...             if result.get("error"):
        ...                 print(f"Error fetching {result['original_url']}: {result['error']}")
        ...             else:
        ...                 print(f"Fetched {result['final_url']}: {len(result['content'])} bytes")
        # To run the example: asyncio.run(main())
    """

    def __init__(
        self,
        max_concurrent_requests: int = 10,
        user_agent: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initializes the AiohttpCrawler.

        Args:
            max_concurrent_requests (int): The maximum number of concurrent
                HTTP requests the crawler can make. Defaults to 10.
            user_agent (Optional[str]): The User-Agent string to use for requests.
                If None, "SmartInfo/1.0" is used.
            headers (Optional[Dict[str, str]]): Custom HTTP headers to include
                in all requests. If 'User-Agent' is not in `headers`, the
                `user_agent` argument (or default) will be used.

        Side Effects:
            - Initializes an `aiohttp.ClientSession` with specified headers
              and a `TCPConnector` configured for concurrency.
            - Sets up internal structures for rate limiting (`domain_timestamps`,
              `domain_locks`) and concurrency control (`semaphore`).
        """
        self.max_concurrent_requests = max_concurrent_requests

        user_agent = user_agent or "SmartInfo/1.0"
        headers = headers or {}
        if "User-Agent" not in headers and user_agent:
            headers["User-Agent"] = user_agent

        tcp_connector = aiohttp.TCPConnector(
            limit=max_concurrent_requests,
            ttl_dns_cache=300,
            # enable_cleanup_closed=True, # NOTE: fixed in python3.13
            force_close=False,
        )

        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=None),
            connector=tcp_connector,
        )

        self.domain_timestamps: Dict[str, float] = {}
        self.domain_locks: Dict[str, asyncio.Lock] = {}

        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def __aenter__(self) -> "AiohttpCrawler":
        """Enters the asynchronous context, returning the crawler instance.

        Returns:
            AiohttpCrawler: The instance of the crawler.
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Exits the asynchronous context, ensuring the session is closed.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of exception raised, if any.
            exc_val (Optional[BaseException]): The exception instance raised, if any.
            exc_tb (Optional[Any]): The traceback object, if any.

        Returns:
            bool: False, indicating that exceptions (if any) should not be suppressed.

        Side Effects:
            - Calls `self.shutdown()` to close the `aiohttp.ClientSession`.
        """
        await self.shutdown()
        return False  # Do not suppress exceptions.

    async def shutdown(self) -> None:
        """Closes the `aiohttp.ClientSession` and releases associated resources.

        This method should be called when the crawler is no longer needed,
        especially if not used as an async context manager. It is idempotent.

        Side Effects:
            - Closes the `self.session` if it's open.
            - Logs shutdown process and any errors during session closure.
        """
        logger.info("Shutting down AiohttpCrawler...")
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                logger.info("Session closed successfully.")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
        logger.info("AiohttpCrawler shutdown complete.")

    async def _enforce_domain_rate_limit(self, url: str) -> None:
        """Enforces a rate limit for requests to the same domain.

        This method ensures that requests to a specific domain are spaced out
        by at least 1 second to avoid overloading the server. It uses a lock
        per domain for thread-safe (async-safe) timestamp updates.

        Args:
            url (str): The URL for which to enforce the rate limit. The domain
                is extracted from this URL.

        Side Effects:
            - May `await asyncio.sleep()` if the last request to the domain
              was too recent.
            - Updates `self.domain_timestamps` for the domain.
        """
        domain = urlparse(url).netloc

        lock = self.domain_locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self.domain_locks[domain] = lock

        async with lock:
            last_access = self.domain_timestamps.get(domain, 0)
            now = time.time()

            if now - last_access < 1.0:  # 1 second between requests to same domain.
                delay = 1.0 - (now - last_access)
                await asyncio.sleep(delay)

            self.domain_timestamps[domain] = time.time()

    async def fetch_single(
        self,
        url: str,
        timeout: int = 10,
        max_retries: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    ) -> Dict[str, str]:
        """Fetches the raw HTML content of a single URL with retries.

        Args:
            url (str): The URL to fetch.
            timeout (int): Request timeout in seconds. Defaults to 10.
            max_retries (int): Maximum number of retry attempts for transient
                errors. Defaults to `DEFAULT_MAX_RETRY_ATTEMPTS`.

        Returns:
            Dict[str, str]: A dictionary containing:
                - "original_url" (str): The URL initially requested.
                - "final_url" (str): The URL after any redirects.
                - "content" (str): The decoded HTML content, or an empty string
                  if fetching or decoding failed.
                - "error" (str): An error message if an error occurred, otherwise
                  an empty string.

        Side Effects:
            - Makes HTTP GET requests.
            - Logs fetching attempts, successes, errors, and retries.
            - May sleep during retries due to `calculate_backoff`.
        """
        await self._enforce_domain_rate_limit(url)

        html_content = ""
        error_message = ""
        final_url = url
        fetch_start_time = time.time()

        async with self.semaphore:
            retry_attempt = 0
            while retry_attempt <= max_retries:
                try:
                    logger.info(f"[Worker] Fetching: {url} (Attempt {retry_attempt+1})")

                    async with self.session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        allow_redirects=True,
                        ssl=False,  # Skip SSL verification for better performance.
                    ) as response:
                        response.raise_for_status()
                        final_url = str(response.url)

                        chunks = []
                        async for chunk in response.content.iter_chunked(8192):
                            chunks.append(chunk)

                        raw_content = b"".join(chunks)

                        # Attempt to decode content.
                        encoding = response.charset
                        try:
                            if encoding:
                                html_content = raw_content.decode(
                                    encoding, errors="replace"
                                )
                            else:
                                # Use charset_normalizer as a fallback if no charset is provided.
                                matches = charset_normalizer.from_bytes(
                                    raw_content
                                ).best()
                                if matches:
                                    detected_encoding = matches.encoding
                                    html_content = raw_content.decode(
                                        detected_encoding, errors="replace"
                                    )
                                else:
                                    # Ultimate fallback to UTF-8.
                                    html_content = raw_content.decode(
                                        "utf-8", errors="replace"
                                    )

                        except Exception as decode_err:
                            error_message = f"Decoding error: {decode_err}"
                            logger.error(f"Error decoding {url}: {decode_err}")
                            return {
                                "original_url": url,
                                "final_url": final_url,
                                "content": "",
                                "error": error_message,
                            }

                    fetch_duration = time.time() - fetch_start_time
                    logger.info(
                        f"[Worker] Successfully fetched: {final_url} in {fetch_duration:.2f} seconds"
                    )
                    # Successful fetch, break retry loop.
                    break

                except aiohttp.ClientResponseError as e:
                    error_message = f"HTTP error: {e.status} {e.message}"
                    logger.error(f"HTTP error for {url}: {e.status} - {e.message}")
                except asyncio.TimeoutError:
                    error_message = f"Request timed out (>{timeout} seconds)"
                    logger.error(f"Request timed out for {url}")
                except aiohttp.ClientError as e:
                    error_message = f"Client error: {e}"
                    logger.error(f"Client error for {url}: {e}")
                except Exception as e:
                    error_message = f"Unexpected error: {e}"
                    logger.exception(f"Unexpected error while fetching {url}")

                retry_attempt += 1
                if retry_attempt <= max_retries:
                    backoff = calculate_backoff(retry_attempt - 1)
                    logger.info(
                        f"Retrying {url} in {backoff:.2f} seconds (attempt {retry_attempt}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)

        result = {
            "original_url": url,
            "final_url": final_url,
            "content": html_content,
            "error": error_message,
        }

        return result

    async def process_urls(
        self,
        urls: List[str],
        timeout: int = 10,
        max_retries: int = DEFAULT_MAX_RETRY_ATTEMPTS,
        batch_size: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Processes a list of URLs asynchronously and yields results.

        Args:
            urls (List[str]): A list of URLs to fetch.
            timeout (int): Request timeout in seconds for each URL.
                Defaults to 10.
            max_retries (int): Maximum retry attempts for each URL.
                Defaults to `DEFAULT_MAX_RETRY_ATTEMPTS`.
            batch_size (Optional[int]): The number of URLs to process in each
                concurrent batch. If None, defaults to a value based on
                `max_concurrent_requests`.

        Yields:
            Dict[str, str]: A dictionary for each processed URL, containing
                "original_url", "final_url", "content", and "error" keys.

        Side Effects:
            - Creates and manages multiple asyncio tasks for fetching URLs.
            - Logs progress, errors, and task execution details.
        """
        if not urls:
            return

        if batch_size is None:
            batch_size = min(len(urls), self.max_concurrent_requests * 2)

        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            tasks = [
                asyncio.create_task(
                    self.fetch_single(url, timeout, max_retries),
                    name=f"fetch_{url[:50]}",  # Name task for easier debugging.
                )
                for url in batch
            ]

            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    yield result
                    if isinstance(result, dict) and result.get("error"):
                        logger.warning(
                            f"Error processing URL {result.get('original_url', 'unknown')}: {result['error']}"
                        )
                except Exception as e:
                    # This catches errors from the task itself (e.g., if fetch_single had an unhandled exception).
                    task_name = (
                        future.get_name()
                        if isinstance(future, asyncio.Task)
                        else "unknown_task"
                    )
                    logger.error(
                        f"Task {task_name} raised an exception: {e}", exc_info=True
                    )
                    # Yield an error result for this URL.
                    original_url = (
                        task_name.replace("fetch_", "")
                        if task_name.startswith("fetch_")
                        else "unknown_url"
                    )
                    yield {
                        "original_url": original_url,
                        "final_url": original_url,
                        "content": "",
                        "error": f"Task execution failed: {e}",
                    }
            # Small delay between batches if there are more URLs.
            if i + batch_size < len(urls):
                await asyncio.sleep(0.5)


class PlaywrightCrawler:
    """
    Asynchronous web crawler using Playwright for fetching HTML content.

    This crawler leverages a headless browser (Chromium by default) via
    Playwright to render web pages, including those heavily reliant on
    JavaScript. It's suitable for complex sites where simple HTTP requests
    are insufficient. It features a pool of browser contexts for concurrency,
    user-agent rotation, and retry mechanisms.

    Attributes:
        headless (bool): Whether to run the browser in headless mode.
        page_timeout (int): Default timeout in milliseconds for page operations.
        max_retries (int): Maximum retry attempts for fetching a URL.
        browser_args (Dict[str, Any]): Arguments for launching the browser.
        user_agent (Optional[str]): Specific user agent to use if rotation is off.
        user_agent_rotation (bool): Whether to rotate user agents.
        pw_instance (Optional[Playwright]): The Playwright instance.
        browser (Optional[Browser]): The Playwright browser instance.
        context_pool (List[Dict[str, Any]]): Pool of browser contexts.
        domain_timestamps (Dict[str, float]): Tracks last access time per domain.
        domain_locks (Dict[str, asyncio.Lock]): Locks for per-domain rate limiting.
        user_agents (List[str]): List of user agents for rotation.

    Examples:
        >>> async def main():
        ...     urls_to_crawl = ["https://example.com/dynamic-page"]
        ...     async with PlaywrightCrawler() as crawler:
        ...         async for result in crawler.process_urls(urls_to_crawl):
        ...             # Process result
        ...             pass
        # To run the example: asyncio.run(main())
    """

    def __init__(
        self,
        headless: bool = True,
        max_concurrent_pages: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        page_timeout: int = 10000,  # ms
        browser_args: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        user_agent_rotation: bool = True,
        max_retries: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    ):
        """Initializes the PlaywrightCrawler.

        Args:
            headless (bool): If True, runs the browser in headless mode.
                Defaults to True.
            max_concurrent_pages (int): Maximum number of browser pages (contexts)
                to use concurrently. Defaults to `DEFAULT_MAX_CONCURRENT_REQUESTS`.
            page_timeout (int): Default timeout in milliseconds for page
                operations like `goto` and `wait_for_load_state`. Defaults to 10000.
            browser_args (Optional[Dict[str, Any]]): Additional arguments to
                pass when launching the browser (e.g., `{"args": ["--no-sandbox"]}`).
            user_agent (Optional[str]): A specific User-Agent string. If provided
                and `user_agent_rotation` is False, this agent is used. If
                `user_agent_rotation` is True, this agent is added to the list
                of agents to rotate.
            user_agent_rotation (bool): If True, rotates User-Agent strings
                from a predefined list for each context. Defaults to True.
            max_retries (int): Maximum number of retry attempts for fetching a URL.
                Defaults to `DEFAULT_MAX_RETRY_ATTEMPTS`.

        Side Effects:
            - Initializes configuration attributes.
            - Sets up internal structures for managing Playwright resources,
              context pooling, rate limiting, and user agents.
        """
        self.headless = headless
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        self.browser_args = browser_args or {}
        self.user_agent = user_agent
        self.user_agent_rotation = user_agent_rotation
        self.pw_instance: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._start_lock = asyncio.Lock()
        self._browser_initialized = False

        self.context_pool: List[Dict[str, Any]] = []
        self.context_pool_size = max_concurrent_pages
        self.context_pool_lock = asyncio.Lock()

        self.domain_timestamps: Dict[str, float] = {}
        self.domain_locks: Dict[str, asyncio.Lock] = {}

        self.user_agents: List[str] = self._initialize_user_agents(user_agent)

    async def __aenter__(self) -> "PlaywrightCrawler":
        """Enters the asynchronous context, ensuring the browser is started.

        Returns:
            PlaywrightCrawler: The instance of the crawler.

        Side Effects:
            - Calls `self._ensure_browser_started()`.
        """
        await self._ensure_browser_started()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Exits the asynchronous context, ensuring Playwright resources are shut down.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of exception raised, if any.
            exc_val (Optional[BaseException]): The exception instance raised, if any.
            exc_tb (Optional[Any]): The traceback object, if any.

        Returns:
            bool: False, indicating that exceptions (if any) should not be suppressed.

        Side Effects:
            - Calls `self.shutdown()`.
        """
        await self.shutdown()
        return False  # Don't suppress exceptions.

    def _initialize_user_agents(self, default_user_agent: Optional[str]) -> List[str]:
        """Initializes a list of User-Agent strings for rotation.

        Includes a set of common browser user agents. If a `default_user_agent`
        is provided, it's added to this list.

        Args:
            default_user_agent (Optional[str]): A specific user agent to include.

        Returns:
            List[str]: A list of User-Agent strings.
        """
        common_user_agents = [
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
            # Firefox on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
            # Safari on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Safari/605.1.15",
            # Chrome on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51",
            # Chrome on Android
            "Mozilla/5.0 (Linux; Android 11; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
            # Safari on iOS
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Mobile/15E148 Safari/604.1",
        ]

        if default_user_agent:
            return [default_user_agent] + common_user_agents

        default = "SmartInfo/1.0 (Playwright)"
        return [default] + common_user_agents

    def _get_random_user_agent(self) -> str:
        """Selects a User-Agent string.

        If `user_agent_rotation` is enabled and multiple agents are available,
        it picks one randomly. Otherwise, it returns the first (or only) agent.

        Returns:
            str: A User-Agent string.
        """
        if not self.user_agent_rotation or len(self.user_agents) <= 1:
            return self.user_agents[0]

        return random.choice(self.user_agents)

    async def _initialize_context_pool(self) -> None:
        """Initializes a pool of Playwright browser contexts.

        Each context is configured with a potentially different user agent and
        viewport size to simulate diverse browser profiles, which can help
        avoid detection and improve crawling success.

        Side Effects:
            - Creates `self.context_pool_size` number of browser contexts.
            - Populates `self.context_pool` with these contexts.
            - Logs initialization details.
        """
        async with self.context_pool_lock:
            logger.info(
                f"Initializing context pool with {self.context_pool_size} contexts"
            )
            if not self.browser:  # Should be ensured by _ensure_browser_started
                logger.error("Browser not initialized before context pool creation.")
                return
            for i in range(self.context_pool_size):
                user_agent = self._get_random_user_agent()
                # Small variation in viewport sizes.
                viewport = ViewportSize(width=1280, height=720)
                if i % 3 == 1:
                    viewport = ViewportSize(width=1366, height=768)
                elif i % 3 == 2:
                    viewport = ViewportSize(width=1920, height=1080)

                context = await self.browser.new_context(
                    user_agent=user_agent,
                    viewport=viewport,
                    java_script_enabled=True,
                )

                self.context_pool.append(
                    {
                        "context": context,
                        "in_use": False,
                        "user_agent": user_agent,
                        "viewport": viewport,
                    }
                )
            logger.info("Context pool initialized with diverse browser profiles.")

    async def _get_context_from_pool(self) -> Dict[str, Any]:
        """Retrieves an available browser context from the pool.

        If all contexts in the pool are in use, it logs this and attempts to
        create a new temporary context.

        Returns:
            Dict[str, Any]: A dictionary representing the acquired context item,
                containing the context object and its usage status.

        Raises:
            RuntimeError: If the browser is not initialized.

        Side Effects:
            - Marks a context in `self.context_pool` as "in_use".
            - May create a new context if the pool is exhausted (though this
              behavior might be refined to strictly use pooled contexts).
        """
        async with self.context_pool_lock:
            for item in self.context_pool:
                if not item["in_use"]:
                    item["in_use"] = True
                    return item

            # Fallback: if all contexts are in use, log and potentially create a new one (or wait).
            # Current implementation creates a new one, which might exceed desired concurrency.
            # A better approach for strict pooling would be to use an asyncio.Semaphore
            # or wait for a context to become available.
            logger.info("All contexts in use, creating a new temporary one.")
            if not self.browser:  # Should be ensured by _ensure_browser_started
                raise RuntimeError(
                    "Browser not initialized when trying to get context."
                )

            context = await self.browser.new_context(user_agent=self.user_agent)
            new_item = {"context": context, "in_use": True}
            # Note: This temporary context is not added to the main pool for reuse tracking here.
            # This part of the logic might need refinement if strict pool sizing is critical.
            return new_item

    async def _return_context_to_pool(self, context_item: Dict[str, Any]) -> None:
        """Returns a browser context to the pool, marking it as not in use.

        Args:
            context_item (Dict[str, Any]): The context item dictionary that was
                previously acquired from the pool.

        Side Effects:
            - Marks the corresponding context in `self.context_pool` as "in_use": False.
        """
        async with self.context_pool_lock:
            for item in self.context_pool:
                if item["context"] == context_item["context"]:
                    item["in_use"] = False
                    break

    async def _ensure_browser_started(self) -> None:
        """Ensures Playwright and the browser are started, using a lock.

        This method handles the lazy initialization of Playwright and the
        browser instance. It's thread-safe (async-safe) due to `_start_lock`.

        Raises:
            RuntimeError: If Playwright or the browser fails to start.

        Side Effects:
            - If not already initialized:
                - Starts Playwright (`self.pw_instance`).
                - Launches a Chromium browser (`self.browser`).
                - Initializes the context pool (`self._initialize_context_pool()`).
                - Sets `self._browser_initialized` to True.
            - Logs initialization steps and errors.
            - Calls `self.shutdown()` if initialization fails partway.
        """
        if self._browser_initialized and self.browser and self.browser.is_connected():
            return

        async with self._start_lock:
            # Double-check after acquiring lock.
            if (
                self._browser_initialized
                and self.browser
                and self.browser.is_connected()
            ):
                return

            if self.pw_instance is None:
                try:
                    logger.info("Starting Playwright...")
                    self.pw_instance = await async_playwright().start()
                except Exception as e:
                    raise RuntimeError("Unable to start Playwright") from e
            try:
                logger.info(f"Starting browser (headless={self.headless})...")
                launch_args: Dict[str, Any] = {
                    "headless": self.headless,
                }
                # Prepare Chromium arguments for stability/performance.
                chromium_args = self.browser_args.get("args", [])
                if not any("disable-dev-shm-usage" in arg for arg in chromium_args):
                    chromium_args.append("--disable-dev-shm-usage")
                if not any("disable-gpu" in arg for arg in chromium_args):
                    chromium_args.append("--disable-gpu")
                if not any("disable-setuid-sandbox" in arg for arg in chromium_args):
                    chromium_args.append("--disable-setuid-sandbox")
                if not any("no-sandbox" in arg for arg in chromium_args):
                    chromium_args.append("--no-sandbox")

                if chromium_args:
                    launch_args["args"] = chromium_args

                self.browser = await self.pw_instance.chromium.launch(**launch_args)
                logger.info("Browser started successfully.")

                await self._initialize_context_pool()
                self._browser_initialized = True

            except Exception as e:
                await self.shutdown()  # Attempt cleanup on partial failure.
                raise RuntimeError(f"Unable to start browser: {e}") from e

    async def shutdown(self) -> None:
        """Closes all browser contexts, the browser, and stops Playwright.

        This method should be called to release all Playwright resources.
        It is idempotent.

        Side Effects:
            - Closes all contexts in `self.context_pool`.
            - Closes `self.browser`.
            - Stops `self.pw_instance`.
            - Resets internal state attributes related to initialization.
            - Logs shutdown process and any errors.
        """
        logger.info("Shutting down the Playwright crawler...")
        async with self._start_lock:  # Ensure exclusive access during shutdown.
            if hasattr(self, "context_pool") and self.context_pool:
                for item in self.context_pool:
                    try:
                        await item["context"].close()
                    except Exception as e:
                        logger.error(f"Error closing context: {e}")
                self.context_pool = []

            if self.browser:
                try:
                    await self.browser.close()
                    logger.info("Browser closed.")
                except Exception as e:
                    logger.error(f"Error closing browser: {e}")
                finally:
                    self.browser = None
            if self.pw_instance:
                try:
                    await self.pw_instance.stop()
                    logger.info("Playwright stopped.")
                except Exception as e:
                    logger.error(f"Error stopping Playwright: {e}")
                finally:
                    self.pw_instance = None
            self._browser_initialized = False  # Reset initialization flag.
        logger.info("Playwright crawler shutdown complete.")

    async def _enforce_domain_rate_limit(self, url: str) -> None:
        """Enforces a rate limit for requests to the same domain.

        (Identical to AiohttpCrawler's implementation, could be refactored
        into a shared utility if desired.)

        Args:
            url (str): The URL for which to enforce the rate limit.

        Side Effects:
            - May `await asyncio.sleep()`.
            - Updates `self.domain_timestamps`.
        """
        domain = urlparse(url).netloc
        lock = self.domain_locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self.domain_locks[domain] = lock

        async with lock:
            last_access = self.domain_timestamps.get(domain, 0)
            now = time.time()
            if now - last_access < 1.0:  # 1 second delay.
                delay = 1.0 - (now - last_access)
                await asyncio.sleep(delay)
            self.domain_timestamps[domain] = time.time()

    async def fetch_single(
        self,
        url: str,
        scroll_page: bool = False,
    ) -> Dict[str, str]:
        """Fetches the raw HTML content of a single URL using Playwright.

        Manages browser contexts from a pool, applies rate limiting, and
        handles retries with backoff.

        Args:
            url (str): The URL to fetch.
            scroll_page (bool): If True, attempts to scroll the page to load
                dynamically appearing content. Defaults to False.

        Returns:
            Dict[str, str]: A dictionary containing:
                - "original_url" (str): The URL initially requested.
                - "final_url" (str): The URL after any redirects.
                - "content" (str): The page's HTML content, or an empty string
                  if fetching failed.
                - "error" (str): An error message if an error occurred, otherwise
                  an empty string.

        Side Effects:
            - Acquires and returns a browser context from the pool.
            - Navigates a browser page to the URL.
            - Potentially scrolls the page.
            - Logs fetching attempts, successes, errors, and retries.
        """
        await self._enforce_domain_rate_limit(url)

        if (
            not self._browser_initialized
            or not self.browser
            or not self.browser.is_connected()
        ):
            await self._ensure_browser_started()
            if not self.browser or not self.browser.is_connected():
                logger.error("Browser is not initialized or not connected for fetch.")
                return {
                    "original_url": url,
                    "final_url": url,
                    "content": "",
                    "error": "Browser initialization failed prior to fetch",
                }

        html_content = ""
        error_message = ""
        final_url = url
        fetch_start_time = time.time()

        logger.info(f"Starting Playwright fetch for {url}")
        context_item: Optional[Dict[str, Any]] = None
        page: Optional[Page] = None

        for attempt in range(self.max_retries):
            try:
                if (
                    not context_item
                ):  # Get context only if needed (e.g., after recovery).
                    context_item = await self._get_context_from_pool()

                page = await context_item["context"].new_page()
                if page:
                    page.set_default_timeout(self.page_timeout)

                    # Block common resource types to speed up loading.
                    await page.route(
                        "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}",
                        lambda route: route.abort(),
                    )

                    await page.goto(
                        url, wait_until="domcontentloaded", timeout=self.page_timeout
                    )
                else:
                    raise PlaywrightError("Failed to create page")
                final_url = page.url  # URL after potential redirects.

                if scroll_page:
                    await self._scroll_page(page)

                try:
                    # Wait for network to be idle for a short period.
                    await page.wait_for_load_state("networkidle", timeout=30000)
                except PlaywrightTimeoutError:
                    logger.warning(
                        f"Network idle wait timed out for {final_url}. Continuing."
                    )
                except PlaywrightError as e:
                    logger.warning(
                        f"Network idle wait failed for {final_url}: {e}. Continuing."
                    )

                html_content = await page.content()
                fetch_duration = time.time() - fetch_start_time
                logger.info(
                    f"[Worker] Successfully fetched (Playwright): {final_url} in {fetch_duration:.2f} seconds"
                )
                error_message = ""  # Clear previous error on success.
                break  # Success.

            except PlaywrightTimeoutError as e:
                error_message = f"Timeout error for {url}: {str(e).splitlines()[0]}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )
            except PlaywrightError as e:
                error_message = f"Playwright error for {url}: {str(e).splitlines()[0]}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )
                # Handle cases where browser/context might have crashed.
                if "Target closed" in str(e) or "Browser closed" in str(e):
                    logger.warning("Browser connection lost, attempting to recover...")
                    self._browser_initialized = False  # Force re-check/re-init.
                    try:
                        await self._ensure_browser_started()
                        context_item = None  # Force getting a new context on retry.
                    except Exception as init_err:
                        logger.error(f"Failed to recover browser: {init_err}")
                        # If recovery fails, likely subsequent attempts will also fail.
            except Exception as e:
                error_message = f"Unexpected error for {url}: {e}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )
            finally:
                if page:
                    try:
                        if not page.is_closed():
                            await page.close()
                    except Exception as e:
                        logger.warning(f"Error closing page for {url}: {e}")
                    page = None  # Ensure page is reset for next attempt or release.

            if attempt < self.max_retries - 1:
                backoff = calculate_backoff(attempt)
                logger.info(
                    f"Retrying {url} in {backoff:.2f} seconds (attempt {attempt+1}/{self.max_retries})"
                )
                await asyncio.sleep(backoff)

        if context_item:
            await self._return_context_to_pool(context_item)

        if error_message:  # Log final failure.
            fetch_duration = time.time() - fetch_start_time
            logger.error(
                f"Failed to process {url} with Playwright after {self.max_retries} attempts, took {fetch_duration:.2f} seconds."
            )

        result = {
            "original_url": url,
            "final_url": final_url,
            "content": html_content,
            "error": error_message,
        }
        return result

    async def _scroll_page(
        self, page: Page, scroll_delay: float = 0.3, max_scrolls: int = 5
    ) -> None:
        """Scrolls the page to trigger loading of dynamic content.

        Args:
            page (Page): The Playwright page object to scroll.
            scroll_delay (float): Delay in seconds between scrolls.
            max_scrolls (int): Maximum number of scroll attempts.

        Side Effects:
            - Executes JavaScript on the page to scroll.
            - May `await asyncio.sleep()`.
            - Logs scrolling activity or failures.
        """
        try:
            last_height = await page.evaluate("document.body.scrollHeight")
            scroll_count = 0
            same_height_count = 0
            MAX_SAME_HEIGHT = 2  # Stop if height doesn't change for this many scrolls.

            while scroll_count < max_scrolls:
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(scroll_delay)
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    same_height_count += 1
                    if same_height_count >= MAX_SAME_HEIGHT:
                        break
                else:
                    same_height_count = 0
                last_height = new_height
                scroll_count += 1
        except PlaywrightError as e:
            logger.warning(f"Scrolling failed for {page.url}: {e}")
        except Exception as e:  # Catch any other unexpected error during scroll.
            logger.warning(f"Unexpected error during scrolling for {page.url}: {e}")

    async def process_urls(
        self,
        urls: List[str],
        scroll_pages: bool = False,
        batch_size: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Processes a list of URLs using Playwright and yields results.

        Args:
            urls (List[str]): A list of URLs to fetch.
            scroll_pages (bool): If True, attempts to scroll pages during fetching.
                Defaults to False.
            batch_size (Optional[int]): The number of URLs to process in each
                concurrent batch. If None, defaults to a value based on
                `context_pool_size`.

        Yields:
            Dict[str, str]: A dictionary for each processed URL, containing
                "original_url", "final_url", "content", and "error" keys.

        Side Effects:
            - Ensures the browser and context pool are initialized.
            - Creates and manages multiple asyncio tasks for fetching URLs.
            - Logs progress, errors, and task execution details.
        """
        if not urls:
            return

        if not self.browser or not self.browser.is_connected():
            await self._ensure_browser_started()

        if batch_size is None:
            batch_size = min(len(urls), self.context_pool_size * 2)

        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            tasks = [
                asyncio.create_task(
                    self.fetch_single(url, scroll_pages), name=f"fetch_{url[:50]}"
                )
                for url in batch
            ]

            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    yield result
                    if result.get("error"):
                        logger.warning(
                            f"Error processing URL {result.get('original_url', 'unknown')} with Playwright: {result['error']}"
                        )
                except Exception as e:
                    task_name = (
                        future.get_name()
                        if isinstance(future, asyncio.Task)
                        else "unknown_task"
                    )
                    logger.error(
                        f"Playwright Task {task_name} raised an unexpected exception: {e}",
                        exc_info=True,
                    )
                    original_url = (
                        task_name.replace("fetch_", "")
                        if task_name.startswith("fetch_")
                        else "unknown_url"
                    )
                    yield {
                        "original_url": original_url,
                        "final_url": original_url,
                        "content": "",
                        "error": f"Playwright task execution failed: {e}",
                    }
            # Small pause between batches.
            if i + batch_size < len(urls):
                await asyncio.sleep(0.5)


class SeleniumCrawler:
    """
    Asynchronous web crawler using Selenium WebDriver for fetching HTML content.

    This crawler uses Selenium with a headless Chrome browser to render web pages,
    making it suitable for sites that require JavaScript execution. It manages a
    pool of WebDriver instances for concurrent operations and includes features
    like user-agent rotation and retry mechanisms.

    Attributes:
        headless (bool): Whether to run Chrome in headless mode.
        page_timeout (int): Timeout in seconds for page load operations.
        max_retries (int): Maximum retry attempts for fetching a URL.
        browser_args (Dict[str, Any]): Arguments for configuring Chrome options.
        user_agent (Optional[str]): Specific user agent if rotation is off.
        user_agent_rotation (bool): Whether to rotate user agents.
        driver_pool (List[Dict[str, Any]]): Pool of WebDriver instances.
        domain_timestamps (Dict[str, float]): Tracks last access time per domain.
        domain_locks (Dict[str, asyncio.Lock]): Locks for per-domain rate limiting.
        user_agents (List[str]): List of user agents for rotation.

    Examples:
        >>> async def main():
        ...     urls_to_crawl = ["https://example.com/js-heavy-site"]
        ...     async with SeleniumCrawler() as crawler:
        ...         async for result in crawler.process_urls(urls_to_crawl):
        ...             # Process result
        ...             pass
        # To run the example: asyncio.run(main())
    """

    def __init__(
        self,
        headless: bool = True,
        max_concurrent_browsers: int = DEFAULT_MAX_CONCURRENT_REQUESTS // 2,
        page_timeout: int = 10,  # seconds
        browser_args: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        user_agent_rotation: bool = True,
        max_retries: int = DEFAULT_MAX_RETRY_ATTEMPTS,
    ):
        """Initializes the SeleniumCrawler.

        Args:
            headless (bool): If True, runs Chrome in headless mode. Defaults to True.
            max_concurrent_browsers (int): Maximum number of WebDriver instances
                to use concurrently. Defaults to half of
                `DEFAULT_MAX_CONCURRENT_REQUESTS`.
            page_timeout (int): Timeout in seconds for page load operations.
                Defaults to 10.
            browser_args (Optional[Dict[str, Any]]): Additional arguments for
                Chrome options (e.g., `{"args": ["--incognito"]}`).
            user_agent (Optional[str]): A specific User-Agent string.
            user_agent_rotation (bool): If True, rotates User-Agent strings.
                Defaults to True.
            max_retries (int): Maximum retry attempts for fetching a URL.
                Defaults to `DEFAULT_MAX_RETRY_ATTEMPTS`.

        Side Effects:
            - Initializes configuration attributes.
            - Sets up internal structures for WebDriver pooling, rate limiting,
              and user agents.
        """
        self.headless = headless
        self.page_timeout = page_timeout
        self.max_retries = max_retries
        self.browser_args = browser_args or {}
        self.user_agent = user_agent
        self.user_agent_rotation = user_agent_rotation

        self.driver_pool: List[Dict[str, Any]] = []
        self.driver_pool_size = max_concurrent_browsers
        self.driver_pool_lock = asyncio.Lock()

        self.domain_timestamps: Dict[str, float] = {}
        self.domain_locks: Dict[str, asyncio.Lock] = {}

        self.user_agents: List[str] = self._initialize_user_agents(user_agent)
        self._start_lock = asyncio.Lock()  # Lock for initializing driver pool.

    async def __aenter__(self) -> "SeleniumCrawler":
        """Enters the asynchronous context, ensuring the driver pool is started.

        Returns:
            SeleniumCrawler: The instance of the crawler.

        Side Effects:
            - Calls `self._ensure_driver_pool_started()`.
        """
        await self._ensure_driver_pool_started()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Exits the asynchronous context, ensuring WebDriver resources are shut down.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of exception raised, if any.
            exc_val (Optional[BaseException]): The exception instance raised, if any.
            exc_tb (Optional[Any]): The traceback object, if any.

        Returns:
            bool: False, indicating that exceptions (if any) should not be suppressed.

        Side Effects:
            - Calls `self.shutdown()`.
        """
        await self.shutdown()
        return False

    def _initialize_user_agents(self, default_user_agent: Optional[str]) -> List[str]:
        """Initializes a list of User-Agent strings for rotation.

        (Identical to PlaywrightCrawler's implementation.)

        Args:
            default_user_agent (Optional[str]): A specific user agent to include.

        Returns:
            List[str]: A list of User-Agent strings.
        """
        common_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51",
        ]
        if default_user_agent:
            return [default_user_agent] + common_user_agents
        default = "SmartInfo/1.0 (Selenium)"
        return [default] + common_user_agents

    def _get_random_user_agent(self) -> str:
        """Selects a User-Agent string.

        (Identical to PlaywrightCrawler's implementation.)

        Returns:
            str: A User-Agent string.
        """
        if not self.user_agent_rotation or len(self.user_agents) <= 1:
            return self.user_agents[0]
        return random.choice(self.user_agents)

    def _create_chrome_options(self, user_agent: Optional[str] = None) -> Options:
        """Creates and configures Selenium Chrome options.

        Sets headless mode, user agent, and various performance/stability flags.

        Args:
            user_agent (Optional[str]): The User-Agent string to set. If None,
                a default or rotated agent might be used by the caller.

        Returns:
            Options: Configured Selenium Chrome options.
        """
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")

        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        # Disable images, cookies for performance if not needed.
        options.add_experimental_option(
            "prefs",
            {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.cookies": 2,
            },
        )
        if self.browser_args:
            for arg in self.browser_args.get("args", []):
                options.add_argument(arg)
        return options

    async def _create_driver(self) -> webdriver.Chrome:
        """Creates a new Selenium Chrome WebDriver instance asynchronously.

        Uses `asyncio.to_thread` to run the blocking WebDriver instantiation
        in a separate thread.

        Returns:
            webdriver.Chrome: The initialized WebDriver instance.

        Side Effects:
            - Installs/manages ChromeDriver via `ChromeDriverManager`.
            - Starts a Chrome browser process.
            - Sets page load and implicit wait timeouts on the driver.
        """
        user_agent = self._get_random_user_agent()
        options = self._create_chrome_options(user_agent)
        # Run blocking webdriver.Chrome in a separate thread.
        create_driver_func = functools.partial(
            webdriver.Chrome,
            options=options,
            service=Service(ChromeDriverManager().install()),
        )
        driver = await asyncio.to_thread(create_driver_func)
        driver.set_page_load_timeout(self.page_timeout)
        driver.implicitly_wait(self.page_timeout)  # Implicit wait for elements.
        return driver

    async def _ensure_driver_pool_started(self) -> None:
        """Ensures the WebDriver pool is initialized, using a lock.

        Lazily initializes the pool by creating a few WebDriver instances if
        the pool is empty.

        Raises:
            RuntimeError: If WebDriver creation fails during initialization.

        Side Effects:
            - If the pool is empty:
                - Creates WebDriver instances up to `min(2, self.driver_pool_size)`.
                - Populates `self.driver_pool`.
            - Logs initialization details.
        """
        async with self._start_lock:
            if not self.driver_pool:  # Initialize only if pool is empty.
                logger.info(
                    f"Initializing Selenium driver pool with up to {self.driver_pool_size} drivers."
                )
                # Start with a small number of drivers, can grow up to pool_size if needed.
                for _ in range(min(2, self.driver_pool_size)):
                    try:
                        driver = await self._create_driver()
                        self.driver_pool.append(
                            {
                                "driver": driver,
                                "in_use": False,
                                "user_agent": self._get_random_user_agent(),  # Store agent used.
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error creating WebDriver for pool: {e}")
                        # If initial drivers fail, it's a critical issue.
                        raise RuntimeError(f"Failed to initialize WebDriver pool: {e}")

    async def _get_driver_from_pool(self) -> Dict[str, Any]:
        """Retrieves an available WebDriver instance from the pool.

        If the pool is exhausted but below its maximum size, a new driver is
        created. If the pool is full, it reuses the first available driver
        (this part might need refinement for true pooling behavior with waiting).

        Returns:
            Dict[str, Any]: A dictionary representing the acquired driver item.

        Raises:
            RuntimeError: If creating a new WebDriver fails.

        Side Effects:
            - Marks a driver in `self.driver_pool` as "in_use".
            - May create and add a new WebDriver instance to the pool.
        """
        async with self.driver_pool_lock:
            for item in self.driver_pool:
                if not item["in_use"]:
                    item["in_use"] = True
                    return item

            if len(self.driver_pool) < self.driver_pool_size:
                try:
                    driver = await self._create_driver()
                    new_item = {
                        "driver": driver,
                        "in_use": True,
                        "user_agent": self._get_random_user_agent(),
                    }
                    self.driver_pool.append(new_item)
                    return new_item
                except Exception as e:
                    logger.error(f"Error creating new driver for pool: {e}")
                    raise RuntimeError(f"Failed to create new WebDriver for pool: {e}")

            logger.info("All drivers in pool are in use, reusing the first one.")
            # Fallback: if pool is full, reuse the first one.
            # This isn't true pooling with waiting, consider semaphore if strict limits are needed.
            if (
                self.driver_pool
            ):  # Should not be empty if _ensure_driver_pool_started worked.
                self.driver_pool[0]["in_use"] = True
                return self.driver_pool[0]
            else:  # Should not happen.
                raise RuntimeError(
                    "Driver pool is unexpectedly empty after initialization."
                )

    async def _return_driver_to_pool(self, driver_item: Dict[str, Any]) -> None:
        """Returns a WebDriver instance to the pool.

        Args:
            driver_item (Dict[str, Any]): The driver item dictionary.

        Side Effects:
            - Marks the driver in `self.driver_pool` as "in_use": False.
        """
        async with self.driver_pool_lock:
            for item in self.driver_pool:
                if item["driver"] == driver_item["driver"]:
                    item["in_use"] = False
                    break

    async def _enforce_domain_rate_limit(self, url: str) -> None:
        """Enforces a rate limit for requests to the same domain.

        (Identical to AiohttpCrawler's implementation.)

        Args:
            url (str): The URL for which to enforce the rate limit.

        Side Effects:
            - May `await asyncio.sleep()`.
            - Updates `self.domain_timestamps`.
        """
        domain = urlparse(url).netloc
        lock = self.domain_locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self.domain_locks[domain] = lock

        async with lock:
            last_access = self.domain_timestamps.get(domain, 0)
            now = time.time()
            if now - last_access < 1.0:  # 1 second delay.
                delay = 1.0 - (now - last_access)
                await asyncio.sleep(delay)
            self.domain_timestamps[domain] = time.time()

    async def _scroll_page(
        self, driver: webdriver.Chrome, scroll_delay: float = 0.3, max_scrolls: int = 5
    ) -> None:
        """Scrolls the page using Selenium to load dynamic content.

        Args:
            driver (webdriver.Chrome): The Selenium WebDriver instance.
            scroll_delay (float): Delay in seconds between scrolls.
            max_scrolls (int): Maximum number of scroll attempts.

        Side Effects:
            - Executes JavaScript on the page to scroll.
            - May `await asyncio.sleep()`.
            - Logs scrolling activity or failures.
        """
        try:
            # JavaScript to scroll and return current scroll height.
            scroll_script = """
            function scrollDown() {
                window.scrollBy(0, window.innerHeight);
                return document.body.scrollHeight;
            }
            return scrollDown();
            """
            # Run blocking Selenium calls in a separate thread.
            scroll_func = functools.partial(driver.execute_script, scroll_script)
            last_height = await asyncio.to_thread(scroll_func)
            scroll_count = 0
            same_height_count = 0
            MAX_SAME_HEIGHT = 2

            while scroll_count < max_scrolls:
                new_height = await asyncio.to_thread(scroll_func)
                await asyncio.sleep(scroll_delay)  # Give time for content to load.
                if new_height == last_height:
                    same_height_count += 1
                    if same_height_count >= MAX_SAME_HEIGHT:
                        break
                else:
                    same_height_count = 0
                last_height = new_height
                scroll_count += 1
        except Exception as e:
            logger.warning(f"Scrolling failed for current page: {e}")

    async def fetch_single(
        self,
        url: str,
        scroll_page: bool = False,
    ) -> Dict[str, str]:
        """Fetches the raw HTML of a single URL using Selenium.

        Manages WebDriver instances from a pool, applies rate limiting, and
        handles retries.

        Args:
            url (str): The URL to fetch.
            scroll_page (bool): If True, attempts to scroll the page.
                Defaults to False.

        Returns:
            Dict[str, str]: A dictionary with "original_url", "final_url",
                "content", and "error" keys.

        Side Effects:
            - Acquires and returns a WebDriver instance from the pool.
            - Navigates the browser to the URL.
            - Potentially scrolls the page.
            - Logs fetching details and errors.
        """
        await self._enforce_domain_rate_limit(url)

        html_content = ""
        error_message = ""
        final_url = url
        fetch_start_time = time.time()

        await self._ensure_driver_pool_started()  # Ensure pool is ready.
        driver_item: Optional[Dict[str, Any]] = None

        for attempt in range(self.max_retries):
            try:
                if not driver_item:  # Get driver only if needed.
                    driver_item = await self._get_driver_from_pool()
                driver = driver_item["driver"]

                # Run blocking Selenium calls in a separate thread.
                get_url_func = functools.partial(driver.get, url)
                await asyncio.to_thread(get_url_func)

                get_current_url_func = functools.partial(lambda: driver.current_url)
                final_url = await asyncio.to_thread(get_current_url_func)

                if scroll_page:
                    await self._scroll_page(driver)
                    await asyncio.sleep(1)  # Additional wait after scrolling.

                try:
                    # Wait for document.readyState to be 'complete'.
                    wait_func = functools.partial(
                        WebDriverWait(driver, self.page_timeout).until,
                        lambda d: d.execute_script("return document.readyState")
                        == "complete",
                    )
                    await asyncio.to_thread(wait_func)
                except TimeoutException:
                    logger.warning(
                        f"Timeout waiting for page to load completely: {url}"
                    )

                get_source_func = functools.partial(lambda: driver.page_source)
                html_content = await asyncio.to_thread(get_source_func)
                fetch_duration = time.time() - fetch_start_time
                logger.info(
                    f"[Worker] Successfully fetched (Selenium): {final_url} in {fetch_duration:.2f} seconds"
                )
                error_message = ""
                break  # Success.

            except TimeoutException as e:
                error_message = f"Timeout error for {url}: {e}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )
            except WebDriverException as e:
                error_message = f"WebDriver error for {url}: {str(e).splitlines()[0]}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )
                if "chrome not reachable" in str(e).lower() and driver_item:
                    logger.warning(
                        "WebDriver connection lost, attempting to recover by replacing driver..."
                    )
                    try:
                        await asyncio.to_thread(driver_item["driver"].quit)
                    except:
                        pass  # Ignore errors if already crashed.
                    async with self.driver_pool_lock:  # Safely remove from pool.
                        self.driver_pool = [
                            item
                            for item in self.driver_pool
                            if item["driver"] != driver_item["driver"]
                        ]
                    driver_item = None  # Force getting a new driver on retry.
            except Exception as e:
                error_message = f"Unexpected error for {url}: {e}"
                logger.error(
                    f"{error_message} (Attempt {attempt+1}/{self.max_retries})"
                )

            if attempt < self.max_retries - 1:
                backoff = calculate_backoff(attempt)
                logger.info(
                    f"Retrying {url} with Selenium in {backoff:.2f} seconds (attempt {attempt+1}/{self.max_retries})"
                )
                await asyncio.sleep(backoff)

        if driver_item:
            await self._return_driver_to_pool(driver_item)

        if error_message:
            fetch_duration = time.time() - fetch_start_time
            logger.error(
                f"Failed to process {url} with Selenium after {self.max_retries} attempts, took {fetch_duration:.2f} seconds."
            )

        result = {
            "original_url": url,
            "final_url": final_url,
            "content": html_content,
            "error": error_message,
        }
        return result

    async def process_urls(
        self,
        urls: List[str],
        scroll_pages: bool = False,
        batch_size: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, str], None]:
        """Processes a list of URLs using Selenium and yields results.

        Args:
            urls (List[str]): A list of URLs to fetch.
            scroll_pages (bool): If True, attempts to scroll pages. Defaults to False.
            batch_size (Optional[int]): Number of URLs per concurrent batch.
                Defaults to a value based on `driver_pool_size`.

        Yields:
            Dict[str, str]: A dictionary for each URL, with "original_url",
                "final_url", "content", and "error" keys.

        Side Effects:
            - Ensures the driver pool is initialized.
            - Manages asyncio tasks for fetching.
            - Logs progress and errors.
        """
        if not urls:
            return
        await self._ensure_driver_pool_started()
        if batch_size is None:
            batch_size = min(len(urls), self.driver_pool_size * 2)

        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            tasks = [
                asyncio.create_task(
                    self.fetch_single(url, scroll_pages), name=f"fetch_sel_{url[:45]}"
                )
                for url in batch
            ]
            for future in asyncio.as_completed(tasks):
                try:
                    result = await future
                    yield result
                    if result.get("error"):
                        logger.warning(
                            f"Error processing URL {result.get('original_url', 'unknown')} with Selenium: {result['error']}"
                        )
                except Exception as e:
                    task_name = (
                        future.get_name()
                        if isinstance(future, asyncio.Task)
                        else "unknown_task"
                    )
                    logger.error(
                        f"Selenium Task {task_name} raised an unexpected exception: {e}",
                        exc_info=True,
                    )
                    original_url = (
                        task_name.replace("fetch_sel_", "")
                        if task_name.startswith("fetch_sel_")
                        else "unknown_url"
                    )
                    yield {
                        "original_url": original_url,
                        "final_url": original_url,
                        "content": "",
                        "error": f"Selenium task execution failed: {e}",
                    }
            if i + batch_size < len(urls):
                await asyncio.sleep(0.5)

    async def shutdown(self) -> None:
        """Closes all WebDriver instances in the pool.

        This method should be called to release all Selenium resources.
        It is idempotent.

        Side Effects:
            - Quits each WebDriver instance in `self.driver_pool`.
            - Clears `self.driver_pool`.
            - Logs shutdown process and any errors.
        """
        logger.info("Shutting down SeleniumCrawler...")
        async with self._start_lock:  # Ensure exclusive access during shutdown.
            if hasattr(self, "driver_pool") and self.driver_pool:
                for item in self.driver_pool:
                    try:
                        # Run blocking driver.quit() in a separate thread.
                        quit_func = functools.partial(item["driver"].quit)
                        await asyncio.to_thread(quit_func)
                        logger.info("WebDriver instance closed.")
                    except Exception as e:
                        logger.error(f"Error closing WebDriver instance: {e}")
                self.driver_pool = []
        logger.info("SeleniumCrawler shutdown complete.")
