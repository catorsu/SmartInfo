# SmartInfo Backend API Reference Guide

## 1. Introduction

This guide provides an overview of the SmartInfo Backend API, its authentication mechanism, common patterns, and examples for key endpoints. For detailed, interactive API documentation, please refer to the auto-generated:

*   **Swagger UI:** `http://<your_backend_host>/docs`
*   **ReDoc:** `http://<your_backend_host>/redoc`

The Pydantic models defining the exact request and response schemas can be found in the `backend/models/schemas/` directory.

### 1.1. Base URL
All API endpoints are prefixed with `/api`. The full base URL depends on your deployment. For local development, it's typically:
`http://localhost:8000/api`

### 1.2. API Versioning
Currently, all endpoints are unversioned (considered v1). Future versions might be introduced with a path prefix (e.g., `/api/v2/...`).

## 2. Authentication

The SmartInfo API uses **JWT (JSON Web Tokens)** for authentication.

*   **Mechanism:** Bearer Token Authentication.
*   **Obtaining a Token:** Clients must first authenticate via the `POST /api/auth/token` endpoint using username and password (OAuth2PasswordRequestForm). A successful login returns an `access_token`.
*   **Using the Token:** The `access_token` must be included in the `Authorization` header of subsequent requests to protected endpoints, prefixed with `Bearer `.
    ```
    Authorization: Bearer <your_access_token>
    ```
*   **Token Expiration:** Access tokens have an expiration time (currently configured in `backend/core/security.py` - `ACCESS_TOKEN_EXPIRE_MINUTES`). Clients should be prepared to handle token expiry (e.g., by redirecting to login).
*   **Protected Endpoints:** Most endpoints require authentication. Unauthenticated access to protected endpoints will result in a `401 Unauthorized` error.

## 3. Common HTTP Status Codes & Error Responses

*   **`200 OK`:** Request successful.
*   **`201 Created`:** Resource successfully created (e.g., after a `POST` request).
*   **`202 Accepted`:** Request accepted for processing, but processing is not yet complete (e.g., for starting background tasks).
*   **`204 No Content`:** Request successful, but no content to return (e.g., after a `DELETE` request).
*   **`400 Bad Request`:** The request was malformed or contained invalid data (e.g., missing required fields, invalid values that don't match Pydantic models). The response body often contains a `detail` field with more information.
    ```json
    {
        "detail": "Invalid input data." // Or more specific Pydantic validation errors
    }
    ```
*   **`401 Unauthorized`:** Authentication is required and has failed or has not yet been provided. The `WWW-Authenticate: Bearer` header is usually included.
    ```json
    {
        "detail": "Not authenticated"
    }
    ```
    or
    ```json
    {
        "detail": "Could not validate credentials"
    }
    ```
*   **`403 Forbidden`:** The authenticated user does not have permission to perform the requested action (e.g., trying to access another user's resources).
    ```json
    {
        "detail": "Access denied to resource."
    }
    ```
*   **`404 Not Found`:** The requested resource could not be found.
    ```json
    {
        "detail": "Resource with ID X not found or not owned by user."
    }
    ```
*   **`409 Conflict`:** The request could not be completed due to a conflict with the current state of the resource (e.g., trying to create a resource with a unique field that already exists).
    ```json
    {
        "detail": "Resource with name 'X' already exists."
    }
    ```
*   **`422 Unprocessable Entity`:** The request was well-formed but contained semantic errors, typically from Pydantic validation failures for request bodies. The response body will contain details about the validation errors.
    ```json
    {
        "detail": [
            {
                "loc": ["body", "title"],
                "msg": "field required",
                "type": "value_error.missing"
            }
        ]
    }
    ```
*   **`500 Internal Server Error`:** An unexpected error occurred on the server.
    ```json
    {
        "detail": "An internal server error occurred."
    }
    ```

## 4. API Endpoints

Endpoints are grouped by resource type.

### 4.1. Authentication (`/api/auth`)

Handles user registration, login (token generation), and user information.

*   **`POST /api/auth/register`**
    *   **Description:** Registers a new user.
    *   **Request Body:** `UserCreate` schema (username, password).
        ```json
        {
            "username": "newuser",
            "password": "securepassword123"
        }
        ```
    *   **Success Response (201 Created):** `TokenWithUser` schema (access_token, token_type, user details).
        ```json
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "id": 2,
                "username": "newuser"
            }
        }
        ```
    *   **Error Responses:** `400 Bad Request` (e.g., username already exists).

*   **`POST /api/auth/token`**
    *   **Description:** Authenticates a user and returns an access token. Uses `application/x-www-form-urlencoded` content type.
    *   **Request Body (Form Data):**
        *   `username`: User's username
        *   `password`: User's password
    *   **Success Response (200 OK):** `TokenWithUser` schema.
    *   **Error Responses:** `401 Unauthorized` (incorrect credentials).

*   **`GET /api/auth/users/me`**
    *   **Description:** Retrieves the details of the currently authenticated user.
    *   **Authentication:** Required (Bearer Token).
    *   **Success Response (200 OK):** `User` schema.
        ```json
        {
            "id": 1,
            "username": "currentuser"
        }
        ```
    *   **Error Responses:** `401 Unauthorized`.

*   **`PUT /api/auth/users/me/password`**
    *   **Description:** Changes the password for the currently authenticated user.
    *   **Authentication:** Required.
    *   **Request Body:** `PasswordChangeRequest` schema.
        ```json
        {
            "current_password": "oldpassword",
            "new_password": "newstrongpassword"
        }
        ```
    *   **Success Response (200 OK):** `{"message": "Password updated successfully"}`.
    *   **Error Responses:** `400 Bad Request` (e.g., incorrect current password), `401 Unauthorized`.

*   **`PUT /api/auth/users/me/username`**
    *   **Description:** Changes the username for the currently authenticated user.
    *   **Authentication:** Required.
    *   **Request Body:** `UsernameChangeRequest` schema.
        ```json
        {
            "new_username": "new_username_here",
            "current_password": "current_password_for_verification"
        }
        ```
    *   **Success Response (200 OK):** `User` schema (updated user).
    *   **Error Responses:** `400 Bad Request` (e.g., incorrect password), `401 Unauthorized`, `409 Conflict` (username taken).

### 4.2. News (`/api/news`)

Manages news items, sources, and categories for the authenticated user. Also includes endpoints for triggering news fetching and analysis tasks.

*   **Authentication:** All endpoints in this group require Bearer Token authentication.

*   **News Items (`/items`)**
    *   **`GET /api/news/items`**: Lists news items for the user. Supports pagination (`page`, `page_size`) and filtering (`category_id`, `source_id`, `analyzed`, `search_term`, `fetch_date`, `sort_by`).
        *   **Success Response (200 OK):** `NewsItemsPage` schema (e.g., `{"items": List[NewsResponse], "total": int, "page": int, "page_size": int}`)
    *   **`POST /api/news/items`**: Creates a new news item.
        *   **Request Body:** `NewsCreate` schema.
        *   **Success Response (201 Created):** `NewsResponse`
    *   **`GET /api/news/items/{news_id}`**: Retrieves a specific news item.
        *   **Success Response (200 OK):** `NewsResponse`
    *   **`PUT /api/news/items/{news_id}/analysis`**: Updates the analysis for a news item.
        *   **Request Body:** `UpdateAnalysisRequest` schema (`{"analysis": "new analysis text"}`).
        *   **Success Response (200 OK):** `{"message": "Analysis updated..."}`
    *   **`DELETE /api/news/items/{news_id}`**: Deletes a news item.
        *   **Success Response (204 No Content)**
    *   **`DELETE /api/news/items/clear`**: Clears all news items for the user.
        *   **Success Response (204 No Content)**

*   **News Sources (`/sources`)**
    *   **`GET /api/news/sources`**: Lists all news sources for the user.
        *   **Success Response (200 OK):** `List[NewsSourceResponse]`
    *   **`POST /api/news/sources`**: Creates a new news source.
        *   **Request Body:** `NewsSourceCreate` schema.
        *   **Success Response (201 Created):** `NewsSourceResponse`
    *   **`GET /api/news/sources/{source_id}`**: Retrieves a specific news source.
        *   **Success Response (200 OK):** `NewsSourceResponse`
    *   **`PUT /api/news/sources/{source_id}`**: Updates a news source.
        *   **Request Body:** `NewsSourceUpdate` schema.
        *   **Success Response (200 OK):** `NewsSourceResponse`
    *   **`DELETE /api/news/sources/{source_id}`**: Deletes a news source.
        *   **Success Response (204 No Content)**

*   **News Categories (`/categories`)**
    *   **`GET /api/news/categories`**: Lists all news categories for the user, including source counts.
        *   **Success Response (200 OK):** `List[NewsCategoryResponse]`
    *   **`POST /api/news/categories`**: Creates a new news category.
        *   **Request Body:** `NewsCategoryCreate` schema.
        *   **Success Response (201 Created):** `NewsCategoryResponse`
    *   **`PUT /api/news/categories/{category_id}`**: Updates a news category.
        *   **Request Body:** `NewsCategoryUpdate` schema.
        *   **Success Response (200 OK):** `NewsCategoryResponse`
    *   **`DELETE /api/news/categories/{category_id}`**: Deletes a news category.
        *   **Success Response (204 No Content)**

*   **News Tasks (`/tasks`)**
    *   **`POST /api/news/tasks/fetch/batch-group`**: Initiates batch fetching of news from specified source IDs.
        *   **Request Body:** `FetchSourceBatchRequest` schema (`{"source_ids": [1, 2, 3]}`).
        *   **Success Response (202 Accepted):** `{"task_group_id": "uuid", "message": "Batch fetch group scheduled..."}`
    *   **`POST /api/news/items/{news_id}/analyze/stream`**: Streams LLM-generated analysis for a specific news item.
        *   **Query Parameter:** `force=true` (optional) to force re-analysis.
        *   **Success Response (200 OK):** `StreamingResponse` (text/plain chunks of analysis).

*   **Fetch History (`/fetch-history`)**
    *   **`GET /api/news/fetch-history`**: Retrieves fetch history records for the user.
        *   **Query Parameters:** `record_date` (YYYY-MM-DD), `start_date`, `end_date`.
        *   **Success Response (200 OK):** `List[FetchHistoryItemResponse]`

### 4.3. Chat (`/api/chat`)

Manages chat sessions and messages for the authenticated user, including LLM interaction.

*   **Authentication:** All endpoints require Bearer Token authentication.

*   **Chat Sessions**
    *   **`GET /api/chat/`**: Lists all chat sessions for the user.
        *   **Success Response (200 OK):** `List[ChatListResponseItem]`
    *   **`POST /api/chat/`**: Creates a new chat session.
        *   **Request Body:** `ChatCreate` schema (`{"title": "Initial chat title"}`).
        *   **Success Response (201 Created):** `ChatResponse` (includes empty messages list).
    *   **`GET /api/chat/{chat_id}`**: Retrieves a specific chat session, including its messages.
        *   **Success Response (200 OK):** `ChatResponse`
    *   **`PUT /api/chat/{chat_id}`**: Updates the title of a chat session.
        *   **Request Body:** `ChatCreate` schema (only `title` is used).
        *   **Success Response (200 OK):** `ChatResponse`
    *   **`DELETE /api/chat/{chat_id}`**: Deletes a chat session and its messages.
        *   **Success Response (204 No Content)**

*   **Messages**
    *   **`GET /api/chat/{chat_id}/messages`**: Lists all messages for a specific chat session.
        *   **Success Response (200 OK):** `List[MessageResponse]`
    *   **`POST /api/chat/messages`**: Adds a new message to a chat session.
        *   **Request Body:** `MessageCreate` schema (`{"chat_id": 1, "sender": "user", "content": "Hello AI"}`).
        *   **Success Response (201 Created):** `MessageResponse`
    *   *(GET and DELETE for individual messages by `/messages/{message_id}` are also available but less commonly used directly by UIs compared to chat-scoped operations.)*

*   **LLM Interaction**
    *   **`POST /api/chat/ask`**: Sends a question to the LLM within the context of a chat session (or a new one if `chat_id` is omitted and backend logic supports it - current SmartInfo requires `chat_id` for `/ask`). Streams the response.
        *   **Request Body:** `Question` schema (`{"content": "What is FastAPI?", "chat_id": 123}`).
        *   **Success Response (200 OK):** `StreamingResponse` (text/plain chunks of LLM response).
        *   **Error Example (400 Bad Request if `chat_id` is missing or invalid):**
            ```json
            {
                "detail": "chat_id is required for streaming responses."
            }
            ```

### 4.4. Settings (`/api/settings`)

Manages API key configurations and general application preferences for the authenticated user.

*   **Authentication:** All endpoints require Bearer Token authentication.

*   **API Keys (`/api_keys`)**
    *   **`GET /api/settings/api_keys`**: Lists all API keys for the user.
        *   **Success Response (200 OK):** `List[ApiKeyResponse]` (note: `api_key` field itself is not returned for security).
    *   **`POST /api/settings/api_keys`**: Creates a new API key configuration.
        *   **Request Body:** `ApiKeyCreate` schema.
        *   **Success Response (201 Created):** `ApiKeyResponse`
    *   **`GET /api/settings/api_keys/{api_key_id}`**: Retrieves a specific API key configuration (excluding the key value).
        *   **Success Response (200 OK):** `ApiKeyResponse`
    *   **`PUT /api/settings/api_keys/{api_key_id}`**: Updates an API key configuration.
        *   **Request Body:** `ApiKeyUpdate` schema.
        *   **Success Response (200 OK):** `ApiKeyResponse`
    *   **`DELETE /api/settings/api_keys/{api_key_id}`**: Deletes an API key configuration.
        *   **Success Response (204 No Content)**
    *   **`POST /api/settings/api_keys/{api_key_id}/test`**: Tests the connection for a specific API key.
        *   **Success Response (200 OK):** `{"status": "success"}` or `{"status": "error", "error": "...", "message": "..."}`

*   **User Preferences (`/settings`)**
    *   **`GET /api/settings/settings`**: Retrieves all application settings for the user.
        *   **Success Response (200 OK):** `Dict[str, Any]` (e.g., `{"llm_default_model": "deepseek-chat"}`).
    *   **`PUT /api/settings/settings`**: Updates application settings for the user.
        *   **Request Body:** `UserPreferenceUpdate` schema (`{"settings": {"key1": "value1"}}`).
        *   **Success Response (200 OK):** `Dict[str, Any]` (updated settings).
    *   **`POST /api/settings/settings/reset`**: Resets application settings to their defaults for the user.
        *   **Success Response (200 OK):** `Dict[str, Any]` (default settings).

### 4.5. Tasks (`/api/tasks`)

Provides endpoints for monitoring background task progress, primarily via WebSockets.

*   **`WS /api/tasks/ws/tasks/group/{task_group_id}`**
    *   **Description:** WebSocket endpoint for real-time progress updates for a specific task group.
    *   **Authentication:** Requires a `token` query parameter containing the JWT access token.
    *   **Path Parameter:** `task_group_id` (string UUID obtained from task initiation endpoints like news batch fetch).
    *   **Messages Sent by Server:** JSON objects describing task progress. Key events include:
        *   `{"event": "source_progress", "source_id": 123, "step": 2, "progress": 25.0}` (See `backend/background/tasks/step_codes.py` for step codes).
        *   `{"event": "batch_task_completed", "task_id": "celery_task_id", "items_saved": 5, "affected_source_ids": [1,2,3]}`
        *   `{"event": "overall_batch_completed", "task_group_id": "uuid", "status": "SUCCESS" | "PARTIAL_SUCCESS" | "FAILURE"}`
        *   `{"event": "error", "message": "Error details"}`
    *   **Connection Lifecycle:** Client connects, authenticates via token. Server sends updates as they occur via Redis Pub/Sub. Connection closes when client disconnects or server initiates closure (e.g., after "overall_batch_completed").

## 5. Rate Limiting

Currently, no explicit rate limiting is implemented on the API. This may be added in future versions if required. Please use the API responsibly.

---
This API Reference Guide should serve as a good starting point for understanding and interacting with the SmartInfo backend.