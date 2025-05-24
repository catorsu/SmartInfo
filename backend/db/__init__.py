"""
Database Repositories Package for SmartInfo.

This package contains repository classes that encapsulate data access logic
for various database entities within the SmartInfo application. Each repository
provides an abstraction layer over raw database queries, offering specific
methods for CRUD (Create, Read, Update, Delete) operations and other
data-related functionalities for a particular table or a set of related tables.

@module_purpose: To provide a structured and maintainable way to interact with
                 the database, separating data access concerns from business
                 logic in services.
@primary_consumers: Service layer (`backend.services.*`) which uses these
                    repositories to perform data operations.
@primary_dependencies: `backend.db.connection` (for acquiring database
                       connections), `backend.db.schema_constants` (for table
                       and column names), `asyncpg` (for database interaction).

Key Components/Exports:
  - BaseRepository: A base class providing common database operation helpers.
  - Concrete Repositories (e.g., UserRepository, NewsRepository): Implement
    specific data access logic for entities like users, news articles, etc.
"""

from db.repositories.news_repository import NewsRepository
from db.repositories.news_source_repository import NewsSourceRepository
from db.repositories.news_category_repository import NewsCategoryRepository
from db.repositories.api_key_repository import ApiKeyRepository
from db.repositories.user_preference_repository import UserPreferenceRepository
from db.repositories.chat_repository import ChatRepository
from db.repositories.message_repository import MessageRepository
from db.repositories.user_repository import UserRepository
from db.repositories.fetch_history_repository import FetchHistoryRepository
from db.repositories.base_repository import BaseRepository

__all__ = [
    "BaseRepository",
    "NewsRepository",
    "NewsSourceRepository",
    "NewsCategoryRepository",
    "ApiKeyRepository",
    "UserPreferenceRepository",
    "ChatRepository",
    "MessageRepository",
    "UserRepository",
    "FetchHistoryRepository",
]
