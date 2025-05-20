"""
Database Schema Constants for SmartInfo.

This module centralizes the string constants used to refer to database table
names and column names throughout the application. Using these constants helps
prevent typos and ensures consistency when interacting with the database,
particularly in repository classes and SQL query construction.

@module_purpose: To provide a single source of truth for database schema names,
                 enhancing maintainability and reducing errors related to schema
                 references.
@primary_consumers: All repository classes in `backend.db.repositories`,
                    database migration scripts (if any), and any service
                    or utility that directly constructs SQL queries or
                    references table/column names.
@primary_dependencies: None directly, but conceptually linked to the database
                       schema defined in `docs/backend/DATABASE_SCHEMA.md`.

Key Constants & Classes:
  - Table name constants (e.g., `USERS_TABLE`, `NEWS_TABLE`).
  - Classes representing tables (e.g., `Users`, `News`), each containing
    constants for their respective column names.
"""

USERS_TABLE = "users"
NEWS_CATEGORY_TABLE = "news_category"
NEWS_SOURCES_TABLE = "news_sources"
NEWS_TABLE = "news"
API_CONFIG_TABLE = "api_config"
USER_PREFERENCES_TABLE = "user_preferences"
CHATS_TABLE = "chats"
MESSAGES_TABLE = "messages"
FETCH_HISTORY_TABLE = "fetch_history"


# Represents the 'users' table in the database.
class Users:
    TABLE_NAME = USERS_TABLE
    ID = "id"  # Primary key
    USERNAME = "username"  # Unique username
    HASHED_PASSWORD = "hashed_password"  # Bcrypt hashed password


# Represents the 'news_category' table in the database.
class NewsCategory:
    TABLE_NAME = NEWS_CATEGORY_TABLE
    ID = "id"  # Primary key
    NAME = "name"  # Name of the category (e.g., "Technology", "Sports")
    USER_ID = "user_id"  # Foreign key to the users table


# Represents the 'news_sources' table in the database.
class NewsSource:
    TABLE_NAME = NEWS_SOURCES_TABLE
    ID = "id"  # Primary key
    NAME = "name"  # Name of the news source (e.g., "TechCrunch", "ESPN")
    URL = "url"  # Base URL of the news source (e.g., "https://techcrunch.com")
    CATEGORY_ID = "category_id"  # Foreign key to the news_category table
    USER_ID = "user_id"  # Foreign key to users table, indicating who added this source


# Represents the 'news' table in the database.
class News:
    TABLE_NAME = NEWS_TABLE
    ID = "id"  # Primary key
    TITLE = "title"  # Title of the news article
    URL = "url"  # URL of the specific news article
    SOURCE_NAME = "source_name"  # Denormalized name of the news source
    CATEGORY_NAME = "category_name"  # Denormalized name of the news category
    SOURCE_ID = "source_id"  # Foreign key to the news_sources table
    CATEGORY_ID = "category_id"  # Foreign key to the news_category table
    SUMMARY = "summary"  # LLM-generated summary of the article
    ANALYSIS = "analysis"  # LLM-generated analysis of the article
    DATE = "date"  # Publication date of the article
    CONTENT = "content"  # Fetched raw content of the article
    USER_ID = "user_id"  # Foreign key to the users table
    TOP_IMAGE = "top_image"  # URL of the article's main image
    TASK_GROUP_ID = "task_group_id"  # Celery task group ID for fetching/analysis
    CREATED_AT = "created_at"  # Timestamp of when this news record was created


# Represents the 'api_config' table in the database.
class ApiConfig:
    TABLE_NAME = API_CONFIG_TABLE
    ID = "id"  # Primary key
    MODEL = "model"  # LLM model identifier (e.g., 'gpt-4', 'claude-2')
    BASE_URL = "base_url"  # Base URL for the LLM API endpoint
    API_KEY = "api_key"  # API key for the LLM service (store securely)
    CONTEXT = "context"  # Default system prompt or context for this configuration
    MAX_OUTPUT_TOKENS = "max_output_tokens"  # Maximum tokens for LLM output generation
    DESCRIPTION = "description"  # User-friendly description of this API configuration
    CREATED_DATE = "created_date"  # Timestamp of creation
    MODIFIED_DATE = "modified_date"  # Timestamp of last modification
    USER_ID = "user_id"  # Foreign key to the users table


# Represents the 'user_preferences' table in the database.
class UserPreferences:
    TABLE_NAME = USER_PREFERENCES_TABLE
    KEY = "config_key"  # Preference key (e.g., 'ui_theme', 'llm_temperature')
    VALUE = "config_value"  # Preference value (e.g., 'dark', '0.7')
    DESCRIPTION = "description"  # Description of the preference key's purpose
    USER_ID = "user_id"  # Foreign key to the users table


# Represents the 'chats' table in the database.
class Chats:
    TABLE_NAME = CHATS_TABLE
    ID = "id"  # Primary key
    TITLE = "title"  # Title of the chat session
    CREATED_AT = "created_at"  # Timestamp of chat creation
    UPDATED_AT = "updated_at"  # Timestamp of last update to the chat
    USER_ID = "user_id"  # Foreign key to the users table


# Represents the 'messages' table in the database.
class Messages:
    TABLE_NAME = MESSAGES_TABLE
    ID = "id"  # Primary key
    CHAT_ID = "chat_id"  # Foreign key to the chats table
    SENDER = "sender"  # Sender of the message (e.g., 'user', 'assistant')
    CONTENT = "content"  # Content of the message
    TIMESTAMP = "timestamp"  # Timestamp of when the message was sent/received
    SEQUENCE_NUMBER = "sequence_number"  # Order of the message within the chat
    DEFAULT_SEQUENCE_NUMBER = 0  # Default value for sequence_number


# Represents the 'fetch_history' table in the database.
class FetchHistory:
    TABLE_NAME = FETCH_HISTORY_TABLE
    ID = "id"  # Primary key
    USER_ID = "user_id"  # Foreign key to the users table
    SOURCE_ID = "source_id"  # Foreign key to the news_sources table
    RECORD_DATE = (
        "record_date"  # Date for which this history record applies (YYYY-MM-DD)
    )
    ITEMS_SAVED_TODAY = (
        "items_saved_today"  # Count of news items saved from this source on record_date
    )
    LAST_UPDATED_AT = "last_updated_at"  # Timestamp of the last update to this record
    LAST_BATCH_TASK_GROUP_ID = (
        "last_batch_task_group_id"  # Celery task group ID for the last fetch batch
    )
