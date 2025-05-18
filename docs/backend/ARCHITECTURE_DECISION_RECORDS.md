# SmartInfo Backend: Architecture Decision Records (ADRs)

## 1. Introduction

This document records significant architectural decisions made for the SmartInfo backend. Each record outlines the context of the decision, the decision itself, and the rationale behind it. ADRs serve as a historical log and a guide for future development, ensuring that the reasoning behind key choices is understood and can be built upon.

This helps both human developers and AI assistants to:
*   Understand why the system is designed the way it is.
*   Make informed decisions when extending or modifying the system.
*   Avoid re-evaluating previously considered options without new context.

---

## ADR-001: Choice of FastAPI as the Primary Web Framework

*   **Status:** Accepted
*   **Context:**
    *   The SmartInfo backend requires a modern, high-performance API layer to serve the frontend and potentially other clients.
    *   Key requirements include support for asynchronous operations (for I/O-bound tasks like database calls and external API interactions), automatic data validation, and good developer experience.
*   **Decision:**
    *   FastAPI was chosen as the primary web framework for building the backend API.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **Asynchronous Support:** Native `async`/`await` syntax aligns well with I/O-bound operations, improving concurrency and performance.
        *   **Performance:** FastAPI is known for its high performance, comparable to Node.js and Go, due to Starlette and Pydantic.
        *   **Data Validation:** Built-in integration with Pydantic for request/response validation is robust and reduces boilerplate. This is excellent for data integrity and API contract enforcement, beneficial for AI understanding of data shapes.
        *   **Automatic API Documentation:** OpenAPI (Swagger UI & ReDoc) generation out-of-the-box from code and Pydantic models, which is invaluable for developers and AI clients.
        *   **Dependency Injection:** FastAPI's dependency injection system simplifies managing dependencies (like database connections, services) and improves testability.
        *   **Developer Experience:** Python-based, with modern features and a growing community.
    *   **Alternatives Considered:**
        *   **Flask:** Mature and flexible, but asynchronous support is less native (requires extensions like Quart), and data validation/docs are not as tightly integrated.
        *   **Django/Django REST framework:** More full-featured and "batteries-included," but can be heavier for an API-first backend. Asynchronous support has improved but FastAPI was designed async-first.
    *   **Trade-offs:** FastAPI is less opinionated than Django in some areas (e.g., ORM choice, project structure), requiring more explicit setup for certain components. This was deemed acceptable for the flexibility it offers.

---

## ADR-002: Asynchronous Task Processing with Celery and Redis

*   **Status:** Accepted
*   **Context:**
    *   SmartInfo requires background processing for long-running, resource-intensive tasks like fetching news from multiple sources, crawling web pages, and performing LLM-based analysis, without blocking API responses.
    *   A robust progress reporting mechanism is needed for these background tasks.
*   **Decision:**
    *   Celery was chosen as the distributed task queue framework.
    *   Redis was chosen as both the message broker and the result backend for Celery.
    *   Redis Pub/Sub is used as an intermediary for broadcasting real-time progress updates from Celery tasks to WebSocket clients.
*   **Rationale/Consequences:**
    *   **Benefits of Celery:**
        *   Mature, widely adopted, and feature-rich for distributed task processing.
        *   Good integration with Python.
        *   Supports complex workflows like `chord` for batching with callbacks (used in news fetching).
        *   Scalable by adding more Celery workers.
    *   **Benefits of Redis:**
        *   Fast in-memory data store, suitable for message broking and result storage.
        *   Provides Pub/Sub functionality, which decouples task progress publishing from direct WebSocket management, allowing workers to be independent of the API server handling WebSockets.
        *   Relatively simple to set up and manage.
    *   **Progress Reporting:** The Redis Pub/Sub -> WebSocket Manager -> Client architecture provides a scalable way to deliver real-time updates without Celery workers needing direct knowledge of WebSocket clients.
    *   **Alternatives Considered:**
        *   **FastAPI BackgroundTasks:** Suitable for very simple, short-lived tasks that don't require a separate worker process or persistence. Not robust enough for SmartInfo's news fetching.
        *   **RQ (Redis Queue):** Simpler than Celery, but less feature-rich, especially for complex workflows like chords.
        *   **Dramatiq:** Another alternative, but Celery has a larger community and more extensive integrations.
    *   **Trade-offs:** Celery adds an extra component to manage (workers, broker). The complexity of setting up chords and managing task state requires careful implementation.

---

## ADR-003: Database Choice - PostgreSQL with `asyncpg`

*   **Status:** Accepted
*   **Context:**
    *   A relational database is needed for storing structured data like user accounts, news items, sources, categories, API keys, and chat history.
    *   The system requires asynchronous database access to align with FastAPI's asynchronous nature.
    *   Features like JSON support, full-text search, and robust transaction management are desirable.
*   **Decision:**
    *   PostgreSQL was chosen as the relational database system.
    *   `asyncpg` was chosen as the Python library for asynchronous interaction with PostgreSQL.
*   **Rationale/Consequences:**
    *   **Benefits of PostgreSQL:**
        *   Mature, feature-rich, and highly reliable open-source RDBMS.
        *   Strong support for complex queries, transactions, and data integrity (FKs, constraints).
        *   Excellent support for JSON/JSONB data types.
        *   Advanced indexing capabilities, including GIN for Full-Text Search (used with `zhparser` for Chinese content).
    *   **Benefits of `asyncpg`:**
        *   High-performance asynchronous driver specifically for PostgreSQL, designed to be very fast.
        *   Directly integrates with Python's `asyncio`.
    *   **Alternatives Considered:**
        *   **MySQL/MariaDB:** Viable alternatives, but PostgreSQL is often favored for its advanced features and extensibility.
        *   **SQLite:** Suitable for simpler applications or local development, but not robust enough for concurrent access or advanced features needed in a production web application.
        *   **NoSQL Databases (e.g., MongoDB):** Considered, but the relational nature of user data, news categorizations, and chat sessions made an RDBMS a better fit for data integrity and querying complex relationships.
    *   **Trade-offs:** PostgreSQL requires more setup and management than SQLite. `asyncpg` is lower-level than an ORM like SQLAlchemy, requiring manual SQL query writing (managed via the Repository pattern). This provides more control over query performance but can be more verbose.

---

## ADR-004: Service Layer and Repository Pattern Implementation

*   **Status:** Accepted
*   **Context:**
    *   A need to separate business logic from API request handling and direct database interaction to improve modularity, testability, and maintainability.
*   **Decision:**
    *   A **Service Layer** was implemented. Service classes (e.g., `NewsService`, `ChatService`) encapsulate business logic and orchestrate operations.
    *   A **Repository Pattern** was implemented. Repository classes (e.g., `NewsRepository`, `UserRepository`) abstract data access logic for specific database entities.
*   **Rationale/Consequences:**
    *   **Benefits of Service Layer:**
        *   Decouples API routers from the details of business operations and data access. Routers become thin.
        *   Centralizes business logic, making it easier to manage and reuse.
        *   Improves testability: Services can be unit-tested by mocking repositories and other external dependencies.
    *   **Benefits of Repository Pattern:**
        *   Decouples services from the specifics of database interaction (e.g., SQL queries, `asyncpg` usage).
        *   Centralizes data access logic for each entity, making it easier to manage and optimize queries.
        *   Improves testability: Repositories can be tested against a real test database, while services mock them.
        *   Provides a clear contract for data operations.
    *   **Interaction:** API Routers call Services. Services use Repositories.
    *   **Alternatives Considered:**
        *   **Fat Routers/Controllers:** Placing business logic directly in API route handlers. This leads to less modularity and harder testing.
        *   **Full ORM (e.g., SQLAlchemy async):** While providing powerful object-relational mapping, it can sometimes add complexity or overhead not desired for all operations. The current `asyncpg` + Repository approach offers more direct control, with Pydantic models serving for data shaping. This could be revisited if ORM benefits outweigh the control trade-off.
    *   **Trade-offs:** Introduces more layers and classes, which can feel like more boilerplate for very simple CRUD operations. However, the benefits for larger features and maintainability are significant.

---

## ADR-005: User-Specific API Key Management for LLM Access

*   **Status:** Accepted
*   **Context:**
    *   SmartInfo needs to interact with various LLMs. Users may have their own preferences or accounts with different LLM providers.
    *   A centralized application-wide API key for LLMs could be a single point of failure or cost management issue.
*   **Decision:**
    *   Users can configure and store their own LLM API keys in the `api_config` table, linked to their `user_id`.
    *   Each configuration includes the model name, base URL, API key, context window, and max output tokens.
    *   Services (`ChatService`, `NewsService`, Celery tasks) retrieve the relevant user's API key at runtime to instantiate `AsyncLLMClient` or `LLMClientPool`.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **Flexibility for Users:** Users can use their preferred LLM providers and models.
        *   **Cost Management:** Users bear the cost of their LLM usage through their own keys.
        *   **Security Scope:** An individual user's key compromise doesn't affect other users' LLM access through the platform.
        *   **Provider Agnostic:** The system can easily support any OpenAI-compatible API by simply having the user configure the correct base URL and key.
    *   **Alternatives Considered:**
        *   **Centralized Application API Key(s):** Simpler initial setup for the application, but less flexible for users, harder to manage costs per user, and a larger security risk if compromised.
        *   **Marketplace-style integration with LLM providers:** More complex, involves billing integration, beyond current scope.
    *   **Trade-offs:**
        *   Users must obtain and manage their own API keys.
        *   The application needs to securely store and handle these user-provided keys. (Current storage is plain text; **encryption at rest is a noted future enhancement**).
