# Technical Context: SmartInfo (Version 1.0)

## 1. Backend Technologies
*   **Primary Language:** Python 3.12+
*   **Web Framework:** FastAPI
    *   Used for building robust, asynchronous APIs.
    *   Leverages Pydantic for data validation and serialization.
    *   Automatic API documentation (Swagger UI, ReDoc).
*   **Asynchronous Programming:**
    *   `asyncio` for core async capabilities.
    *   `aiohttp` for asynchronous HTTP client requests (used in `AsyncLLMClient` and `AiohttpCrawler`).
    *   `asyncpg` for asynchronous interaction with the PostgreSQL database.
*   **Database:** PostgreSQL
    *   Primary persistent data store.
    *   Schema managed implicitly on application startup (`main.py` lifespan function).
*   **Task Queue:** Celery
    *   Used for offloading long-running tasks (news fetching, analysis) to background workers.
    *   Ensures API responsiveness.
*   **Message Broker & Result Backend (for Celery):** Redis
    *   Also used for WebSocket Pub/Sub mechanism for real-time progress updates.
*   **Web Crawling:**
    *   `Playwright`: For complex websites requiring JavaScript rendering (initial page load).
    *   `Selenium`: Alternative for JavaScript-heavy sites.
    *   `Aiohttp`: For fetching content from already identified, simpler URLs (e.g., extracted article links).
    *   `Trafilatura`: Library for extracting main content and metadata from HTML.
    *   `Newspaper4k`: For article extraction and metadata parsing.
    *   `BeautifulSoup4`: For HTML parsing and manipulation.
*   **LLM Interaction:**
    *   OpenAI Python SDK (or compatible libraries for services like DeepSeek).
    *   `LLMClientPool` for managing concurrent connections to LLM APIs.
*   **Authentication:**
    *   JWT (JSON Web Tokens) for stateless authentication.
    *   `python-jose` library for JWT encoding/decoding.
    *   `bcrypt` for password hashing.
*   **Dependency Management:** Poetry (`pyproject.toml`, `poetry.lock`).
*   **Environment Variables:** `python-dotenv` (`.env` file for configuration).
*   **Web Server (Development):** Uvicorn.

## 2. Frontend Technologies
*   **Primary Language:** TypeScript
*   **Framework:** Next.js (React framework)
    *   Used for server-side rendering (SSR) or static site generation (SSG) capabilities, routing, and overall application structure.
*   **UI Library:** Ant Design (antd)
    *   Provides a rich set of pre-built, customizable React components for building the user interface.
*   **State Management:** React Context API
    *   Used for managing global state, particularly `AuthContext` for authentication status and user information.
*   **HTTP Client:** Axios
    *   Used for making API requests from the frontend to the FastAPI backend.
*   **Styling:**
    *   CSS Modules for component-scoped styles.
    *   Global CSS (`globals.css`) for overall application styling and Ant Design theme overrides.
*   **Package Manager:** npm or yarn (`package.json`).
*   **Testing:**
    *   Jest: JavaScript testing framework.
    *   React Testing Library: For testing React components.

## 3. Development & Operational Setup
*   **Backend Setup:**
    1.  `poetry install` to install dependencies.
    2.  Configure `.env` file (database credentials, Redis URL, `SECRET_KEY`).
    3.  Run FastAPI server: `poetry run uvicorn main:app --reload`.
    4.  Run Celery worker: `poetry run celery -A background.celery_app worker --loglevel=info`.
*   **Frontend Setup:**
    1.  `npm install` or `yarn install`.
    2.  Configure `.env.local` with `NEXT_PUBLIC_API_URL`.
    3.  Run development server: `npm run dev` or `yarn dev`.
*   **Database Initialization:** Tables are created automatically by the FastAPI backend on startup if they don't exist.
*   **Inter-service Communication:**
    *   Frontend <-> Backend: HTTP/HTTPS RESTful API calls, WebSockets for real-time updates.
    *   Backend -> LLM API: HTTPS API calls.
    *   Backend (FastAPI) <-> Celery Worker: Via Redis message broker.
    *   Celery Worker -> Redis (Pub/Sub): For publishing task progress.
    *   Backend (FastAPI WebSocket) <- Redis (Pub/Sub): For receiving task progress.

## 4. Technical Constraints & Considerations
*   **LLM API Costs & Rate Limits:** Usage of LLM APIs will incur costs and be subject to rate limits. The `LLMClientPool` and careful design of LLM-dependent features are important.
*   **Web Crawling Ethics & Robustness:**
    *   Respect `robots.txt`.
    *   Implement appropriate delays and user-agent rotation to avoid overloading servers.
    *   Handle various website structures and anti-crawling measures.
*   **Security:**
    *   Secure JWT implementation (`SECRET_KEY` management).
    *   Input validation (Pydantic on backend, form validation on frontend).
    *   Protection against common web vulnerabilities (OWASP Top 10 considerations).
*   **Scalability:** While Celery allows for scaling background workers, database performance and LLM API throughput will be key bottlenecks for larger scale.
*   **Error Handling:** Robust error handling and logging are implemented across both backend and frontend (`apiErrorHandler.ts` on frontend).