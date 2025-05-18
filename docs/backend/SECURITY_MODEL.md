# SmartInfo Backend: Security Model

## 1. Introduction

This document outlines the security model, mechanisms, and best practices employed by the SmartInfo backend. The primary goal is to protect user accounts, ensure data privacy and integrity through proper authentication and authorization, and mitigate common web application vulnerabilities.

All developers, including AI assistants, must understand and adhere to these security principles when contributing to the project.

## 2. Authentication

Authentication is the process of verifying a user's identity. SmartInfo uses JSON Web Tokens (JWTs).

### 2.1. Mechanism
*   **JWT Standard:** Tokens are compliant with the JWT standard.
*   **Token Type:** Bearer Tokens.

### 2.2. Authentication Flow
1.  **Login Request:** The user (via the client) submits their `username` and `password` to the `POST /api/auth/token` endpoint. This endpoint expects `application/x-www-form-urlencoded` data (as per `OAuth2PasswordRequestForm`).
2.  **Credential Verification:** The `AuthService` verifies the credentials against the `users` table (hashed passwords).
3.  **Token Issuance:** Upon successful verification, `core.security.create_access_token()` generates a JWT.
    *   The token payload includes a `sub` (subject) claim containing the `user.id`.
    *   It also includes an `exp` (expiration) claim.
4.  **Token Response:** The API returns the `access_token` and `token_type: "bearer"` to the client, along with basic user details.

### 2.3. Token Usage
*   For subsequent requests to protected API endpoints, the client **MUST** include the `access_token` in the `Authorization` HTTP header, prefixed with `Bearer `.
    ```
    Authorization: Bearer <your_access_token>
    ```

### 2.4. Token Validation
*   Protected FastAPI endpoints use the `Depends(get_current_active_user)` dependency (defined in `api.dependencies.dependencies`).
*   This dependency uses the `OAuth2PasswordBearer` scheme to extract the token from the `Authorization` header.
*   `core.security.decode_access_token()` is called to validate the token's signature, check for expiration, and decode its payload.
*   If the token is valid, the `user_id` from the `sub` claim is used to fetch the user's details from the database via `UserRepository`.
*   If any step fails (token missing, invalid, expired, user not found), an `HTTPException` (typically `401 Unauthorized`) is raised.

### 2.5. Token Expiration
*   Access tokens have a defined lifetime, configured by `ACCESS_TOKEN_EXPIRE_MINUTES` in `core.security.py` (default: 6000 minutes).
*   Clients should be prepared to handle token expiration (e.g., by receiving a `401 Unauthorized` response) and typically redirect the user to log in again to obtain a new token. No refresh token mechanism is currently implemented.

## 3. Password Management

*   **Hashing:** User passwords are **NEVER** stored in plain text.
    *   `core.security.get_password_hash(password)` uses `bcrypt` to generate a strong, salted hash of the user's password during registration or password change.
    *   `core.security.verify_password(plain_password, hashed_password)` is used during login to compare a provided password against the stored hash.
*   **Storage:** Hashed passwords are stored in the `hashed_password` column of the `users` table.
*   **Password Change:** The `PUT /api/auth/users/me/password` endpoint allows authenticated users to change their password after verifying their current password.

## 4. Authorization (Access Control)

Authorization determines what an authenticated user is permitted to do.

### 4.1. Primary Model: User Data Ownership
*   The core authorization principle in SmartInfo is **data ownership**. Most resources are directly associated with a `user_id`.
*   Examples:
    *   `news`, `news_sources`, `news_category`
    *   `api_config` (LLM API keys)
    *   `user_preferences`
    *   `chats`, `messages`
    *   `fetch_history`
*   Users can only access, modify, or delete resources they own.

### 4.2. Enforcement
*   **Service Layer:** Service methods consistently receive the authenticated `user_id` (from `Depends(get_current_active_user)` in the API router) as a parameter.
*   **Repository Layer:** Repository queries are constructed to include a `WHERE user_id = $X` clause, ensuring that database operations are scoped to the authenticated user's data.
    *   For example, `NewsRepository.get_by_id(news_id, user_id)` will only return a news item if it exists *and* belongs to that `user_id`.
*   **Consequences of Violation:** Attempting to access or modify another user's resource typically results in a `404 Not Found` (as if the resource doesn't exist for the requesting user) or a `403 Forbidden` response.

### 4.3. Role-Based Access Control (RBAC)
*   Currently, SmartInfo **does not** implement a complex Role-Based Access Control system (e.g., admin users, editors). All authenticated users have the same level of permissions with respect to their own data.
*   This could be a future enhancement if different user roles with varying capabilities are required.

## 5. API Key Security (User-Provided LLM Keys)

Users can store API keys for external LLM services.

*   **Storage:**
    *   Stored in the `api_config` table, linked to a `user_id`.
    *   The `api_key` column currently stores the key as `TEXT`.
    *   **Security Note & Future Enhancement:** For enhanced security, API keys stored in the database should ideally be **encrypted at rest**. This is a planned future improvement. Until then, database access security is paramount.
*   **Transmission to Backend:** Assumed to occur over HTTPS when the user configures their API key via the frontend.
*   **Usage by Backend:**
    *   When a user performs an action requiring an LLM (e.g., chat, analysis), the relevant service (`ChatService`, `NewsService`) retrieves the user's *own* API key configuration(s) from `ApiKeyRepository`.
    *   The decrypted (if encrypted in the future) API key is used to instantiate an `AsyncLLMClient` or `LLMClientPool` specifically for that user's request.
    *   Keys are used for server-to-LLM API communication and are **not** exposed back to the client/frontend beyond the user's own settings management interface.
*   **Testing API Keys:** The `POST /api/settings/api_keys/{api_key_id}/test` endpoint allows users to test their key. The backend makes a simple test call to the LLM API using that key.

## 6. Input Validation

*   **Pydantic Models:** FastAPI extensively uses Pydantic models (defined in `backend/models/schemas/`) for request body validation, query parameter validation, and response serialization.
    *   This automatically handles type checking, presence of required fields, format validation (e.g., for URLs), and constraints (e.g., `max_length`).
    *   If validation fails, FastAPI automatically returns a `422 Unprocessable Entity` response with detailed error messages.
*   **Service-Level Validation:** Additional business logic validation (e.g., checking if a `category_id` provided in a request actually belongs to the authenticated user) is performed within the service layer.

## 7. Protection Against Common Web Vulnerabilities

*   **SQL Injection (SQLi):**
    *   Mitigated by the use of `asyncpg` with parameterized queries. Repositories construct queries using placeholders (e.g., `$1`, `$2`), and `asyncpg` handles proper escaping.
    *   Direct construction of SQL strings with unvalidated user input is strictly avoided.
*   **Cross-Site Scripting (XSS):**
    *   The backend API primarily returns JSON data. It is the frontend's responsibility to properly sanitize and encode any data before rendering it in HTML to prevent XSS.
    *   FastAPI's default JSON response mechanism does not inherently create XSS vulnerabilities in the API itself.
*   **Cross-Site Request Forgery (CSRF):**
    *   As the API primarily uses JWT Bearer tokens passed in the `Authorization` header (stateless authentication), it is generally not susceptible to traditional CSRF attacks that rely on cookies automatically sent by browsers.
    *   Standard CSRF protection mechanisms (like CSRF tokens) are not typically required for this authentication model.
*   **Insecure Direct Object References (IDOR):**
    *   Mitigated by the strict user data ownership model (see Section 4. Authorization). All data access is scoped by the authenticated `user_id`.
*   **Dependency Security:**
    *   Regularly update dependencies (Python packages) to patch known vulnerabilities. Tools like `poetry show --outdated` can help identify outdated packages. `Dependabot` or similar services should be considered.

## 8. HTTPS (Transport Layer Security)

*   For any production or publicly accessible deployment, the SmartInfo backend **MUST** be served over HTTPS.
*   HTTPS encrypts data in transit, protecting sensitive information such as user credentials (passwords during login), JWT access tokens, and user-provided LLM API keys.
*   This is typically handled by a reverse proxy (e.g., Nginx, Traefik) in front of the Uvicorn server, which manages SSL/TLS certificates.

## 9. Logging and Monitoring

*   The application implements structured logging (see `main.py`).
*   Security-relevant events (e.g., failed login attempts, authorization failures, significant errors) should be logged.
*   In a production environment, these logs should be ingested into a centralized logging system and monitored for suspicious activity or attack patterns. (Specific monitoring tools are outside the scope of this document).

## 10. Security as an Evolving Concern

Security is an ongoing process. This document reflects the current security model. As new features are added or the threat landscape changes, this model and its implementations will be reviewed and updated. Developers should always code with security in mind.
