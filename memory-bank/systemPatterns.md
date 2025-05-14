# System Patterns & Architecture: SmartInfo (Version 1.0)

## 1. System Architecture Overview
SmartInfo employs a full-stack architecture:
*   **Backend:** A FastAPI application serving as the API and data processing hub.
*   **Frontend:** A Next.js (React) single-page application providing the user interface.
*   **Database:** PostgreSQL for persistent data storage.
*   **Task Queue:** Celery with Redis as the broker and result backend for asynchronous background tasks.
*   **LLM Interaction:** Integration with OpenAI-compatible LLM APIs.

Diagrammatically (High-Level):

[User via Browser] <--> [Next.js Frontend] <--> [FastAPI Backend]
                     |                         |
                     | (HTTP API, WebSockets)  |
                     v                         v
           [PostgreSQL DB] [Celery Workers] <--> [Redis]
                           |
                           v
            [LLM APIs (e.g., OpenAI)]
            [External News Websites]

## 2. Key Technical Decisions & Patterns

### 2.1. Backend (FastAPI)
*   **Layered Architecture:**
    *   **API Routers (`backend/api/routers/`):** Handle HTTP request/response, input validation (Pydantic), and delegate to services. User-specific context (user_id) is primarily enforced at this layer or passed to services.
    *   **Services (`backend/services/`):** Encapsulate business logic. Coordinate interactions between repositories, LLMs, and other core components. Services are designed to be user-aware where necessary.
    *   **Repositories (`backend/db/repositories/`):** Abstract database interactions (CRUD operations). Repositories are generally responsible for user-specific data access by including `user_id` in their queries.
    *   **Core (`backend/core/`):** Contains cross-cutting concerns like security (JWT), LLM client management (pool), web crawling utilities, and workflow logic for complex operations (e.g., `news_fetch.py`).
    *   **Models (`backend/models/schemas/`):** Pydantic models for data validation, serialization, and API contracts. User-specific models (e.g., `NewsItemCreate` that doesn't take `user_id` directly from payload but service adds it) are a pattern.
*   **Asynchronous Operations:** Extensive use of `async/await` for non-blocking I/O, especially for database interactions (`asyncpg`), HTTP requests to LLMs (`aiohttp` in `AsyncLLMClient`), and web crawling.
*   **Dependency Injection:** FastAPI's `Depends` system is used to inject dependencies like services, repositories, and the current user.
*   **Background Tasks (Celery & Redis):**
    *   News fetching and initial processing (`news_tasks.py`) are offloaded to Celery workers. This prevents blocking API requests and allows for long-running operations.
    *   Redis serves as the message broker (task queue) and result backend for Celery.
*   **LLM Interaction (`backend/core/llm/`):**
    *   `AsyncLLMClient`: Handles communication with OpenAI-compatible APIs.
    *   `LLMClientPool`: Manages a pool of `AsyncLLMClient` instances for efficient reuse and concurrency.
*   **Web Crawling (`backend/core/crawler.py`):**
    *   Multiple crawler implementations (Aiohttp, Playwright, Selenium) provide flexibility for different types of websites. `PlaywrightCrawler` seems to be favored for initial page load, and `AiohttpCrawler` for fetching sub-links.
*   **Real-time Progress (WebSockets & Redis Pub/Sub):**
    *   `ConnectionManager` (`backend/core/ws_manager.py`) manages WebSocket connections.
    *   Celery tasks publish progress updates to Redis Pub/Sub channels.
    *   The FastAPI backend (specifically `tasks` router) subscribes to these Redis channels and forwards updates to connected WebSocket clients.
*   **Authentication:** JWT-based authentication (`python-jose`, `bcrypt`). `SECRET_KEY` is critical.
*   **Database Management:**
    *   `asyncpg` for asynchronous PostgreSQL interaction.
    *   Database schema constants are defined in `backend/db/schema_constants.py`.
    *   Tables are created on application startup via `lifespan` function in `main.py`.

### 2.2. Frontend (Next.js)
*   **Component-Based Architecture:** UI is built using React components (`frontend/src/components/`).
*   **Routing:** Next.js file-system based routing (`frontend/src/pages/`).
*   **UI Library:** Ant Design (`antd`) for pre-built UI components, ensuring a consistent look and feel.
*   **State Management:** React Context API (`AuthContext` for authentication state).
*   **API Communication:** Axios for making HTTP requests to the FastAPI backend (`frontend/src/services/`).
*   **Protected Routes:** Higher-Order Component (HOC) `withAuth.tsx` to protect routes requiring authentication.
*   **TypeScript:** For type safety.
*   **Styling:** CSS Modules and global styles.

### 2.3. Data Flow for News Fetching & Analysis (Critical Path)
1.  **User Action (Frontend):** User triggers news fetch (e.g., from selected sources) via UI.
2.  **API Request (Frontend -> Backend):** Frontend calls a FastAPI endpoint (e.g., `/api/news/tasks/fetch/batch-group`).
3.  **Task Dispatch (Backend):**
    *   FastAPI endpoint validates request, generates a `task_group_id`.
    *   A Celery `chord` is created:
        *   Header tasks: `process_single_batch_task` (one for each batch of source IDs). Each batch task gets `user_id` and `task_group_id`.
        *   Callback task: `finalize_news_fetch_group` (runs after all header tasks complete).
    *   The `task_group_id` is returned to the frontend.
4.  **WebSocket Connection (Frontend):** Frontend establishes a WebSocket connection to `/api/tasks/ws/tasks/group/{task_group_id}`.
5.  **Background Processing (Celery Worker):**
    *   `process_single_batch_task` (Celery task):
        *   Initializes its own DB connection, LLM client pool, and repositories.
        *   For each source in its batch:
            *   Calls `core.workflow.news_fetch.fetch_news()`.
                *   `fetch_news` uses `PlaywrightCrawler` (or other) to get main page HTML.
                *   Cleans HTML, converts to Markdown.
                *   Uses LLM to extract article links.
                *   Uses `AiohttpCrawler` to fetch content of extracted links.
                *   Uses LLM to summarize content and generate titles for each valid sub-article.
            *   Saves processed news items to DB via `NewsRepository`.
            *   Records fetch history via `FetchHistoryRepository`.
            *   Publishes progress updates (step, percentage, items_saved) to a Redis channel (`task_progress:{task_group_id}`).
6.  **Progress Forwarding (Backend):**
    *   FastAPI (via `tasks` router's WebSocket endpoint) has a listener subscribed to the Redis channel.
    *   When a message is received on Redis, `ws_manager` sends it to the connected WebSocket client(s) for that `task_group_id`.
7.  **UI Update (Frontend):** Frontend receives progress via WebSocket and updates the UI (e.g., task drawer).
8.  **Finalization (Celery Worker):**
    *   Once all `process_single_batch_task` instances in the chord complete, `finalize_news_fetch_group` is called.
    *   This task publishes an `overall_batch_completed` event to the Redis channel.
9.  **UI Final Update & Cleanup (Frontend/Backend):** Frontend updates UI to show completion. WebSocket connection might be closed.

## 3. Key Modules & Responsibilities
*   `backend/main.py`: FastAPI app entry point, lifespan management (DB, LLM pool init).
*   `backend/core/crawler.py`: Web crawling logic.
*   `backend/core/llm/pool.py` & `client.py`: LLM interaction.
*   `backend/core/workflow/news_fetch.py`: Orchestrates the news fetching and processing logic for a single source URL.
*   `backend/background/tasks/news_tasks.py`: Celery tasks for background processing.
*   `backend/core/ws_manager.py` & `backend/api/routers/tasks.py`: Real-time progress updates.
*   `backend/services/`: Business logic layer.
*   `backend/db/repositories/`: Data access layer.
*   `frontend/src/pages/index.tsx`: Main news dashboard page.
*   `frontend/src/services/newsService.ts`: Frontend service for news-related API calls.
*   `frontend/src/context/AuthContext.tsx`: Frontend authentication state.

## 4. Scalability & Performance Considerations
*   Asynchronous backend operations are key for handling concurrent users and I/O bound tasks.
*   Celery allows for distributing background task processing across multiple workers.
*   LLM Client Pool helps manage resources for LLM API calls.
*   Database connection pooling (`asyncpg.create_pool` in `db.connection.py` when `DB_CONNECTION_MODE` is 'pool').
*   Efficient web crawling strategies (e.g., choosing the right crawler, respecting `robots.txt` - not explicitly mentioned but good practice).
*   Frontend pagination and optimized API calls for displaying news.

