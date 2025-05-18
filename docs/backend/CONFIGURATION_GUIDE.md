# SmartInfo Backend: Configuration Guide

## 1. Introduction

This guide details how the SmartInfo backend application is configured. Understanding these settings is essential for local development setup, deployment to various environments (development, staging, production), and for troubleshooting.

Configuration is primarily managed through environment variables, which are loaded and made accessible via the `config.py` module.

## 2. Configuration Sources

*   **Environment Variables:** The primary method for configuring the application, especially in containerized or production environments.
*   **.env Files:** For local development, environment variables can be conveniently managed by creating a `.env` file in the `backend/` directory. An example file, `.env.example`, is provided in the main project repository. **The `.env` file itself should not be committed to version control.**

The `python-dotenv` library is used to load variables from the `.env` file into the environment when the application starts.

## 3. Environment Variables

The following environment variables are used to configure the SmartInfo backend. They are accessed within the application primarily through the `config` object instantiated from `backend.config.AppConfig`.

### 3.1. Database Configuration
These variables are crucial for connecting to the PostgreSQL database.

*   **`DB_USER`**
    *   **Purpose:** The username for the PostgreSQL database.
    *   **Required:** Yes.
    *   **Default Value:** None (must be set).
    *   **Example Value:** `smartinfo_user`
    *   **Module(s) Affected:** `backend.config`, `backend.db.connection`

*   **`DB_PASSWORD`**
    *   **Purpose:** The password for the specified PostgreSQL user.
    *   **Required:** Yes.
    *   **Default Value:** None (must be set).
    *   **Example Value:** `s3cureP@ssw0rd`
    *   **Module(s) Affected:** `backend.config`, `backend.db.connection`

*   **`DB_NAME`**
    *   **Purpose:** The name of the PostgreSQL database to connect to.
    *   **Required:** Yes.
    *   **Default Value:** None (must be set).
    *   **Example Value:** `smartinfo_db`
    *   **Module(s) Affected:** `backend.config`, `backend.db.connection`

*   **`DB_HOST`**
    *   **Purpose:** The hostname or IP address of the PostgreSQL server.
    *   **Required:** No.
    *   **Default Value:** `localhost`
    *   **Example Value:** `db.smartinfo.internal` or `192.168.1.100`
    *   **Module(s) Affected:** `backend.config`, `backend.db.connection`

*   **`DB_PORT`**
    *   **Purpose:** The port number on which the PostgreSQL server is listening.
    *   **Required:** No.
    *   **Default Value:** `5432`
    *   **Example Value:** `5433`
    *   **Module(s) Affected:** `backend.config`, `backend.db.connection`

### 3.2. Redis Configuration
Used for Celery message broker, Celery result backend, and WebSocket progress update Pub/Sub.

*   **`REDIS_URL`**
    *   **Purpose:** Connection URL for the Redis instance used as Celery's message broker and for WebSocket Pub/Sub.
    *   **Required:** No.
    *   **Default Value:** `redis://localhost:6379/0` (Database 0)
    *   **Example Value:** `redis://redis.smartinfo.internal:6379/0`
    *   **Module(s) Affected:** `backend.config`, `backend.background.celery_app`, `backend.main` (for WebSocket Redis client)

*   **`REDIS_BACKEND_URL`**
    *   **Purpose:** Connection URL for the Redis instance used as Celery's result backend. Can be the same as `REDIS_URL` but using a different database number is recommended.
    *   **Required:** No.
    *   **Default Value:** `redis://localhost:6379/1` (Database 1)
    *   **Example Value:** `redis://redis.smartinfo.internal:6379/1`
    *   **Module(s) Affected:** `backend.background.celery_app`

### 3.3. Application Behavior
Controls various operational aspects of the backend.

*   **`SECRET_KEY`**
    *   **Purpose:** A secret key used for cryptographic signing, primarily for JWT (JSON Web Tokens) in user authentication. **This MUST be a long, random, and unique string in production.**
    *   **Required:** Yes (though a very insecure default is provided in `core/security.py` if not set, which is **NOT SUITABLE** for production).
    *   **Default Value:** (Insecure default in code, see `backend/core/security.py`)
    *   **Example Value:** `your-very-strong-random-secret-key-here-CHANGE-ME`
    *   **Module(s) Affected:** `backend.core.security` (JWT generation/validation)

*   **`ACCESS_TOKEN_EXPIRE_MINUTES`**
    *   **Purpose:** Defines the validity period for JWT access tokens in minutes.
    *   **Required:** No.
    *   **Default Value:** `6000` (as defined in `backend/core/security.py`)
    *   **Example Value:** `1440` (for 24 hours)
    *   **Module(s) Affected:** `backend.core.security` (JWT generation)

*   **`FETCH_BATCH_SIZE`**
    *   **Purpose:** The number of news sources to process in a single Celery task batch during bulk news fetching.
    *   **Required:** No.
    *   **Default Value:** `5` (as defined in `backend.config.AppConfig`)
    *   **Example Value:** `10`
    *   **Module(s) Affected:** `backend.config`, `backend.api.routers.news` (when dispatching Celery tasks)

*   **`LOG_LEVEL`**
    *   **Purpose:** Sets the logging level for the application (e.g., DEBUG, INFO, WARNING, ERROR).
    *   **Required:** No.
    *   **Default Value:** `INFO` (as defined in `backend.main.py`)
    *   **Example Value:** `DEBUG`
    *   **Module(s) Affected:** `backend.main` (global logging configuration), `uvicorn` log level.

*   **`RELOAD` (For Uvicorn Development Server)**
    *   **Purpose:** Enables or disables auto-reloading for the Uvicorn development server when code changes.
    *   **Required:** No.
    *   **Default Value:** `False` (empty string or not "true" evaluates to false in `main.py`)
    *   **Example Value:** `true`
    *   **Module(s) Affected:** `backend.main.start_api()` (Uvicorn startup)

*   **`HOST` (For Uvicorn Development Server)**
    *   **Purpose:** The host address Uvicorn should bind to.
    *   **Required:** No.
    *   **Default Value:** `0.0.0.0`
    *   **Example Value:** `127.0.0.1`
    *   **Module(s) Affected:** `backend.main.start_api()`

*   **`PORT` (For Uvicorn Development Server)**
    *   **Purpose:** The port Uvicorn should listen on.
    *   **Required:** No.
    *   **Default Value:** `8000`
    *   **Example Value:** `8080`
    *   **Module(s) Affected:** `backend.main.start_api()`

## 4. Accessing Configuration in Code

The `backend.config.config` object (an instance of `AppConfig`) provides properties to access these configured values:
```python
from backend.config import config

db_host = config.db_host
redis_main_url = config.redis_url # Accesses the _redis_url attribute
batch_size = config.fetch_batch_size
```
The `AppConfig` class in `config.py` defines how these environment variables are loaded and what defaults are used if they are not set.

## 5. User-Specific Preferences

In addition to global environment variables, SmartInfo stores user-specific preferences in the `user_preferences` database table (see `DATABASE_SCHEMA.md`). These are managed via the `/api/settings/settings` endpoints and accessed via `UserPreferenceRepository` and `SettingService`.

These preferences typically control user-specific behavior or defaults within the application features (e.g., default LLM model for a user, display settings) and are distinct from the application-level environment configurations described above.

## 6. Adding New Configuration Parameters

If a new application-level configuration parameter is required:

1.  **Decide Scope:** Determine if it's a global setting (environment variable) or a user-specific preference.
2.  **For Environment Variables:**
    *   Add a new attribute (e.g., `_new_setting_value`) and corresponding property to `backend.config.AppConfig`.
    *   Update the `__init__` method in `AppConfig` to load it from `os.getenv()`, providing a sensible default.
    *   Document the new environment variable in this `CONFIGURATION_GUIDE.md` and in `.env.example`.
    *   Update any relevant modules to use `config.new_setting_value`.
3.  **For User-Specific Preferences:**
    *   If it's a new type of preference, consider if any schema changes are needed (usually not if it's a simple key-value).
    *   Update `SettingService` and relevant API endpoints if new logic is needed to manage or apply this preference.
    *   Ensure the frontend provides a way for users to manage this preference.
