# SmartInfo Backend Testing Guide

## 1. Introduction

### 1.1. Purpose
This guide outlines the testing philosophy, strategies, tools, and conventions for the SmartInfo backend. Its primary goal is to ensure code quality, maintainability, and correctness, enabling both human developers and AI assistants to contribute effectively and safely.

Adhering to these guidelines will help us:
*   Catch bugs early in the development cycle.
*   Facilitate safer refactoring and addition of new features.
*   Provide clear, testable contracts for different modules.
*   Enable AI assistants to generate meaningful and correct tests.

### 1.2. Testing Philosophy
Our testing philosophy is based on a pragmatic approach to the testing pyramid:
*   **Strong Foundation of Unit Tests:** Most of our tests should be unit tests that are fast, isolated, and verify the smallest pieces of logic.
*   **Targeted Integration Tests:** Verify interactions between components, especially API endpoints and their immediate service layer dependencies, and interactions with the database.
*   **Continuous Improvement:** Our testing strategy will evolve as the project grows.

We aim for tests that are:
*   **Readable:** Easy to understand what is being tested and why.
*   **Reliable:** Produce consistent results (no flakiness).
*   **Maintainable:** Easy to update when the code changes.
*   **Fast:** Quick to execute to encourage frequent running.

## 2. Tools & Frameworks

*   **Primary Testing Framework:** [`pytest`](https://docs.pytest.org/) - For its concise syntax, powerful fixture system, and rich plugin ecosystem.
*   **Asynchronous Testing:** [`pytest-asyncio`](https://pytest-asyncio.readthedocs.io/) - For testing our `async` code.
*   **Mocking:** [`unittest.mock`](https://docs.python.org/3/library/unittest.mock.html) (standard library) or [`pytest-mock`](https://pytest-mock.readthedocs.io/) plugin - For isolating components by mocking dependencies.
*   **API Endpoint Testing:** [`httpx.AsyncClient`](https://www.python-httpx.org/async/) - For making asynchronous HTTP requests to our FastAPI application during integration tests.
*   **Code Coverage:** [`pytest-cov`](https://pytest-cov.readthedocs.io/) - To measure test coverage.
*   **Database Fixtures:** Custom `pytest` fixtures will be used for managing test database connections and state.
*   **Celery Testing:** [`celery.contrib.testing.worker`](https://docs.celeryq.dev/en/stable/userguide/testing.html#celery-contrib-testing) for in-process worker testing of Celery tasks, or direct invocation of task logic with mocks.

## 3. Types of Tests

### 3.1. Unit Tests
*   **Focus:** Test individual functions, methods, or classes in isolation.
*   **Scope:** Limited to a single module or a small, cohesive set of functions/classes.
*   **Dependencies:** External dependencies (database, LLM APIs, other services, Redis, file system) **MUST** be mocked.
*   **Location:** `backend/tests/unit/<module_path>/test_<filename>.py` (e.g., `backend/tests/unit/services/test_news_service.py`).
*   **Goal:** Verify logic, edge cases, and error handling of individual components.

### 3.2. Integration Tests
*   **Focus:** Test the interaction between multiple components.
*   **Scope:**
    *   **API Endpoint Tests:** Verify API request/response contracts, status codes, and basic data validation. These tests will typically involve the API router and the service layer, with the repository layer potentially interacting with a **test database**.
    *   **Service-Repository Tests:** Verify that service logic correctly uses repository methods and that repositories interact correctly with the **test database**.
    *   **Celery Task Integration (Limited):** Test the successful dispatch of Celery tasks and, separately, the task's interaction with services/repositories using a test database/mocked LLM.
*   **Dependencies:**
    *   For API tests, services might be partially mocked or use real instances connected to a test database. LLM calls and other truly external APIs should still be mocked.
    *   For Service-Repository tests, a live test database is used.
*   **Location:** `backend/tests/integration/<component_type>/test_<feature>.py` (e.g., `backend/tests/integration/api/test_news_endpoints.py`).
*   **Goal:** Ensure components work together as expected and interactions with the database are correct.

*(Future Consideration: End-to-End (E2E) Tests - These would test complete workflows through the deployed application, including Celery workers and external systems. For now, we focus on unit and integration tests.)*

## 4. Test Organization and Naming Conventions

### 4.1. Directory Structure
```
SmartInfo/
└── backend/
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py         # Global pytest fixtures
    │   ├── unit/
    │   │   ├── __init__.py
    │   │   ├── services/
    │   │   │   └── test_news_service.py
    │   │   ├── repositories/
    │   │   │   └── test_news_repository.py
    │   │   ├── core/
    │   │   │   ├── llm/
    │   │   │   │   └── test_llm_client_pool.py
    │   │   │   └── workflow/
    │   │   │       └── test_news_fetch_workflow.py
    │   │   └── utils/
    │   │       └── test_text_utils.py
    │   └── integration/
    │       ├── __init__.py
    │       ├── api/
    │       │   └── test_news_endpoints.py
    │       │   └── test_auth_endpoints.py
    │       └── tasks/
    │           └── test_news_tasks_integration.py # For Celery task logic integration
    └── ... (application code)
```

### 4.2. File Naming
*   Test files **MUST** start with `test_` (e.g., `test_news_service.py`).
*   Test files should generally mirror the structure of the application code they are testing.

### 4.3. Function/Method Naming
*   Test functions **MUST** start with `test_`.
*   Use descriptive names that indicate what is being tested and the expected outcome or condition.
*   Format: `test_<method_or_function_being_tested>__<condition_or_scenario>__<expected_behavior>()`
    *   Example: `test_news_service_add_news__valid_data__returns_news_item()`
    *   Example: `test_user_repository_get_user_by_username__user_exists__returns_user_in_db()`
    *   Example: `test_news_router_get_items__no_filters__returns_200_and_list()`
    *   Example: `test_news_router_create_item__duplicate_url__returns_409_conflict()`

## 5. Writing Unit Tests

### 5.1. General Principles
*   **AAA Pattern:** Arrange (set up test preconditions), Act (execute the code being tested), Assert (verify the outcome).
*   **Isolation:** Each test should be independent and not rely on the state or outcome of other tests.
*   **Focus:** Test one specific piece of logic or behavior per test function.
*   **Clarity:** Test code should be as readable as production code, if not more so.

### 5.2. Testing Services
*   **Dependencies:** Mock all external dependencies of the service, primarily:
    *   Repository methods.
    *   `LLMClientPool` or `AsyncLLMClient` methods.
    *   Celery task `delay()` or `apply_async()` calls.
    *   Any utility functions that have external dependencies or complex internal logic not relevant to the service test.
*   **Focus:** Test the business logic within the service method:
    *   Correct invocation of repository methods with expected arguments.
    *   Proper handling of data returned by repositories.
    *   Correct interaction with LLM clients (parameters passed, handling of responses).
    *   Logic for dispatching Celery tasks.
    *   Error handling and exception raising.
*   **Example Snippet (Conceptual):**
    ```python
    # backend/tests/unit/services/test_news_service.py
    import pytest
    from unittest.mock import AsyncMock, patch

    from backend.services import NewsService
    from backend.models import NewsItemCreate # Pydantic model for creation

    @pytest.mark.asyncio
    async def test_news_service_create_news__valid_data__calls_repo_and_returns_item(
        mock_news_repository, # Pytest fixture providing a mocked NewsRepository
        mock_user_api_key_repo, # Mock for ApiKeyRepository
        test_user_id
    ):
        # Arrange
        news_service = NewsService(
            news_repo=mock_news_repository,
            source_repo=AsyncMock(), # Other repos mocked as needed
            category_repo=AsyncMock(),
            api_key_repo=mock_user_api_key_repo
        )
        news_data_dict = {"title": "Test Title", "url": "http://example.com/test", "user_id": test_user_id}
        # Assuming Pydantic model for creation, or use dict directly if service expects that
        news_create_data = NewsItemCreate(**news_data_dict)

        # Mock repository's add method to return an ID
        mock_news_repository.add.return_value = 123
        # Mock repository's get_by_id to return the "created" item
        mock_news_repository.get_by_id.return_value = {"id": 123, **news_data_dict, "content": None, "analysis": None} # Simplified

        # Act
        # Assuming create_news is the method name, adjust if different
        # And assuming it expects Pydantic model or a dict, adjust accordingly
        created_item = await news_service.create_news(news_create_data, user_id=test_user_id) # Hypothetical method

        # Assert
        mock_news_repository.add.assert_called_once()
        # Further assertions on what was passed to mock_news_repository.add
        mock_news_repository.get_by_id.assert_called_once_with(123, test_user_id)
        assert created_item is not None
        assert created_item["id"] == 123
        assert created_item["title"] == "Test Title"
    ```

### 5.3. Testing Repositories
*   **Strategy:** Repository tests will typically be integration tests interacting with a **dedicated test database**. This ensures SQL queries are correct and database constraints are met.
*   **Test Database:**
    *   Use a separate PostgreSQL database instance or schema for testing.
    *   `pytest` fixtures should manage creating/dropping tables and populating initial test data for each test session or module.
    *   Ensure data isolation between tests (e.g., transactions that are rolled back, or table truncation).
*   **Focus:**
    *   Correctness of SQL queries.
    *   Data transformation to/from Pydantic models or dictionaries.
    *   Handling of database constraints (e.g., `UNIQUE`, `FOREIGN KEY`).
    *   Edge cases (e.g., empty tables, non-existent IDs).
*   **`conftest.py` for DB Fixtures:**
    ```python
    # backend/tests/conftest.py (simplified example)
    import pytest
    import asyncpg
    import os

    @pytest.fixture(scope="session")
    async def db_test_conn_pool(): # Manages a pool for the entire test session
        # Use different DB credentials/name for testing from environment variables
        pool = await asyncpg.create_pool(
            user=os.getenv("TEST_DB_USER"),
            password=os.getenv("TEST_DB_PASSWORD"),
            database=os.getenv("TEST_DB_NAME"),
            host=os.getenv("TEST_DB_HOST", "localhost"),
            port=os.getenv("TEST_DB_PORT", "5432")
        )
        yield pool
        await pool.close()

    @pytest.fixture
    async def db_conn(db_test_conn_pool): # Provides a connection for a single test
        async with db_test_conn_pool.acquire() as connection:
            async with connection.transaction(): # Start a transaction
                yield connection
                # Transaction will be rolled back here, ensuring test isolation
    ```
*   **Example Snippet (Conceptual):**
    ```python
    # backend/tests/integration/repositories/test_news_repository.py
    import pytest
    from backend.db.repositories import NewsRepository
    from backend.db.schema_constants import News # For table/column names

    @pytest.mark.asyncio
    async def test_news_repository_add_and_get_by_id(db_conn, test_user_id): # db_conn from conftest.py
        # Arrange
        repo = NewsRepository() # Repositories now get connection from context
        news_data = {
            "title": "Unique Test News", "url": "http://unique.example.com/news",
            "user_id": test_user_id, "source_name": "Test Source"
        }

        # Act
        # Override internal connection context for this test instance of repo
        repo._get_connection_context = lambda: db_conn # Simplistic override for example
        
        news_id = await repo.add(news_data, test_user_id)
        assert news_id is not None
        retrieved_news = await repo.get_by_id(news_id, test_user_id)

        # Assert
        assert retrieved_news is not None
        assert retrieved_news[News.TITLE.lower()] == "Unique Test News"
        assert retrieved_news[News.URL.lower()] == "http://unique.example.com/news"
    ```

### 5.4. Testing Utility Functions (`backend/utils/`)
*   These are typically pure functions and should be straightforward to unit test.
*   Provide varied inputs to cover different logic paths and edge cases.

### 5.5. Testing Core Components (e.g., `LLMClient`, `Crawlers`)
*   **`LLMClient` / `LLMClientPool`:**
    *   Mock the underlying `openai.AsyncOpenAI` client or HTTP calls it makes.
    *   Test construction, parameter passing to the mocked client.
    *   Test retry logic if implemented within our client wrappers.
    *   Test error handling for API errors from the mocked client.
    *   For the pool, test acquisition, release, and pool size management.
*   **Crawlers (`AiohttpCrawler`, `PlaywrightCrawler`):**
    *   Mock `aiohttp.ClientSession.get` or Playwright's `page.goto`, `page.content`.
    *   Test URL processing, header manipulation, retry logic.
    *   Test handling of different HTTP status codes and network errors from mocks.

## 6. Writing Integration Tests

### 6.1. API Endpoint Tests
*   **Tool:** Use `httpx.AsyncClient` against the FastAPI application instance.
    ```python
    # backend/tests/integration/api/conftest.py
    import pytest
    from httpx import AsyncClient
    from backend.main import app # Your FastAPI app instance

    @pytest.fixture(scope="module")
    async def async_client():
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client
    ```
*   **Focus:**
    *   Request validation (correct and incorrect payloads).
    *   Response status codes.
    *   Response payload structure and key data points (Pydantic models ensure this).
    *   Authentication and authorization (testing with and without valid tokens, accessing other users' resources).
    *   Correct interaction with the (potentially mocked) service layer.
*   **Database Interaction:**
    *   For `GET` requests, populate the test database with necessary data via fixtures.
    *   For `POST`, `PUT`, `DELETE`, verify changes in the test database.
*   **Example Snippet (Conceptual):**
    ```python
    # backend/tests/integration/api/test_news_endpoints.py
    import pytest
    from httpx import AsyncClient

    @pytest.mark.asyncio
    async def test_create_news_item_valid_data_returns_201(
        async_client: AsyncClient, authenticated_user_headers, db_conn, test_user_id
    ): # authenticated_user_headers is a fixture providing auth token
        # Arrange
        # Ensure test_user_id exists, and any FKs like category/source exist for this user in db_conn
        news_payload = {
            "title": "API Test News", "url": "http://api.example.com/news",
            "source_name": "API Source", "category_name": "API Category"
            # user_id is implicit from token
        }

        # Act
        response = await async_client.post("/api/news/items", json=news_payload, headers=authenticated_user_headers)

        # Assert
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["title"] == "API Test News"
        assert "id" in response_data

        # Optionally, verify in db_conn that the item was created for test_user_id
    ```

## 7. Mocking Strategies

*   **`unittest.mock.patch` or `pytest-mock` (`mocker` fixture):**
    *   Use `patch.object` to mock methods on specific instances.
    *   Use `patch` as a decorator or context manager to mock module-level functions or classes.
    *   `AsyncMock` for mocking `async` functions/methods.
*   **Database:**
    *   **Unit Tests:** Mock repository methods entirely.
    *   **Integration Tests:** Use a dedicated test database. Provide `pytest` fixtures to:
        *   Establish connection.
        *   Create/truncate tables (e.g., using `alembic` or raw SQL).
        *   Seed necessary data for specific tests.
        *   Wrap tests in transactions that are rolled back.
*   **LLM API Calls:**
    *   Mock `AsyncLLMClient.get_completion_content` and `AsyncLLMClient.stream_completion_content`.
    *   Have mocks return predefined responses to test how your service handles different LLM outputs (success, error, empty).
*   **External Services (if any besides LLM):**
    *   Mock the client library or HTTP calls (e.g., using `httpx.mock_transport`).
*   **Celery Tasks:**
    *   **Unit Testing Task Logic:** Import the task function directly and call it, mocking its dependencies (DB, LLM, etc.).
    *   **Testing Task Dispatch:** Use `mocker.patch('backend.background.tasks.news_tasks.process_single_batch_task.delay')` (or `.s()`) to assert that the task was called with correct arguments by a service.
    *   **Testing Task Behavior (In-Process):** For more involved task testing, you can use `celery.contrib.testing.worker.start_worker(app, concurrency=1)` within your tests to run a worker in the same process. This is more complex to set up.
*   **Redis (`ws_manager`, Celery Broker/Backend):**
    *   For `ws_manager` unit tests, mock the `redis.Redis` client methods (`publish`, `pubsub`, etc.).
    *   For Celery, the broker/backend interaction is usually handled by Celery's testing utilities or by testing task logic in isolation.

## 8. Running Tests

*   **Run all tests:**
    ```bash
    cd backend
    pytest
    ```
*   **Run tests in a specific file:**
    ```bash
    pytest tests/unit/services/test_news_service.py
    ```
*   **Run a specific test function (using `-k` expression):**
    ```bash
    pytest -k "test_news_service_add_news"
    ```
*   **With Coverage:**
    ```bash
    pytest --cov=backend --cov-report=html
    ```
    (Ensure `backend` is the correct path to your source code for coverage calculation).
    Open `htmlcov/index.html` to view the report.

## 9. Code Coverage

*   **Target:** Aim for **>85%** line coverage for new code. Critical modules (e.g., auth, core services) should aim for higher.
*   **Review:** Coverage reports should be reviewed periodically. Low coverage in critical areas should be addressed.
*   **Focus on Quality:** High coverage is good, but it doesn't guarantee test quality. Ensure tests are meaningful and assert important behaviors.

## 10. Best Practices & Guidelines

*   **Test Happy Paths and Edge Cases:** Include tests for normal operation, expected error conditions, invalid inputs, and boundary conditions.
*   **Keep Tests Independent:** Avoid tests that depend on the state or outcome of other tests.
*   **Avoid Testing External Libraries:** Trust that external libraries (like `aiohttp`, `FastAPI` itself) are well-tested. Focus on testing *your* code's integration and logic.
*   **Use Descriptive Fixtures:** `pytest` fixtures should have clear names and encapsulate setup logic.
*   **Parameterize Tests:** Use `@pytest.mark.parametrize` to run the same test logic with different inputs/outputs, reducing boilerplate.
*   **Refactor Test Code:** Test code is code. Keep it clean, DRY (Don't Repeat Yourself), and maintainable. Utility functions or helper classes for tests are encouraged.
*   **Run Tests Frequently:** Integrate tests into your local development workflow and CI/CD pipeline.

## 11. AI Contribution Guide for Tests

When an AI assistant is tasked with generating or modifying code, it should also be responsible for associated tests.

*   **New Features:** For any new service method, API endpoint, or significant utility function, the AI **MUST** generate corresponding unit tests (and integration tests for API endpoints).
*   **Bug Fixes:** If a bug fix modifies logic, the AI **MUST** provide a regression test that would have caught the bug.
*   **Refactoring:** The AI **MUST** ensure all existing relevant tests pass after refactoring and update tests if interfaces change.
*   **Test Coverage:** Generated tests should aim to cover the new/modified logic adequately, targeting the project's coverage goals.
*   **Mocking:** The AI should correctly identify and mock external dependencies as per the strategies outlined in this guide.
*   **Assertions:** Assertions should be specific and verify the intended outcomes and side effects.
*   **Prompting AI for Tests:**
    *   "Generate unit tests for the `create_chat` method in `ChatService`. Mock the `ChatRepository` and cover scenarios for valid input, invalid input (e.g., missing title), and repository errors."
    *   "Write an integration test for the `POST /api/news/items` endpoint. Ensure it tests successful creation (201), unauthorized access (401), and payload validation errors (422)."