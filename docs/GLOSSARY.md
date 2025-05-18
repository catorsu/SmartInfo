# SmartInfo Project: Glossary of Terms

## 1. Introduction

This glossary defines key terms, acronyms, and concepts used throughout the SmartInfo project, encompassing both backend and frontend development. Its purpose is to establish a common understanding and vocabulary for all contributors, including human developers and AI assistants, facilitating clear communication and efficient development.

Terms are listed alphabetically.

---

## A

*   **ADR (Architecture Decision Record)**
    *   **Scope:** General (Project Management)
    *   **Definition:** A document that captures a significant architectural decision, including its context, the decision made, and the rationale behind it. Used to maintain a historical log of design choices.
    *   **Key Modules/Files:** `docs/backend/ARCHITECTURE_DECISION_RECORDS.md` (example location)

*   **AI Assistant (in project context)**
    *   **Scope:** General
    *   **Definition:** Refers to Large Language Models or other AI tools used to aid in the development, understanding, or usage of the SmartInfo project. Project documentation is designed with such assistants in mind.

*   **AiohttpCrawler**
    *   **Scope:** Backend
    *   **Definition:** A core crawler component (`core.crawler.AiohttpCrawler`) that uses the `aiohttp` library for making asynchronous HTTP requests to fetch web content. Often used for fetching content from multiple sub-article links efficiently due to its lightweight nature.

*   **Ant Design (AntD)**
    *   **Scope:** Frontend
    *   **Definition:** The primary UI component library used in the SmartInfo frontend to provide pre-built and customizable React components (buttons, forms, modals, layout elements, etc.).
    *   **Key Modules/Files:** `styles/globals.css` (for overrides), various `frontend/src/components/**/*.tsx`.

*   **API Key (User-Specific LLM Key)**
    *   **Scope:** Backend / Full-Stack
    *   **Definition:** Credentials (model name, base URL, key string, context size, etc.) provided by a SmartInfo user to allow the application to make calls to an external Large Language Model (LLM) API on their behalf.
    *   **Storage:** `api_config` database table.
    *   **Key Modules/Files:** `models.schemas.api_key` (BE), `db.repositories.api_key_repository` (BE), `services.setting_service` (BE), `frontend/src/components/settings/SettingsContent.tsx` (FE for management).

*   **API Router (FastAPI Router)**
    *   **Scope:** Backend
    *   **Definition:** A FastAPI component (instance of `fastapi.APIRouter`) that defines a set of API endpoints for a specific resource or functionality (e.g., news, chat).
    *   **Key Modules/Files:** Files within `backend/api/routers/` (e.g., `news.py`, `chat.py`).

*   **AsyncLLMClient**
    *   **Scope:** Backend
    *   **Definition:** A core client class (`core.llm.client.AsyncLLMClient`) responsible for making asynchronous API calls to OpenAI-compatible LLMs.
    *   **Related Terms:** `LLMClientPool`.

*   **Authentication**
    *   **Scope:** Full-Stack
    *   **Definition:** The process of verifying the identity of a user, typically through username and password, resulting in the issuance of a JWT access token in SmartInfo.
    *   **Key Modules/Files:** `backend/api/routers/auth.py`, `backend/services/auth_service.py`, `backend/core/security.py`, `frontend/src/context/AuthContext.tsx`, `frontend/src/services/authService.ts`.

*   **Authorization**
    *   **Scope:** Backend (primarily enforced), Frontend (UI reflects it)
    *   **Definition:** The process of determining whether an authenticated user has permission to access a specific resource or perform a particular action. In SmartInfo, this is primarily based on user data ownership.

*   **Axios**
    *   **Scope:** Frontend
    *   **Definition:** The HTTP client library used for making API requests from the frontend to the SmartInfo backend.
    *   **Key Modules/Files:** `frontend/src/services/api.ts`.

## B

*   **Batch Processing (News Fetching)**
    *   **Scope:** Backend
    *   **Definition:** The strategy of grouping multiple news source fetching operations into batches, where each batch is processed by a single Celery task (`process_single_batch_task`).
    *   **Related Terms:** `Task Group ID`, `Chord`.

*   **Broker (Celery Message Broker)**
    *   **Scope:** Backend
    *   **Definition:** An intermediary service (Redis in SmartInfo) that handles messages (task requests) between clients (the FastAPI app dispatching tasks) and Celery workers.
    *   **Key Modules/Files:** `backend/background/celery_app.py`.

## C

*   **Celery**
    *   **Scope:** Backend
    *   **Definition:** An asynchronous task queue/job queue based on distributed message passing. Used in SmartInfo for background processing of long-running tasks like news fetching.
    *   **Key Modules/Files:** `backend/background/celery_app.py`, `backend/background/tasks/news_tasks.py`.

*   **Chord (Celery Chord)**
    *   **Scope:** Backend
    *   **Definition:** A Celery workflow primitive consisting of a "header" (a group of tasks run in parallel) and a "body" (a callback task that runs only after all header tasks complete). Used for managing news fetching batches.
    *   **Key Modules/Files:** `backend/background/tasks/news_tasks.py`.

*   **Component (React Component)**
    *   **Scope:** Frontend
    *   **Definition:** A reusable, self-contained piece of UI in React. SmartInfo uses function components with hooks.
    *   **Key Modules/Files:** Files within `frontend/src/components/`.

*   **Configuration (`config.py`)**
    *   **Scope:** Backend
    *   **Definition:** The module (`backend.config`) and `AppConfig` class responsible for loading and providing access to application-level settings, primarily from environment variables.
    *   **Key Modules/Files:** `backend.config.py`, `CONFIGURATION_GUIDE.md` (BE).

*   **Context (React Context API)**
    *   **Scope:** Frontend
    *   **Definition:** A React API for sharing state (e.g., authentication status, page action triggers) across the component tree without prop drilling.
    *   **Key Modules/Files:** `frontend/src/context/` (e.g., `AuthContext.tsx`, `PageActionContext.tsx`). Refer to `STATE_MANAGEMENT.MD` (FE).

*   **Context Window (LLM)**
    *   **Scope:** Backend / General LLM
    *   **Definition:** The maximum number of tokens (input + output) that an LLM can process in a single interaction. Configured per user API key.
    *   **Related Terms:** `Token (LLM)`.

*   **Crawler**
    *   **Scope:** Backend
    *   **Definition:** A component responsible for fetching web content from URLs. SmartInfo uses `AiohttpCrawler` and `PlaywrightCrawler`.
    *   **Key Modules/Files:** `backend/core/crawler.py`.

*   **CRUD**
    *   **Scope:** General (Database/API)
    *   **Definition:** Acronym for Create, Read, Update, Delete – fundamental operations for persistent data storage.

*   **CSS Modules**
    *   **Scope:** Frontend
    *   **Definition:** A CSS file where class names are locally scoped by default (e.g., `styles.myClass`), preventing global namespace collisions. Files typically end in `.module.css`.

## D

*   **Dependency Injection (DI)**
    *   **Scope:** Backend (FastAPI)
    *   **Definition:** A design pattern used by FastAPI where dependencies (like services, repositories, or the current user) are automatically provided to API endpoint functions as parameters.
    *   **Key Modules/Files:** `backend/api/dependencies/dependencies.py`.

*   **Docstring**
    *   **Scope:** General (Python/TypeScript)
    *   **Definition:** A string literal used as the first statement in a module, function, class, or method to document it. SmartInfo uses Google Style (Python) and JSDoc (TypeScript).

## E

*   **Environment Variables**
    *   **Scope:** Full-Stack
    *   **Definition:** Variables set outside the application (e.g., in a `.env` file or the deployment environment) that configure its behavior.
    *   **Key Modules/Files:** `backend/config.py` (BE), `frontend/.env.local` (FE), `CONFIGURATION_GUIDE.md` (BE).

*   **ERD (Entity-Relationship Diagram)**
    *   **Scope:** Backend (Database)
    *   **Definition:** A diagram visually representing database tables and their relationships.
    *   **Key Modules/Files:** `docs/backend/DATABASE_SCHEMA.md`.

## F

*   **FastAPI**
    *   **Scope:** Backend
    *   **Definition:** The primary web framework used for building the SmartInfo backend API.

*   **Fetch History Item**
    *   **Scope:** Backend / Full-Stack (Data Concept)
    *   **Definition:** A database record (`fetch_history` table) tracking the number of news items successfully fetched and saved from a specific news source, for a particular user, on a given day.
    *   **Key Modules/Files:** `models.schemas.news.FetchHistoryItemResponse` (BE), `db.repositories.fetch_history_repository` (BE).

*   **Full-Text Search (FTS)**
    *   **Scope:** Backend (Database)
    *   **Definition:** A database feature (PostgreSQL) enabling efficient searching within text content. SmartInfo uses this for searching news items, with `zhparser` for Chinese language support.

## H

*   **Hook (React Hook)**
    *   **Scope:** Frontend
    *   **Definition:** Functions (e.g., `useState`, `useEffect`, `useContext`) that allow function components in React to use state and other React features.

*   **HOC (Higher-Order Component)**
    *   **Scope:** Frontend
    *   **Definition:** A function that takes a component and returns a new component, often used for reusing component logic or wrapping components with shared functionality.
    *   **Key Modules/Files:** `frontend/src/components/auth/withAuth.tsx`.

## J

*   **JSDoc**
    *   **Scope:** Frontend
    *   **Definition:** A markup language used to annotate JavaScript and TypeScript code, allowing documentation to be generated from comments. Used in SmartInfo frontend.

*   **JSX (JavaScript XML)**
    *   **Scope:** Frontend
    *   **Definition:** A syntax extension for JavaScript used with React to describe UI structure, resembling HTML.

*   **JWT (JSON Web Token)**
    *   **Scope:** Full-Stack (Authentication)
    *   **Definition:** A compact, URL-safe means of representing claims to be transferred between two parties, used in SmartInfo for user authentication access tokens.
    *   **Key Modules/Files:** `backend/core/security.py`.

## L

*   **LLM (Large Language Model)**
    *   **Scope:** Backend / General AI
    *   **Definition:** Advanced AI models used in SmartInfo for tasks like link extraction, summarization, and analysis.

*   **LLMClientPool**
    *   **Scope:** Backend
    *   **Definition:** A class (`core.llm.pool.LLMClientPool`) that manages a pool of `AsyncLLMClient` instances for efficient reuse.

## M

*   **Mermaid.js**
    *   **Scope:** General (Documentation)
    *   **Definition:** A JavaScript-based diagramming tool that uses Markdown-inspired text to create diagrams. Used in SmartInfo documentation.

*   **Mocking (Testing)**
    *   **Scope:** Full-Stack (Testing)
    *   **Definition:** Replacing parts of the system with controlled "fake" objects (mocks) during testing to isolate code and simulate dependencies.
    *   **Key Modules/Files:** `TESTING_GUIDE.md` (BE & FE).

## N

*   **Next.js**
    *   **Scope:** Frontend
    *   **Definition:** The React framework used for the SmartInfo frontend, providing features like file-system routing and server-side rendering capabilities.

## O

*   **OpenAPI**
    *   **Scope:** Backend (API Documentation)
    *   **Definition:** A specification for building APIs. FastAPI automatically generates an OpenAPI schema for the SmartInfo API.
    *   **Related Terms:** `Swagger UI`, `ReDoc`.

## P

*   **Page (Next.js Page)**
    *   **Scope:** Frontend
    *   **Definition:** A React component in `frontend/src/pages` that corresponds to a specific application route.

*   **PlaywrightCrawler**
    *   **Scope:** Backend
    *   **Definition:** A core crawler component (`core.crawler.PlaywrightCrawler`) using Playwright for browser automation to fetch web content, especially for JavaScript-heavy pages.

*   **PostgreSQL (Postgres)**
    *   **Scope:** Backend
    *   **Definition:** The relational database management system (RDBMS) used by SmartInfo.

*   **Prompt (System Prompt)**
    *   **Scope:** Backend (LLM Interaction)
    *   **Definition:** A set of instructions given to an LLM to guide its behavior and output for a specific task.
    *   **Key Modules/Files:** `backend/utils/prompt.py`, `LLM_INTEGRATION_GUIDE.md` (BE).

*   **Props (React Props)**
    *   **Scope:** Frontend
    *   **Definition:** Read-only inputs to React components, passed from parent to child to configure behavior or appearance.

*   **Pub/Sub (Publish/Subscribe)**
    *   **Scope:** Backend (Real-time communication)
    *   **Definition:** A messaging pattern where "publishers" (e.g., Celery tasks) send messages to "channels" (Redis) without direct knowledge of "subscribers" (e.g., WebSocket manager). Used for real-time progress updates.

*   **Pydantic**
    *   **Scope:** Backend
    *   **Definition:** A Python library for data validation and settings management using Python type annotations. Used for API request/response schemas and data models.
    *   **Key Modules/Files:** `backend/models/schemas/`.

*   **Pytest**
    *   **Scope:** Backend (Testing)
    *   **Definition:** The primary testing framework used for the SmartInfo backend.

## R

*   **React Testing Library (RTL)**
    *   **Scope:** Frontend (Testing)
    *   **Definition:** A testing utility for React components that encourages testing from the user's perspective.

*   **Redis**
    *   **Scope:** Backend
    *   **Definition:** An in-memory data store used as Celery message broker, Celery result backend, and Pub/Sub mechanism for WebSocket progress updates.

*   **Repository Pattern**
    *   **Scope:** Backend (Database Interaction)
    *   **Definition:** An architectural pattern abstracting data access logic. Repository classes (e.g., `NewsRepository`) provide an interface for services to interact with database entities.
    *   **Key Modules/Files:** Files within `backend/db/repositories/`.

## S

*   **Schema (Database Schema)**
    *   **Scope:** Backend
    *   **Definition:** The structure of the database (tables, columns, relationships).
    *   **Key Modules/Files:** `backend/db/schema_constants.py`, `DATABASE_SCHEMA.md` (BE).

*   **Schema (Pydantic Schema / TypeScript Interface)**
    *   **Scope:** Backend (Pydantic) / Frontend (TypeScript)
    *   **Definition:** Defines the structure and types of data objects (e.g., API requests/responses, internal data structures).

*   **Service (Frontend Service)**
    *   **Scope:** Frontend
    *   **Definition:** A TypeScript module in `frontend/src/services/` that encapsulates API calls to specific backend resources.

*   **Service Layer (Backend Service)**
    *   **Scope:** Backend
    *   **Definition:** An architectural layer (`backend/services/`) containing classes that encapsulate core business logic, orchestrating operations between API routers and repositories.

*   **Side Effects (Function/Method)**
    *   **Scope:** General (Programming)
    *   **Definition:** Modifications a function or method makes to state outside of its local scope (e.g., database changes, external API calls, modifying input arguments in-place, logging). Critical to document for AI.

*   **State (React State)**
    *   **Scope:** Frontend
    *   **Definition:** Data that a React component maintains and can change over time, leading to UI re-renders. Can be local or global (via Context).

*   **Step Codes (News Fetching)**
    *   **Scope:** Backend (Celery Tasks / WebSockets)
    *   **Definition:** Integer codes (`backend/background/tasks/step_codes.py`) representing stages in the news fetching workflow, used in progress messages.

*   **Streaming**
    *   **Scope:** Full-Stack
    *   **Definition:** The process of sending or receiving data in a continuous flow of chunks rather than a single complete payload. Used for LLM responses in chat and news analysis.
    *   **Key Modules/Files:** `backend/core/llm/client.py` (BE), `frontend/src/streaming/AnalysisStreamManager.ts` (FE), `frontend/src/pages/chat/[id].tsx` (FE).

*   **Swagger UI**
    *   **Scope:** Backend (API Documentation)
    *   **Definition:** A tool providing an interactive UI for exploring APIs documented with OpenAPI. Accessible at `/docs` on the backend.

## T

*   **Task Group ID**
    *   **Scope:** Backend (Celery / WebSockets)
    *   **Definition:** A unique UUID string generated for a multi-source news fetch operation, grouping related Celery tasks and used as a channel ID for WebSocket progress updates.

*   **Token (Access Token / JWT)**
    *   **Scope:** Full-Stack (Authentication)
    *   **Definition:** A JSON Web Token issued upon successful login, used to authorize API requests.

*   **Type Hinting (Python - PEP 484)**
    *   **Scope:** Backend
    *   **Definition:** Using Python type annotations to specify expected types, aiding static analysis and code clarity.

*   **TypeScript**
    *   **Scope:** Frontend
    *   **Definition:** A superset of JavaScript that adds static typing, used for developing the SmartInfo frontend.

## U

*   **User Data Ownership**
    *   **Scope:** Backend (Authorization)
    *   **Definition:** A core security principle in SmartInfo where most data entities are associated with a `user_id`, and users can only access/modify their own data.

*   **`user-event` (`@testing-library/user-event`)**
    *   **Scope:** Frontend (Testing)
    *   **Definition:** A companion library for React Testing Library that provides more realistic simulation of user interactions.

## W

*   **WebSocket (WS)**
    *   **Scope:** Full-Stack (Real-time Communication)
    *   **Definition:** A protocol for full-duplex communication over a single TCP connection, used for real-time progress updates from backend to frontend.
    *   **Key Modules/Files:** `backend/api/routers/tasks.py`, `backend/core/ws_manager.py`.

*   **WebSocket Manager (`ws_manager`)**
    *   **Scope:** Backend
    *   **Definition:** The `ConnectionManager` instance (`core.ws_manager.ws_manager`) that tracks active WebSocket connections and broadcasts messages.

*   **Workflow**
    *   **Scope:** General (Project Design)
    *   **Definition:** A sequence of steps or operations in a complex process, often spanning multiple components (e.g., News Fetching and Analysis Workflow).
    *   **Key Modules/Files:** `backend/core/workflow/`, `docs/backend/WORKFLOWS/`, `docs/frontend/KEY_USER_FLOWS_FRONTEND.md`.

---