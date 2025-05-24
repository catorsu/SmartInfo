"""
Pydantic Schemas for News-Related Data.

This module defines Pydantic models for representing news categories, news sources,
individual news items, and various request/response structures related to news
fetching and analysis within the SmartInfo application. These schemas are crucial
for API request validation, response serialization, and internal data consistency.

Key Schemas:
  - NewsCategory, NewsCategoryCreate, NewsCategoryUpdate, NewsCategoryResponse: For news categories.
  - NewsSource, NewsSourceCreate, NewsSourceUpdate, NewsSourceResponse: For news sources.
  - NewsItem, NewsItemCreate, NewsItemUpdate, NewsResponse: For individual news articles.
  - FetchSourceRequest, FetchSourceBatchRequest, FetchUrlRequest: For news fetching requests.
  - TaskResponse: For asynchronous task initiation responses.
  - AnalyzeRequest, AnalyzeContentRequest, AnalysisResult, UpdateAnalysisRequest: For content analysis.
  - FetchHistoryItemResponse: For news fetching history.
"""

from datetime import date, datetime
from pydantic import BaseModel, Field, AnyHttpUrl, ConfigDict, field_validator
from typing import List, Optional, Dict, Any


class NewsCategoryFields(BaseModel):
    """
    Base fields for news category data, primarily the category name.
    Shared by category creation, update, and full category models.
    """

    name: str = Field(
        ...,
        max_length=100,
        description="Name of the news category, e.g., 'Technology', 'Sports'. Must be unique per user.",
        examples=["Technology", "Artificial Intelligence", "World News"],
    )


class NewsCategoryCreate(NewsCategoryFields):
    """
    Schema for creating a new news category. Used as a request body.
    The `user_id` is typically derived from the authenticated user context.
    """

    pass  # Inherits name. user_id is handled by the service.


class NewsCategoryUpdate(NewsCategoryFields):
    """
    Schema for updating an existing news category's name. Used as a request body.
    """

    pass  # Inherits name. user_id and category_id are path/context parameters.


class NewsCategory(NewsCategoryFields):
    """
    Schema representing a full news category object, typically for database
    representation or internal use. Includes database ID and user ownership.
    """

    id: int = Field(
        ..., description="Unique identifier for the news category.", examples=[1, 25]
    )
    user_id: int = Field(
        ..., description="ID of the user who owns this category.", examples=[1, 10]
    )
    source_count: Optional[int] = Field(
        None,
        description="Number of news sources associated with this category for the user. Typically populated on demand.",
        examples=[0, 5, 12],
    )

    model_config = ConfigDict(from_attributes=True)


class NewsCategoryResponse(BaseModel):
    """
    Schema for representing a news category in API responses.
    Excludes `user_id` for security/privacy. Includes `source_count`.
    """

    id: int = Field(
        ..., description="Unique identifier for the news category.", examples=[1]
    )
    name: str = Field(
        ...,
        max_length=100,
        description="Name of the news category.",
        examples=["Technology"],
    )
    source_count: Optional[int] = Field(
        None,
        description="Number of news sources associated with this category for the user.",
        examples=[5],
    )

    model_config = ConfigDict(from_attributes=True)


class NewsSourceFields(BaseModel):
    """
    Base fields for news source data.
    Shared by source creation, update, and full source models.
    """

    name: str = Field(
        ...,
        max_length=100,
        description="User-defined name for the news source, e.g., 'TechCrunch', 'BBC News'. Must be unique per user.",
        examples=["TechCrunch", "The Guardian Tech"],
    )
    url: AnyHttpUrl = Field(
        ...,
        description="URL of the news source, typically the homepage or an RSS feed URL. Must be unique per user.",
        examples=[
            "https://techcrunch.com",
            "https://www.theguardian.com/technology/rss",
        ],
    )
    category_id: int = Field(
        ...,
        description="ID of the news category this source belongs to. The category must exist and be owned by the user.",
        examples=[1, 25],
    )


class NewsSourceCreate(NewsSourceFields):
    """
    Schema for creating a new news source. Used as a request body.
    The `user_id` is derived from the authenticated user context.
    """

    pass  # Inherits fields. user_id is handled by the service.


class NewsSourceUpdate(
    BaseModel
):  # Changed from inheriting NewsSourceFields to allow all fields to be truly optional
    """
    Schema for updating an existing news source. Used as a request body.
    All fields are optional, allowing partial updates.
    """

    name: Optional[str] = Field(
        None,
        max_length=100,
        description="New name for the news source.",
        examples=["TechCrunch (Updated)"],
    )
    url: Optional[AnyHttpUrl] = Field(
        None,
        description="New URL for the news source.",
        examples=["https://techcrunch.com/new-feed"],
    )
    category_id: Optional[int] = Field(
        None, description="New category ID for the source.", examples=[2]
    )


class NewsSource(NewsSourceFields):
    """
    Schema representing a full news source object, typically for database
    representation or internal use. Includes database ID, user ownership,
    and denormalized category name.
    """

    id: int = Field(
        ..., description="Unique identifier for the news source.", examples=[101, 202]
    )
    user_id: int = Field(
        ..., description="ID of the user who owns this source.", examples=[1, 10]
    )
    category_name: Optional[str] = Field(
        None,
        description="Name of the category this source belongs to (denormalized for convenience).",
        examples=["Technology"],
    )

    model_config = ConfigDict(from_attributes=True)


class NewsSourceResponse(BaseModel):
    """
    Schema for representing a news source in API responses.
    Excludes `user_id`. Includes denormalized `category_name`.
    """

    id: int = Field(
        ..., description="Unique identifier for the news source.", examples=[101]
    )
    name: str = Field(
        ...,
        max_length=100,
        description="Name of the news source.",
        examples=["TechCrunch"],
    )
    url: AnyHttpUrl = Field(
        ...,
        description="URL of the news source.",
        examples=["https://techcrunch.com"],
    )
    category_id: int = Field(
        ..., description="ID of the category this source belongs to.", examples=[1]
    )
    category_name: Optional[str] = Field(
        None,
        description="Name of the category this source belongs to.",
        examples=["Technology"],
    )

    model_config = ConfigDict(from_attributes=True)


class NewsItemFields(BaseModel):
    """
    Base fields for news item data.
    Shared by news item creation, update, and full item models.
    """

    title: str = Field(
        ...,
        description="Title of the news item or article.",
        examples=["New AI Model Achieves Breakthrough Performance"],
    )
    url: Optional[AnyHttpUrl] = Field(
        None,
        description="URL of the original news article. Should be unique per user if provided.",
        examples=["https://example.com/news/ai-breakthrough"],
    )
    source_id: Optional[int] = Field(
        None,
        description="ID of the news source this item came from. Must exist and be owned by the user.",
        examples=[101],
    )
    category_id: Optional[int] = Field(
        None,
        description="ID of the news category this item belongs to. Must exist and be owned by the user.",
        examples=[1],
    )
    summary: Optional[str] = Field(
        None,
        description="A brief summary of the news item, possibly LLM-generated.",
        examples=[
            "An AI model has surpassed human benchmarks in complex reasoning tasks..."
        ],
    )
    content: Optional[str] = Field(
        None,
        description="Full content of the news item. This can be large and is often excluded from list views.",
    )
    analysis: Optional[str] = Field(
        None,
        description="LLM-generated in-depth analysis or structured summary of the content.",
    )
    date: Optional[str] = Field(
        None,
        description="Publication date of the news item (stored as text, e.g., 'YYYY-MM-DD' or ISO format).",
        examples=["2023-10-26", "2023-10-26T10:00:00Z"],
    )
    source_name: Optional[str] = Field(
        None,
        description="Name of the news source (denormalized for convenience, especially if `source_id` is not set).",
        examples=["Tech Journal"],
    )
    category_name: Optional[str] = Field(
        None,
        description="Name of the news category (denormalized for convenience, especially if `category_id` is not set).",
        examples=["Artificial Intelligence"],
    )
    top_image: Optional[AnyHttpUrl] = Field(  # Changed to AnyHttpUrl for consistency
        None,
        description="URL of the top image associated with the news item.",
        examples=["https://example.com/images/ai-breakthrough.jpg"],
    )


class NewsItemCreate(NewsItemFields):
    """
    Schema for creating a new news item. Used as a request body.
    `title` and `url` are mandatory for creation.
    The `user_id` is derived from the authenticated user context.
    """

    title: str = Field(
        ..., description="Title of the news item."
    )  # Already in NewsItemFields, but reinforcing mandatory nature
    url: AnyHttpUrl = Field(
        ..., description="URL of the original news article."
    )  # Already in NewsItemFields, but reinforcing mandatory nature and type
    # user_id is handled by the service.


class NewsItemUpdate(NewsItemFields):
    """
    Schema for updating an existing news item. Used as a request body.
    All fields are optional, allowing partial updates.
    """

    title: Optional[str] = Field(None, description="New title for the news item.")
    # All other fields inherited from NewsItemFields are already Optional or made Optional here.


class NewsItem(NewsItemFields):
    """
    Schema representing a full news item object, typically for database
    representation or internal use. Includes database ID, user ownership,
    and creation timestamp.
    """

    id: int = Field(
        ..., description="Unique identifier for the news item.", examples=[1001, 2050]
    )
    user_id: int = Field(
        ..., description="ID of the user who owns this news item.", examples=[1, 10]
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601 format) when this news item record was created in the system.",
        examples=["2023-10-26T10:05:00Z"],
    )
    task_group_id: Optional[str] = Field(
        None,
        description="ID of the Celery task group that fetched/processed this item (if applicable).",
        examples=["abc-123-def-456"],
    )

    model_config = ConfigDict(from_attributes=True)


DEFAULT_NEWS_IMAGE_URL = "https://via.placeholder.com/350x200.png?text=SmartInfo+News"


class NewsResponse(BaseModel):
    """
    Schema for representing a news item in API responses.
    Excludes `user_id` and full `content` for brevity and security.
    Includes a validated `top_image` URL.
    """

    id: int = Field(
        ..., description="Unique identifier for the news item.", examples=[1001]
    )
    title: str = Field(
        ...,
        description="Title of the news item.",
        examples=["AI Model Surpasses Human Benchmarks"],
    )
    url: Optional[AnyHttpUrl] = Field(
        None,
        description="URL of the original news article.",
        examples=["https://example.com/news/ai-benchmark"],
    )
    source_id: Optional[int] = Field(
        None, description="ID of the news source.", examples=[101]
    )
    category_id: Optional[int] = Field(
        None, description="ID of the news category.", examples=[1]
    )
    summary: Optional[str] = Field(
        None,
        description="A brief summary of the news item.",
        examples=["A new AI model has shown superior performance..."],
    )
    analysis: Optional[str] = Field(
        None, description="LLM-generated analysis of the content."
    )
    date: Optional[str] = Field(
        None,
        description="Publication date (e.g., 'YYYY-MM-DD' or ISO format).",
        examples=["2023-10-26"],
    )
    source_name: Optional[str] = Field(
        None, description="Name of the news source.", examples=["AI Insights Weekly"]
    )
    category_name: Optional[str] = Field(
        None, description="Name of the news category.", examples=["AI Research"]
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601) when the item was saved in SmartInfo.",
        examples=["2023-10-26T10:05:00Z"],
    )
    top_image: AnyHttpUrl = Field(
        ...,  # Made non-optional due to validator providing default
        description="URL of the top image for the news item. Defaults to a placeholder if not available or invalid.",
        examples=["https://example.com/images/news-image.jpg"],
    )

    @field_validator("top_image", mode="before")
    @classmethod
    def validate_top_image_url(cls, v: Any) -> str:
        """
        Validates the top_image field. If it's None, an empty string, or not a
        valid-looking HTTP/S URL string, it defaults to DEFAULT_NEWS_IMAGE_URL.
        The returned string will then be parsed by Pydantic into AnyHttpUrl.
        """
        if isinstance(v, str) and v.strip():
            if v.startswith("http://") or v.startswith("https://"):
                return v
        return DEFAULT_NEWS_IMAGE_URL

    model_config = ConfigDict(from_attributes=True)


# NEW MODEL FOR PAGINATED NEWS ITEMS RESPONSE
class NewsItemsPage(BaseModel):
    """
    Schema for a paginated list of news items.
    Includes the list of items for the current page and the total count of
    items matching the query across all pages.
    """

    items: List[NewsResponse] = Field(
        ..., description="A list of news items for the current page."
    )
    total: int = Field(
        ...,
        description="The total number of news items matching the filter criteria across all pages.",
        examples=[100, 253],
    )
    page: Optional[int] = Field(
        None, description="The current page number (1-indexed).", examples=[1, 5]
    )
    page_size: Optional[int] = Field(
        None, description="The number of items per page.", examples=[10, 20]
    )
    # total_pages: Optional[int] = Field(None, description="Total number of pages available.") # Can be calculated if needed

    model_config = ConfigDict(from_attributes=True)


class FetchSourceRequest(BaseModel):
    """Schema for requesting news fetching from a specific source ID."""

    source_id: int = Field(
        ...,
        description="ID of the news source to fetch news from.",
        examples=[101],
    )


class FetchSourceBatchRequest(BaseModel):
    """Schema for requesting batch fetching of news from multiple source IDs."""

    source_ids: List[int] = Field(
        ...,
        description="List of news source IDs to fetch news from.",
        examples=[[101, 102, 103]],
    )


class FetchUrlRequest(BaseModel):
    """Schema for requesting crawling and processing of a single URL."""

    url: AnyHttpUrl = Field(
        ...,
        description="The URL to crawl and process for news content.",
        examples=["https://example.com/specific-article-to-fetch"],
    )


class TaskResponse(BaseModel):
    """Schema for responses to asynchronous task initiation requests."""

    task_group_id: str = Field(
        ...,
        description="Unique identifier for the initiated task group. Used for progress tracking.",
        examples=["a1b2c3d4-e5f6-7890-1234-567890abcdef"],
    )
    message: str = Field(
        ...,
        description="Informational message about the task initiation status.",
        examples=["Batch fetch group scheduled for 5 sources."],
    )


class AnalyzeRequest(BaseModel):
    """Schema for requesting LLM analysis of one or more news items."""

    news_ids: Optional[List[int]] = Field(
        None,
        description="List of news item IDs to analyze. If empty or None, the backend might analyze all unanalyzed items for the user.",
        examples=[[1001, 1002]],
    )
    force: bool = Field(
        False,
        description="If True, force re-analysis even if an analysis already exists for the news item(s).",
        examples=[True, False],
    )


class AnalyzeContentRequest(BaseModel):
    """Schema for requesting LLM analysis of arbitrary text content."""

    content: str = Field(..., description="The text content to be analyzed by the LLM.")
    instructions: str = Field(
        ...,
        description="Specific instructions or system prompt for the LLM on how to perform the analysis.",
        examples=[
            "Summarize this text in three bullet points.",
            "Identify the key arguments in this article.",
        ],
    )


class AnalysisResult(BaseModel):
    """Schema for the result of an LLM content analysis."""

    analysis: str = Field(
        ...,
        description="The analysis result generated by the LLM (can be Markdown, plain text, or other format as per instructions).",
    )


class UpdateAnalysisRequest(BaseModel):
    """Schema for manually updating the analysis field of a news item."""

    analysis: str = Field(
        ...,
        description="The new analysis text to store for the news item.",
        examples=["This article discusses the impact of AI on employment..."],
    )


class FetchHistoryItemResponse(BaseModel):
    """Schema for representing a fetch history item in API responses."""

    source_id: int = Field(..., description="ID of the news source.", examples=[101])
    source_name: str = Field(
        ..., description="Name of the news source.", examples=["Tech News Daily"]
    )
    record_date: date = Field(
        ...,
        description="The date (YYYY-MM-DD) for which items were saved.",
        examples=["2023-10-26"],
    )
    items_saved_today: int = Field(
        ...,
        description="Number of items saved from this source for the user on this day.",
        examples=[5, 0, 12],
    )
    last_updated_at: Optional[datetime] = Field(
        None,
        description="Timestamp (ISO 8601) when this history record was last updated.",
        examples=["2023-10-26T14:30:00Z"],
    )

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
