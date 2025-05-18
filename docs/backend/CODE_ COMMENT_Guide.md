# SmartInfo Backend: Code Commenting Guide

## 1. Introduction

This guide provides the official standards and best practices for writing code comments and docstrings within the SmartInfo backend Python codebase.

Adherence to this guide is expected for all new and modified code.

## 2. Guiding Principles

1.  **Clarity & Precision:** Use unambiguous language. Be explicit about intent, assumptions, and behavior.
2.  **Purpose over Mechanics:** Code describes *what* it does. Comments explain *why* it does it, the rationale behind non-obvious choices, and the broader context.
3.  **Define Contracts:** Docstrings for public interfaces (modules, classes, functions/methods) are contracts. They must detail purpose, arguments, return values, exceptions, and side effects.
4.  **Consistency:** Follow the specified formats (PEP 8, PEP 257, Google Style Docstrings) and terminology consistently.
5.  **Up-to-Date:** Comments **MUST** be kept synchronized with the code they describe. Outdated comments are misleading and harmful.
6.  **Type Hinting is Integral:** This guide assumes mandatory and accurate type hinting (PEP 484) as a foundational part of code documentation.

## 3. General Commenting Rules (PEP 8 Alignment)

*   **Line Length:** Comments and docstrings should be wrapped at 72 characters.
*   **Sentence Structure:** Comments should be complete sentences, capitalized, and end with a period.
*   **Language:** All comments and docstrings must be in English.
*   **Block Comments:** Apply to the code that follows them and should be indented to the same level. Each line starts with `#` and a single space. Paragraphs are separated by a line containing a single `#`.
*   **Inline Comments:** Use sparingly. Separate from the statement by at least two spaces. Start with `#` and a single space. Explain non-obvious logic, not the obvious.
    *   **Good:** `x = x + 1  # Compensate for 1-based indexing from external system.`
    *   **Bad:** `x = x + 1  # Increment x.`

## 4. Docstrings (PEP 257 & Google Python Style Guide)

All public modules, functions, classes, and methods **MUST** have docstrings. Non-public methods should have a comment describing what they do if not immediately obvious.

### 4.1. General Docstring Format
*   Use `"""triple double quotes"""`.
*   For one-liners, the closing quotes are on the same line.
*   For multi-line docstrings, the summary line is followed by a blank line, then the more detailed description. The closing `"""` is on a line by itself, indented the same as the opening quotes.

### 4.2. Module Docstrings (Top of each `.py` file & `__init__.py`)
*   **Purpose:** High-level summary of the module's or package's responsibility and role within SmartInfo.
*   **Content:**
    1.  Concise one-line summary ending with a period.
    2.  (Optional) A more detailed explanation of its functionality and purpose.
    3.  **Key Components/Exports:** List key classes or functions provided, with a brief description of their role. (e.g., for `utils/prompt.py`: "Provides standardized system prompt strings for LLM interactions.")
    4.  **(Conceptual Tag) `@module_purpose:`** (Optional, within prose): Clearly state the primary goal (e.g., "Data access layer for User entities.").
    5.  **(Conceptual Tag) `@primary_consumers:`** (Optional, within prose): Note typical modules that use this one (e.g., "Consumed by `AuthService` and API routers requiring user data.").
    6.  **(Conceptual Tag) `@primary_dependencies:`** (Optional, within prose): Note critical modules this one relies on.
*   **Example (`backend/core/security.py`):**
    ```python
    """
    Security Utilities for SmartInfo Backend.

    This module provides functions for password hashing and verification using bcrypt,
    and for creating and decoding JWT (JSON Web Tokens) for user authentication
    and session management.

    @module_purpose: Centralized security operations related to passwords and JWTs.
    @primary_consumers: `AuthService`, `api.dependencies.dependencies` (for token decoding).
    """
    ```

### 4.3. Class Docstrings (Google Style)
*   **Purpose:** Explain the role, responsibilities, and key features of the class.
*   **Content:**
    1.  Concise one-line summary.
    2.  (Optional) More detailed explanation of the class's design and purpose.
    3.  **`Attributes:` Section (for public attributes):**
        *   `attribute_name (type): Description of the attribute. Include constraints
          (e.g., "immutable after initialization") or default values if applicable.`
    4.  **(Conceptual Tag) `@class_responsibility:`** (Optional, within prose): Clearly state the main responsibility.
    5.  **(Conceptual Tag) `@typical_usage_pattern:`** (Optional, within prose): How is this class typically instantiated and used? (e.g., "Instantiated by `LLMClientPool`; methods called by services needing LLM completions.").
    6.  Mention key collaborator classes/dependencies.
*   **Example (`backend/core/llm/client.py` - `AsyncLLMClient`):**
    ```python
    class AsyncLLMClient(LLMClientBase):
        """
        Asynchronous client for interacting with OpenAI-compatible LLMs.

        This client uses `openai.AsyncOpenAI` to send requests for completions
        and streaming content. It handles API authentication, request parameters,
        and leverages the underlying library's retry mechanisms for transient errors.

        @class_responsibility: Provide a standardized asynchronous interface for making
                                API calls to LLMs.

        Attributes:
            base_url (str): The base URL of the LLM API.
            api_key (Optional[str]): The API key for authentication.
            default_model (Optional[str]): Default model name if not specified in calls.
            timeout (int): Request timeout in seconds.
            max_retries (int): Max retries for transient errors by the OpenAI client.
            _client (Optional[AsyncOpenAI]): The underlying AsyncOpenAI client instance.
            _is_closed (bool): Flag indicating if the client has been closed.
        """
    ```

### 4.4. Function and Method Docstrings (Google Style)
These are **critical** for AI understanding of how to use specific pieces of code.

*   **Mandatory Sections (where applicable):**
    1.  **One-line Summary:** Imperative mood (e.g., "Create a new chat session."). Ends with a period.
    2.  **(Optional) Extended Description:** Elaborate on purpose, context, or complex behavior. Explain *why* it exists if non-trivial.
    3.  **`Args:`**
        *   `param_name (type): Description.`
        *   Specify if optional, default values.
        *   **AI Optimization:** Clearly state constraints (e.g., "must be positive," "enum values: 'A', 'B'"), expected data format for complex types (e.g., for `List[Dict[str, str]]`, detail dict keys: `Each dict must contain 'role' ('user'|'assistant') and 'content' (str).`), and units (e.g., `timeout_seconds (int): Timeout duration in seconds.`).
    4.  **`Returns:` (or `Yields:` for generators)**
        *   `type: Description.`
        *   **AI Optimization:** For complex types (`Dict`, `List[Dict]`), detail the structure and semantic meaning of returned data.
    5.  **`Raises:`**
        *   `ExceptionType: Specific conditions under which this exception is raised.`
        *   **AI Optimization:** Include exceptions that might propagate from critical internal calls if not caught. Be specific (e.g., "Raises `ValueError` if `chat_id` is not found. Raises `asyncpg.PostgresError` if database interaction fails.").
    6.  **`Side Effects:` (CRITICAL for AI understanding of impact)**
        *   Explicitly list all significant side effects:
            *   Database modifications (e.g., "Inserts a record into the `chats` table.").
            *   External API calls (e.g., "Calls the LLM API endpoint.").
            *   File system changes.
            *   Modifications to input arguments if passed by reference and mutated in-place.
            *   Publishing messages to queues/brokers (e.g., "Publishes progress to Redis channel `task_progress:{task_group_id}`.").
            *   Changes to object state (e.g., "Sets `self._is_initialized` to True.").
    7.  **`Examples:` (Highly beneficial for AI)**
        *   Provide concise, runnable or near-runnable code snippets demonstrating typical usage.
        *   Include expected output structure for the given example inputs if feasible.
        *   Show how to handle common exceptions if relevant.

*   **Optional but Recommended Sections for Enhanced AI Understanding:**
    *   **`@preconditions:`** (Conceptual tag, within prose): What external state or conditions must be true before calling? (e.g., "Database connection must be initialized.", "User must be authenticated via `get_current_active_user`.").
    *   **`@postconditions:`** (Conceptual tag, within prose): What state is guaranteed after successful execution? (e.g., "A `Chat` record with the specified title will exist for the user.").
    *   **`@performance_notes:`** (Conceptual tag, within prose): Known performance characteristics or bottlenecks (e.g., "LLM calls can introduce significant latency.").
    *   **`@security_notes:`** (Conceptual tag, within prose): Specific security considerations for this function (e.g., "Input `raw_html` is not sanitized here; caller must ensure safety if rendering.", "Handles user API keys; ensure `user_id` context is strictly enforced.").
    *   **`@thread_safety:`** (Conceptual tag, within prose): Is the function/method thread-safe? (e.g., "Not thread-safe due to shared instance attribute `_counter`.").
    *   **`@idempotency:`** (Conceptual tag, within prose): Is the operation idempotent? (e.g., "Yes", "No, creates duplicates if called multiple times with same args.").

*   **Example (`backend/services/chat_service.py` - `create_chat`):**
    ```python
    async def create_chat(self, chat_data: ChatCreate, user_id: int) -> Chat:
        """Creates a new chat session for a specific user.

        The user_id provided is validated against the user context from which
        this service method is typically called (e.g., authenticated user).

        Args:
            chat_data (ChatCreate): Pydantic model containing the initial title
                for the chat. The `user_id` within `chat_data` (if present, though
                typically not in `ChatCreate` by design) is ignored in favor of
                the explicit `user_id` parameter.
            user_id (int): The ID of the user for whom the chat session is being created.
                This ID must be validated by the caller (e.g., API router).

        Returns:
            Chat: The newly created Chat Pydantic model, including its database ID
                  and timestamps. Messages list will be empty initially.

        Raises:
            ValueError: If `chat_data.title` is empty or if the underlying
                repository fails to create the chat record and returns no ID.
            asyncpg.PostgresError: If a database error occurs during insertion.

        Side Effects:
            - Inserts a new record into the `chats` table in the database.
            - Logs the creation event.

        @preconditions: `user_id` must correspond to an existing, valid user.
        @postconditions: A new chat session record linked to `user_id` will exist
                         in the database.
        """
    ```

## 5. Comments for Constants, Configuration, and Prompts

*   **`backend/schema_constants.py`:**
    *   Module docstring.
    *   Above each class (e.g., `Users`, `News`), a comment: `# Represents the 'users' table in the database.`
    *   Above each constant attribute (e.g., `ID = "id"`), a comment if its purpose isn't obvious from the name (usually is).
*   **`backend/config.py`:**
    *   Module docstring and `AppConfig` class docstring.
    *   For each property providing a config value (e.g., `@property def db_user(self)`), its docstring should explain what it configures and the environment variable it reads from.
*   **`backend/utils/prompt.py`:**
    *   Module docstring.
    *   Above **each** system prompt string (e.g., `SYSTEM_PROMPT_EXTRACT_ARTICLE_LINKS`):
        *   A multi-line comment explaining:
            *   `# Purpose: What this prompt instructs the LLM to achieve.`
            *   `# LLM Role: The persona the LLM should adopt (e.g., "Deep Reading Link Extraction Assistant").`
            *   `# Expected User Input Format: Describe the structure and key placeholders the application code will fill (e.g., "Receives <Base URL> and <Markdown content> tags.").`
            *   `# Expected LLM Output Format: Precisely describe the structure of the LLM's response (e.g., "Plain text, one URL per line. Outputs 'no' if no suitable links.").`
            *   `# Key Instructions to LLM (Summary): Briefly summarize the main rules/heuristics in the prompt.`
            *   `# Consumed By: Which module/function primarily uses this prompt (e.g., "core.workflow.news_fetch._extract_and_crawl_links").`

## 6. Pydantic Model Documentation (`backend/models/schemas/`)

*   **Module Docstring:** For each `*.py` file in `schemas/` (e.g., `news.py`, `chat.py`).
*   **Class Docstring:** For each Pydantic `BaseModel`, explain what real-world entity or data structure it represents.
*   **Field Descriptions:** **EVERY** field **MUST** have a `description` in `Field(..., description="...")`.
    *   Be specific about the field's meaning and any constraints not captured by the type (e.g., "User's chosen display name, must be unique across the system.").
    *   For optional fields, clarify when they might be `None`.
    *   Include `examples` in `Field` where it adds significant clarity for AI understanding of typical data.

## 7. Inline Comments (`#`)

*   **Use Sparingly:** Code should be as self-documenting as possible.
*   **Purpose:**
    *   Explain *why* non-obvious code exists (e.g., complex algorithm, workaround for a library bug, specific business rule implementation).
    *   Clarify complex conditions or mathematical formulas.
    *   Performance optimizations that might look counter-intuitive.
    *   `# TODO(username or issue_tracker_link): Explanation of what needs to be done.`
    *   `# FIXME(username or issue_tracker_link): Explanation of the bug and potential fix.`
    *   `# AI_ASSUMPTION: Comment if the code relies on an assumption not easily verifiable by static analysis (e.g., "Assumes input list is always sorted by caller").`
    *   `# AI_WARNING: Highlight potential pitfalls for AI refactoring (e.g., "Modifying this loop order will break the stateful calculation").`

## 8. Maintenance

*   **Comments as Code:** Treat comments and docstrings as integral parts of the codebase.
*   **Review Process:** Code reviews **MUST** include a review of associated comments and docstrings for clarity, accuracy, and completeness according to this guide.
*   **Updates:** When code logic changes, the corresponding comments and docstrings **MUST** be updated in the same commit/PR.
