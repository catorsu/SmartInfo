# SmartInfo Backend: LLM Integration Guide

## 1. Introduction

Large Language Models (LLMs) are a core component of SmartInfo, providing capabilities such as article summarization, title generation, in-depth content analysis, and powering the conversational chat interface. This guide details how the backend integrates with LLM APIs, manages configurations, and utilizes system prompts.

Understanding this integration is crucial for developers and AI assistants working on features that leverage LLM capabilities or need to modify existing LLM interactions.

## 2. Core LLM Client Architecture

The backend uses a modular approach for interacting with LLMs, designed to be compatible with OpenAI-compatible APIs (e.g., OpenAI, DeepSeek, VolcEngine).

### 2.1. LLM Clients (`core/llm/client.py`)
*   **`LLMClientBase`:** An abstract base class defining the common interface for both synchronous and asynchronous LLM clients.
*   **`AsyncLLMClient`:** The primary client used for asynchronous interactions with LLM APIs. It wraps the `openai.AsyncOpenAI` client, providing methods for:
    *   `get_completion_content()`: For non-streaming, full responses.
    *   `stream_completion_content()`: For streaming responses.
    It handles API request parameters (model, messages, temperature, max_tokens, etc.) and includes built-in retry mechanisms for transient API errors (e.g., rate limits, timeouts) via the underlying `openai` library.
*   **`SyncLLMClient`:** A synchronous counterpart, wrapping `openai.OpenAI`. Less frequently used in the primarily asynchronous backend but available if needed for specific synchronous contexts.

### 2.2. LLM Client Pool (`core/llm/pool.py`)
*   **`LLMClientPool`:** Manages a pool of `AsyncLLMClient` instances.
    *   **Purpose:** Efficiently reuses LLM client connections, especially important for concurrent operations like those in Celery background tasks where multiple news sources or articles might be processed in parallel.
    *   **Functionality:**
        *   Lazy initialization of a configured number of `AsyncLLMClient` instances.
        *   Provides an `asynccontextmanager` (`pool.context()`) for acquiring a client from the pool and automatically releasing it.
        *   Direct convenience methods (`pool.get_completion_content()`, `pool.stream_completion_content()`) that handle client acquisition and release.
    *   **Instantiation:** Typically instantiated by services or tasks that need to make LLM calls, configured with user-specific API key details.

## 3. API Key Management

SmartInfo allows users to configure their own LLM API keys, providing flexibility in choosing LLM providers and models.

*   **Storage:** User-specific API key configurations are stored securely in the `api_config` database table. Each record includes:
    *   `model`: The model name (e.g., "deepseek-chat").
    *   `base_url`: The API endpoint base URL.
    *   `api_key`: The user's actual API key (Note: Stored as TEXT. Future enhancement: encrypt at rest).
    *   `context`: The model's context window size.
    *   `max_output_tokens`: The maximum number of tokens the model should generate.
    *   `description`: User-provided description.
    *   `user_id`: Foreign key to the `users` table.
*   **Repository:** `db/repositories/api_key_repository.py` (`ApiKeyRepository`) handles all CRUD operations for these configurations.
*   **Usage by Services:**
    *   Services like `ChatService`, `NewsService`, or Celery tasks (e.g., in `news_tasks.py` via `_get_user_llm_pool`) that need to interact with an LLM for a specific user will:
        1.  Fetch the user's API key configurations from the `ApiKeyRepository` using the `user_id`.
        2.  Typically, select the first valid/active configuration (future enhancement: allow user to select a default or preferred key).
        3.  Instantiate an `AsyncLLMClient` (or an `LLMClientPool` if multiple concurrent calls are anticipated for that user within the task) with the fetched `base_url`, `api_key`, `model`, etc.
*   **Security:** API keys are sensitive. They are tied to a user and should only be accessible and used by operations performed on behalf of that authenticated user.

## 4. System Prompts (`utils/prompt.py`)

System prompts define the role, goal, instructions, and output format for the LLM for specific tasks. They are crucial for guiding the LLM to produce desired results.

---
**Prompt Catalog:**

*   **1. `SYSTEM_PROMPT_EXTRACT_ARTICLE_LINKS`**
    *   **Purpose:** Instructs the LLM to act as a "Deep Reading Link Extraction Assistant." It identifies and extracts URLs of in-depth articles or detailed blog posts from a given Markdown document, filtering out navigation links, ads, author profiles, etc.
    *   **Key Instructions/Heuristics Summary:**
        *   Select links to full-length articles, tutorials, research papers.
        *   Exclude homepages, ads, navigation pages, listicles.
        *   Prefer links with deeper path segments.
        *   Expand relative links using the provided Base URL.
    *   **Expected Input to LLM (User Prompt Structure):**
        ```
        <Base URL>
        {base_url_of_the_source_page}
        </Base URL>
        <Markdown content>
        {markdown_content_of_the_source_page}
        </Markdown content>
        ```
    *   **Expected LLM Output Format:** Plain text, one URL per line. No Markdown, JSON, or commentary. If no suitable links are found, output is exactly "no".
    *   **Primary Consumer(s):** `core.workflow.news_fetch.fetch_news` (specifically, the `_extract_and_crawl_links` internal function).
    *   **Parsing Logic:** The output string is split by newlines. Each line is stripped of whitespace and validated as a URL. Relative URLs are joined with the base URL.

*   **2. `SYSTEM_PROMPT_EXTRACT_SUMMARIZE_ARTICLE_BATCH`**
    *   **Purpose:** Instructs the LLM to act as an "intelligent content summarization and title generation assistant." Given a series of articles (each with original title, URL, date, and full content), it generates a new fact-based title and a concise, detailed summary for each.
    *   **Key Instructions/Heuristics Summary:**
        *   Skip non-substantive articles.
        *   Generate a *new* fact-based title (not a copy of the original) avoiding exaggeration or clickbait.
        *   Write a detailed summary (150-200 words) covering core messages, context, evidence, implications.
        *   Preserve the original language of the article (English/Chinese).
    *   **Expected Input to LLM (User Prompt Structure):** A concatenated string of multiple article blocks:
        ```
        <Article>
        Title: {original_article_title_1}
        Url: {article_url_1}
        Date: {article_date_1}
        Content:
        {full_article_content_1}
        </Article>

        <Article>
        Title: {original_article_title_2}
        Url: {article_url_2}
        Date: {article_date_2}
        Content:
        {full_article_content_2}
        </Article>
        ...
        Please summarize each article in Markdown format, following the structure and style shown above.
        ```
    *   **Expected LLM Output Format:** A single JSON array. Each element in the array is an object with three keys: `"url"` (string), `"title"` (string - the newly generated title), and `"summary"` (string).
    *   **Primary Consumer(s):** `core.workflow.news_fetch.fetch_news` (specifically, the `summarize_content` internal function).
    *   **Parsing Logic:** `utils.parse.parse_json_from_text` is used to extract the JSON array from the LLM's response (which might be enclosed in Markdown code fences ```json ... ```).

*   **3. `SYSTEM_PROMPT_ANALYZE_CONTENT`**
    *   **Purpose:** Instructs the LLM to act as an "expert content analyst." It performs a deep analysis of provided content, surfacing its essence, context, implications, and actionable insights.
    *   **Key Instructions/Heuristics Summary:**
        *   Identify core themes, key actors.
        *   Explore background, context, potential impacts, multiple perspectives.
        *   Draw conclusions, offer recommendations.
        *   Adjust analysis points based on content complexity.
        *   Write in the same language as the original content.
        *   Present in plain text, clear paragraphs, first line indented.
    *   **Expected Input to LLM (User Prompt Structure):**
        ```
        Please analyze the following news content:
        """
        {full_news_item_content}
        """
        **Write in the same language as the original content** ...
        ```
        (The service layer (`NewsService.stream_analysis_for_news_item`) constructs this user prompt.)
    *   **Expected LLM Output Format:** Plain text, structured into clear paragraphs with the first line of each indented.
    *   **Primary Consumer(s):** `NewsService.stream_analysis_for_news_item` (for analyzing specific news items) and potentially `NewsService.analyze_content_streaming` (for arbitrary content, though this endpoint seems less used currently).
    *   **Parsing Logic:** The output is typically treated as plain text. If streamed, chunks are concatenated.

---

## 5. LLM Interaction Patterns

SmartInfo primarily uses two modes of interaction with LLMs via `AsyncLLMClient`:

### 5.1. Non-Streaming (`client.get_completion_content()`)
*   **Usage:** When a complete, single response from the LLM is required before proceeding.
*   **Examples in SmartInfo:**
    *   Extracting article links from a source page (`_extract_and_crawl_links` in `news_fetch.py`).
    *   Generating titles and summaries for a batch of articles (`summarize_content` in `news_fetch.py`).
*   **Process:** The application sends the full prompt and waits for the entire LLM response.

### 5.2. Streaming (`client.stream_completion_content()`)
*   **Usage:** When the LLM response is expected to be long, and providing incremental updates to the user (or for further processing) is beneficial.
*   **Examples in SmartInfo:**
    *   Chat responses in `/api/chat/ask` (via `ChatService.process_question`).
    *   Live analysis of a news item in `/api/news/items/{news_id}/analyze/stream` (via `NewsService.stream_analysis_for_news_item`).
*   **Process:** The application receives the LLM response as a stream of text chunks, which can be immediately sent to the client or processed incrementally.

## 6. Error Handling for LLM Calls

*   The `AsyncLLMClient` (and the underlying `openai` library) handles retries for common transient API errors such as:
    *   `RateLimitError`
    *   `APITimeoutError`
    *   `APIConnectionError`
*   If retries are exhausted or a non-retryable error occurs (e.g., `APIError` for authentication issues, invalid requests), the client will raise these exceptions.
*   **Calling Services/Workflows are responsible for:**
    *   Catching these exceptions.
    *   Logging the error appropriately.
    *   Handling the error gracefully (e.g., returning an error message to the user, marking a task as failed, skipping an item in a batch).
    *   For example, in `ChatService.process_question`, an error during LLM streaming results in an error message being yielded to the client and logged.

## 7. Token Management and Context Windows

*   **Configuration:** Each user's API key configuration (`api_config` table) stores:
    *   `context`: The maximum context window (input + output tokens) supported by the configured model.
    *   `max_output_tokens`: The maximum number of tokens the LLM is requested to generate in a response.
    These values are passed to the `AsyncLLMClient` upon instantiation.
*   **Token Calculation:** `utils.token_utils.get_token_size(text, model_type)` is available to estimate the token count of a given text, primarily for "deepseek" models currently. This can be used to:
    *   Check if a prompt is likely to exceed the model's context window.
    *   Inform decisions about chunking large content.
*   **Handling Large Inputs:**
    *   The `core.workflow.news_fetch.fetch_news` workflow demonstrates a strategy for handling large content:
        *   If the Markdown content of a source page is too large for link extraction, it's chunked using `utils.text_utils.get_chunks`.
        *   If the combined content of multiple articles is too large for batch summarization, the articles are grouped into smaller chunks for the LLM.
    *   This ensures that prompts do not exceed the `max_input_tokens` (calculated as `context - max_output_tokens`) of the LLM client.

## 8. Adding New LLM-Powered Features

When integrating new LLM-driven functionalities:

1.  **Define the Task & LLM Role:** Clearly articulate what the LLM needs to do.
2.  **Create a System Prompt:**
    *   Add a new constant to `utils/prompt.py` (e.g., `SYSTEM_PROMPT_NEW_FEATURE_X`).
    *   Follow the guidelines in this document for prompt content: clear role, goal, detailed instructions, input/output format examples.
3.  **Update this Guide:** Add an entry for your new prompt in the "Prompt Catalog" section of this `LLM_INTEGRATION_GUIDE.md`.
4.  **Develop Service Logic:**
    *   Implement the logic in the relevant service to:
        *   Retrieve user API key(s) and instantiate an `AsyncLLMClient` or use the `LLMClientPool`.
        *   Construct the user part of the prompt dynamically based on input data.
        *   Call the appropriate `AsyncLLMClient` method (`get_completion_content` or `stream_completion_content`).
        *   Parse and validate the LLM's response according to the expected output format defined in your system prompt.
        *   Handle potential errors gracefully.
5.  **Token Considerations:** Be mindful of token limits. Implement chunking or other strategies if input data can be large. Use `get_token_size` for estimations.
6.  **Testing:**
    *   Unit test your service logic by mocking the `AsyncLLMClient` calls.
    *   Provide mock LLM responses that cover successful outputs and potential error/malformed outputs to test your parsing and error handling.
