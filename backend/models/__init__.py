"""
Models module for the application.
Imports all model classes and re-exports them for convenient imports elsewhere.
"""

from models.schemas.user import User, UserCreate
from models.schemas.news import (
    NewsItem as News,  # Alias NewsItem as News
    NewsItemCreate as NewsCreate,  # Alias NewsItemCreate as NewsCreate
    NewsItemUpdate as NewsUpdate,  # Alias NewsItemUpdate as NewsUpdate
    NewsCategory,
    NewsCategoryCreate,
    NewsCategoryUpdate,  # Keep NewsCategoryUpdate if it exists elsewhere or might be added
    NewsSource,
    NewsSourceCreate,
    NewsSourceUpdate,
    FetchSourceRequest,
    FetchSourceBatchRequest,
    FetchUrlRequest,
    AnalyzeRequest,
    AnalyzeContentRequest,
    AnalysisResult,
    UpdateAnalysisRequest,
    NewsCategoryResponse,
    NewsSourceResponse,
    NewsResponse,
    FetchHistoryItemResponse,
    NewsItemsPage,  # ADDED NewsItemsPage
)
from models.schemas.api_key import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyResponse,
)
from models.schemas.settings import (
    UserPreference,
    UserPreferenceBase,
    UserPreferenceUpdate,
)
from models.schemas.chat import (
    Chat,
    ChatCreate,
    Message,
    MessageCreate,
    ChatAnswer,
    Question,
    MessageResponse,
    ChatResponse,
    ChatListResponseItem,
)


from models.schemas.user import UserInDB


__all__ = [
    "User",
    "UserCreate",
    "News",
    "NewsCreate",
    "NewsUpdate",
    "NewsCategory",
    "NewsCategoryCreate",
    "NewsCategoryUpdate",
    "NewsSource",
    "NewsSourceCreate",
    "NewsSourceUpdate",
    "FetchSourceRequest",
    "FetchSourceBatchRequest",
    "FetchUrlRequest",
    "AnalyzeRequest",
    "AnalyzeContentRequest",
    "AnalysisResult",
    "UpdateAnalysisRequest",
    "FetchHistoryItemResponse",
    "NewsItemsPage",  # ADDED NewsItemsPage
    "ApiKey",
    "ApiKeyCreate",
    "UserPreference",
    "UserPreferenceBase",
    "UserPreferenceUpdate",
    "Chat",
    "ChatCreate",
    "Message",
    "MessageCreate",
    "ChatAnswer",
    "Question",
    "NewsCategoryResponse",
    "NewsSourceResponse",
    "NewsResponse",
    "ApiKeyResponse",
    "MessageResponse",
    "ChatResponse",
    "ChatListResponseItem",
]
