# SmartInfo Backend Database Schema

## 1. Introduction

This document details the database schema used by the SmartInfo backend application. It describes the tables, columns, relationships, and key indexing strategies. Understanding this schema is essential for developing and maintaining the application, especially for interacting with the data repository layer.

The canonical names for tables and columns are defined in `backend/db/schema_constants.py`.

## 2. Database System

*   **System:** PostgreSQL
*   **Access Library:** `asyncpg` (asynchronous Python driver)

## 3. Schema Overview (ER Diagram)

```mermaid
erDiagram
    USERS {
        INT id PK "User ID (Serial)"
        TEXT username UK "Unique username"
        TEXT hashed_password "Hashed password"
    }

    NEWS_CATEGORY {
        INT id PK "Category ID (Serial)"
        TEXT name "Category name"
        INT user_id FK "User who owns this category"
        UK (name, user_id) "Category name unique per user"
    }

    NEWS_SOURCES {
        INT id PK "Source ID (Serial)"
        TEXT name "Source name"
        TEXT url "Source URL"
        INT category_id FK "Category this source belongs to"
        INT user_id FK "User who owns this source"
        UK (url, user_id) "Source URL unique per user"
        UK (name, user_id) "Source name unique per user"
    }

    NEWS {
        BIGINT id PK "News item ID (BigSerial)"
        TEXT title "News title"
        TEXT url UK "News URL (unique per user)"
        TEXT source_name "Name of the source"
        TEXT category_name "Name of the category"
        INT source_id FK "FK to news_sources (nullable)"
        INT category_id FK "FK to news_category (nullable)"
        TEXT summary "News summary"
        TEXT analysis "LLM-generated analysis"
        TEXT date "Publication date string"
        TEXT content "Full news content"
        TEXT top_image "URL of top image"
        INT user_id FK "User who owns this news item"
        TIMESTAMPTZ created_at "Timestamp of creation (default: current_timestamp)"
        TEXT task_group_id "ID of the task group that fetched this (nullable)"
    }

    API_CONFIG {
        INT id PK "API Config ID (Serial)"
        TEXT model "LLM model name"
        TEXT base_url "API base URL"
        TEXT api_key "Encrypted API key"
        INT context "Model context length"
        INT max_output_tokens "Max output tokens"
        TEXT description "Optional description"
        INT user_id FK "User who owns this API config"
        TIMESTAMPTZ created_date "Creation timestamp"
        TIMESTAMPTZ modified_date "Last modification timestamp"
    }

    USER_PREFERENCES {
        TEXT config_key PK "Preference key"
        TEXT config_value "Preference value (stored as text)"
        TEXT description "Optional description"
        INT user_id PK FK "User these preferences belong to"
    }

    CHATS {
        BIGINT id PK "Chat ID (BigSerial)"
        TEXT title "Chat title"
        INT user_id FK "User who owns this chat"
        TIMESTAMPTZ created_at "Creation timestamp"
        TIMESTAMPTZ updated_at "Last update timestamp"
    }

    MESSAGES {
        BIGINT id PK "Message ID (BigSerial)"
        BIGINT chat_id FK "Chat this message belongs to"
        TEXT sender "'user' or 'assistant'"
        TEXT content "Message content"
        TIMESTAMPTZ timestamp "Message timestamp"
        INT sequence_number "Order of message in chat"
    }

    FETCH_HISTORY {
        BIGINT id PK "History ID (BigSerial)"
        INT user_id FK "User this history belongs to"
        INT source_id FK "News source this record is for"
        DATE record_date "Date of the fetch records (YYYY-MM-DD)"
        INT items_saved_today "Number of items saved from this source on this day"
        TIMESTAMPTZ last_updated_at "When this record was last updated"
        TEXT last_batch_task_group_id "Task group ID of the last batch affecting this entry"
        UK (user_id, source_id, record_date) "Unique entry per user, source, day"
    }

    USERS ||--o{ NEWS_CATEGORY : "owns"
    USERS ||--o{ NEWS_SOURCES : "owns"
    USERS ||--o{ NEWS : "owns"
    USERS ||--o{ API_CONFIG : "owns"
    USERS ||--o{ USER_PREFERENCES : "owns"
    USERS ||--o{ CHATS : "owns"
    USERS ||--o{ FETCH_HISTORY : "owns"

    NEWS_CATEGORY ||--o{ NEWS_SOURCES : "categorizes"
    NEWS_CATEGORY ||--o{ NEWS : "categorizes (denormalized)"

    NEWS_SOURCES ||--o{ NEWS : "sourced from (denormalized)"
    NEWS_SOURCES ||--o{ FETCH_HISTORY : "history for"

    CHATS ||--o{ MESSAGES : "contains"
```

## 4. Table Definitions

### 4.1. `users` Table
*   **Purpose:** Stores user account information for authentication and data ownership.
*   **Constant:** `schema_constants.Users`

| Column Name       | Data Type   | Constraints                               | Description                                      | Example Value                |
|:------------------|:------------|:------------------------------------------|:-------------------------------------------------|:-----------------------------|
| `id`              | `SERIAL`    | `PRIMARY KEY`                             | Unique identifier for the user.                  | `1`                          |
| `username`        | `TEXT`      | `NOT NULL`, `UNIQUE`                      | User's chosen username.                          | `"john_doe"`                 |
| `hashed_password` | `TEXT`      | `NOT NULL`                                | Bcrypt hashed password for the user.             | `"$2b$..."` (hashed string) |
*   **Indexes:**
    *   `idx_users_username` ON `username` (for fast username lookups).

### 4.2. `news_category` Table
*   **Purpose:** Allows users to define their own categories for organizing news sources and items.
*   **Constant:** `schema_constants.NewsCategory`

| Column Name | Data Type | Constraints                                                        | Description                                       | Example Value    |
|:------------|:----------|:-------------------------------------------------------------------|:--------------------------------------------------|:-----------------|
| `id`        | `SERIAL`  | `PRIMARY KEY`                                                      | Unique identifier for the category.               | `101`            |
| `name`      | `TEXT`    | `NOT NULL`, `UNIQUE` with `user_id`                                | Name of the category (e.g., "Technology", "AI").  | `"Technology"`   |
| `user_id`   | `INTEGER` | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`)      | ID of the user who owns this category.            | `1`              |
*   **Relationships:**
    *   Many-to-one with `users` (a user can have many categories).
*   **Design Notes:** The `UNIQUE (name, user_id)` constraint ensures category names are unique per user.

### 4.3. `news_sources` Table
*   **Purpose:** Stores news sources (websites, feeds) added by users.
*   **Constant:** `schema_constants.NewsSource`

| Column Name   | Data Type | Constraints                                                                         | Description                                       | Example Value                        |
|:--------------|:----------|:------------------------------------------------------------------------------------|:--------------------------------------------------|:-------------------------------------|
| `id`          | `SERIAL`  | `PRIMARY KEY`                                                                       | Unique identifier for the news source.            | `201`                                |
| `name`        | `TEXT`    | `NOT NULL`, `UNIQUE` with `user_id`                                                 | User-defined name for the source.                 | `"TechCrunch"`                       |
| `url`         | `TEXT`    | `NOT NULL`, `UNIQUE` with `user_id`                                                 | URL of the news source (e.g., homepage or RSS).   | `"https://techcrunch.com"`           |
| `category_id` | `INTEGER` | `NOT NULL`, `FOREIGN KEY` to `news_category.id` (`ON DELETE CASCADE`)               | ID of the category this source belongs to.        | `101`                                |
| `user_id`     | `INTEGER` | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`)                       | ID of the user who owns this source.              | `1`                                  |
*   **Indexes:**
    *   `idx_news_sources_url` ON `url` (for efficient lookup by URL, though uniqueness is per user).
*   **Relationships:**
    *   Many-to-one with `users`.
    *   Many-to-one with `news_category`.
*   **Design Notes:** `url` and `name` are unique per user.

### 4.4. `news` Table
*   **Purpose:** Stores individual news articles fetched and processed for users.
*   **Constant:** `schema_constants.News`

| Column Name     | Data Type     | Constraints                                                              | Description                                                    | Example Value                               |
|:----------------|:--------------|:-------------------------------------------------------------------------|:---------------------------------------------------------------|:--------------------------------------------|
| `id`            | `BIGSERIAL`   | `PRIMARY KEY`                                                            | Unique identifier for the news item.                           | `1001`                                      |
| `title`         | `TEXT`        | `NOT NULL`                                                               | Title of the news article.                                     | `"New AI Model Released"`                   |
| `url`           | `TEXT`        | `NOT NULL`, `UNIQUE` with `user_id`                                      | URL of the original article.                                   | `"http://example.com/article1"`             |
| `source_name`   | `TEXT`        |                                                                          | Name of the source (denormalized for convenience).             | `"TechCrunch"`                              |
| `category_name` | `TEXT`        |                                                                          | Name of the category (denormalized for convenience).           | `"Technology"`                              |
| `source_id`     | `INTEGER`     | `FOREIGN KEY` to `news_sources.id` (`ON DELETE SET NULL`)                | ID of the source this item came from (if known).               | `201`                                       |
| `category_id`   | `INTEGER`     | `FOREIGN KEY` to `news_category.id` (`ON DELETE SET NULL`)               | ID of the category this item belongs to (if known).            | `101`                                       |
| `summary`       | `TEXT`        |                                                                          | LLM-generated or extracted summary.                            | `"A new AI model focusing on..."`           |
| `analysis`      | `TEXT`        |                                                                          | LLM-generated in-depth analysis.                               | `"The model's architecture suggests..."`     |
| `date`          | `TEXT`        |                                                                          | Publication date of the article (stored as text).              | `"2024-03-15"`                              |
| `content`       | `TEXT`        |                                                                          | Full extracted content of the article.                         | `"The full article text..."`                |
| `top_image`     | `TEXT`        |                                                                          | URL of the article's main image.                               | `"http://example.com/image.jpg"`            |
| `user_id`       | `INTEGER`     | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`)            | ID of the user who owns this news item.                        | `1`                                         |
| `created_at`    | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                              | Timestamp when this news item record was created in our system.| `2024-05-15T10:00:00Z`                      |
| `task_group_id` | `TEXT`        |                                                                          | ID of the Celery task group that fetched this item (nullable). | `uuid-string`                               |
*   **Indexes:**
    *   `idx_news_url` ON `url` (for efficient lookup by URL).
    *   `idx_news_date` ON `date DESC`.
    *   `idx_news_category_id` ON `category_id`.
    *   `idx_news_source_id` ON `source_id`.
    *   `idx_news_user_id` ON `user_id`.
    *   `idx_news_user_id_created_at` ON `user_id, created_at DESC`.
    *   `idx_news_search_fts` USING `GIN (to_tsvector('zhparsercfg', COALESCE(title, '') || ' ' || ...))` for Full-Text Search (Chinese-optimized).
*   **Relationships:**
    *   Many-to-one with `users`.
    *   Many-to-one with `news_sources` (optional, `ON DELETE SET NULL`).
    *   Many-to-one with `news_category` (optional, `ON DELETE SET NULL`).
*   **Design Notes:**
    *   `source_name` and `category_name` are denormalized for easier display and filtering without extra joins.
    *   `date` is stored as `TEXT` to accommodate various date formats from sources; parsing/validation happens at the application layer.
    *   `ON DELETE SET NULL` for `source_id` and `category_id` means if a source or category is deleted, the news item remains but loses its association.
    *   The `UNIQUE (url, user_id)` constraint prevents duplicate articles per user.

### 4.5. `api_config` Table
*   **Purpose:** Stores user-specific API key configurations for interacting with LLMs.
*   **Constant:** `schema_constants.ApiConfig`

| Column Name         | Data Type     | Constraints                                                   | Description                                         | Example Value                          |
|:--------------------|:--------------|:--------------------------------------------------------------|:----------------------------------------------------|:---------------------------------------|
| `id`                | `SERIAL`      | `PRIMARY KEY`                                                 | Unique ID for the API configuration.                | `301`                                  |
| `model`             | `TEXT`        | `NOT NULL`                                                    | Name of the LLM model (e.g., "deepseek-chat").      | `"deepseek-chat"`                      |
| `base_url`          | `TEXT`        | `NOT NULL`                                                    | Base URL of the LLM API endpoint.                   | `"https://api.deepseek.com"`           |
| `api_key`           | `TEXT`        | `NOT NULL`                                                    | The API key (should be stored encrypted at rest if possible, though current schema stores as TEXT). | `"sk-..."`                             |
| `context`           | `INTEGER`     |                                                               | Context window size for the model.                  | `16000`                                |
| `max_output_tokens` | `INTEGER`     |                                                               | Maximum tokens the model can output.                | `4000`                                 |
| `description`       | `TEXT`        |                                                               | Optional user description for this configuration.   | `"My primary DeepSeek key"`            |
| `user_id`           | `INTEGER`     | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`) | ID of the user who owns this API key.               | `1`                                    |
| `created_date`      | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                   | Timestamp of creation.                              | `2024-05-15T10:00:00Z`                 |
| `modified_date`     | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                   | Timestamp of last modification.                     | `2024-05-16T11:00:00Z`                 |
*   **Relationships:** Many-to-one with `users`.

### 4.6. `user_preferences` Table
*   **Purpose:** Stores general user-specific application preferences as key-value pairs.
*   **Constant:** `schema_constants.UserPreferences`

| Column Name   | Data Type | Constraints                                                                | Description                                             | Example Value                      |
|:--------------|:----------|:---------------------------------------------------------------------------|:--------------------------------------------------------|:-----------------------------------|
| `config_key`  | `TEXT`    | `NOT NULL`, `PRIMARY KEY` with `user_id`                                   | Unique key for the preference (e.g., "llm_default_model"). | `"llm_default_model"`              |
| `config_value`| `TEXT`    |                                                                            | Value of the preference (stored as text).               | `"deepseek-chat"`                  |
| `description` | `TEXT`    |                                                                            | Optional description of the preference.                 | `"Default LLM for new analyses"`   |
| `user_id`     | `INTEGER` | `NOT NULL`, `PRIMARY KEY` with `config_key`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`) | ID of the user these preferences belong to.             | `1`                                |
*   **Relationships:** Many-to-one with `users`. Composite primary key `(config_key, user_id)`.

### 4.7. `chats` Table
*   **Purpose:** Stores metadata for chat sessions initiated by users.
*   **Constant:** `schema_constants.Chats`

| Column Name  | Data Type     | Constraints                                                   | Description                                 | Example Value                          |
|:-------------|:--------------|:--------------------------------------------------------------|:--------------------------------------------|:---------------------------------------|
| `id`         | `BIGSERIAL`   | `PRIMARY KEY`                                                 | Unique identifier for the chat session.     | `401`                                  |
| `title`      | `TEXT`        | `NOT NULL`                                                    | Title of the chat session (e.g., first user message). | `"Summary of today's AI news"`         |
| `user_id`    | `INTEGER`     | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`) | ID of the user who owns this chat.          | `1`                                    |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                   | Timestamp of chat creation.                 | `2024-05-15T10:00:00Z`                 |
| `updated_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                   | Timestamp of last message/update to chat.   | `2024-05-15T10:05:00Z`                 |
*   **Relationships:** Many-to-one with `users`. One-to-many with `messages`.

### 4.8. `messages` Table
*   **Purpose:** Stores individual messages within each chat session.
*   **Constant:** `schema_constants.Messages`

| Column Name      | Data Type     | Constraints                                                      | Description                                 | Example Value                          |
|:-----------------|:--------------|:-----------------------------------------------------------------|:--------------------------------------------|:---------------------------------------|
| `id`             | `BIGSERIAL`   | `PRIMARY KEY`                                                    | Unique identifier for the message.          | `5001`                                 |
| `chat_id`        | `BIGINT`      | `NOT NULL`, `FOREIGN KEY` to `chats.id` (`ON DELETE CASCADE`)    | ID of the chat session this message belongs to. | `401`                                  |
| `sender`         | `TEXT`        | `NOT NULL`                                                       | Sender of the message ("user" or "assistant").| `"user"`                               |
| `content`        | `TEXT`        |                                                                  | Content of the message.                     | `"What are the latest AI developments?"` |
| `timestamp`      | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                      | Timestamp when the message was created.     | `2024-05-15T10:01:00Z`                 |
| `sequence_number`| `INTEGER`     |                                                                  | Order of the message within the chat.       | `0`                                    |
*   **Indexes:**
    *   `idx_messages_chat_id_sequence` ON `(chat_id, sequence_number)` (for efficient retrieval of ordered messages per chat).
*   **Relationships:** Many-to-one with `chats`.

### 4.9. `fetch_history` Table
*   **Purpose:** Tracks the number of news items successfully fetched and saved per source, per user, per day.
*   **Constant:** `schema_constants.FetchHistory`

| Column Name                  | Data Type     | Constraints                                                                         | Description                                                     | Example Value                          |
|:-----------------------------|:--------------|:------------------------------------------------------------------------------------|:----------------------------------------------------------------|:---------------------------------------|
| `id`                         | `BIGSERIAL`   | `PRIMARY KEY`                                                                       | Unique identifier for the history record.                       | `601`                                  |
| `user_id`                    | `INTEGER`     | `NOT NULL`, `FOREIGN KEY` to `users.id` (`ON DELETE CASCADE`)                       | ID of the user this fetch history belongs to.                   | `1`                                    |
| `source_id`                  | `INTEGER`     | `NOT NULL`, `FOREIGN KEY` to `news_sources.id` (`ON DELETE CASCADE`)                | ID of the news source this record pertains to.                  | `201`                                  |
| `record_date`                | `DATE`        | `NOT NULL`                                                                          | The date (YYYY-MM-DD) for which items were saved.               | `2024-05-17`                           |
| `items_saved_today`          | `INTEGER`     | `DEFAULT 0`                                                                         | Number of items saved from this source for this user on this day. | `5`                                    |
| `last_updated_at`            | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP`                                                         | Timestamp when this record was last updated.                    | `2024-05-17T14:30:00Z`                 |
| `last_batch_task_group_id`   | `TEXT`        |                                                                                     | Task group ID of the last batch run that affected this entry.   | `uuid-string`                          |
*   **Constraints:**
    *   `UNIQUE (user_id, source_id, record_date)` ensures one summary record per user, source, and day.
*   **Indexes:**
    *   `idx_fetch_history_user_id` ON `user_id`.
    *   `idx_fetch_history_source_id` ON `source_id`.
    *   `idx_fetch_history_date` ON `record_date`.
*   **Relationships:**
    *   Many-to-one with `users`.
    *   Many-to-one with `news_sources`.
*   **Design Notes:** This table is updated using an `UPSERT` (INSERT ... ON CONFLICT ... DO UPDATE) operation to atomically increment `items_saved_today` when new items are fetched for an existing user-source-date combination.

## 5. Data Integrity and Relationships

*   **User Ownership:** Most primary data tables (`news_category`, `news_sources`, `news`, `api_config`, `user_preferences`, `chats`, `fetch_history`) have a direct `user_id` foreign key referencing `users.id`. This is the cornerstone of data isolation.
*   **Cascading Deletes:**
    *   Deleting a `user` will cascade delete all their associated data in other tables.
    *   Deleting a `news_category` will cascade delete associated `news_sources` (if `ON DELETE CASCADE` is set on `news_sources.category_id` FK, which it is).
    *   Deleting a `news_source` will cascade delete associated `fetch_history` records. For `news` items, `source_id` will be set to `NULL`.
    *   Deleting a `chat` will cascade delete all its `messages`.
*   **`ON DELETE SET NULL`:** For `news.source_id` and `news.category_id`, if the referenced source or category is deleted, these fields in the `news` table will be set to `NULL`. This preserves the news item itself even if its original source/category is removed by the user.
*   **Full-Text Search (FTS):** The `news` table includes a GIN index (`idx_news_search_fts`) on a combined text vector (`title`, `summary`, `source_name`, `category_name`) using the `zhparsercfg` text search configuration for optimized Chinese and general text searching. Ensure `zhparser` extension and its configuration are set up in PostgreSQL.

## 6. Schema Evolution

*   Database migrations are currently handled implicitly by the `_create_tables` logic in `db/connection.py` which uses `CREATE TABLE IF NOT EXISTS`.
*   For more complex schema changes in the future (e.g., altering columns, dropping tables, complex data migrations), a dedicated migration tool like [Alembic](https://alembic.sqlalchemy.org/) should be considered.

This document provides a snapshot of the current database schema. As the SmartInfo project evolves, this document should be updated to reflect any changes.