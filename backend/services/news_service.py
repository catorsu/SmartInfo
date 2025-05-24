"""
NewsService Module.

This service layer component is responsible for managing all aspects of news
content specifically tailored to individual users. It orchestrates operations
including:
- Retrieval and processing of news articles from various sources.
- User-specific CRUD (Create, Read, Update, Delete) operations for news items,
  news sources, and news categories.
- Interaction with Large Language Models (LLMs) for advanced functionalities such
  as extracting relevant article links from URLs and performing in-depth
  summarization or analysis of news content.
- Storing and managing fetched news data, analyses, and user-defined
  classifications (sources, categories) in the database.
"""

from datetime import date
import logging
from typing import List, Dict, Optional, Any, AsyncGenerator


from db.repositories import (
    NewsRepository,
    NewsSourceRepository,
    NewsCategoryRepository,
    ApiKeyRepository,
)


from core.llm.client import AsyncLLMClient

from utils.prompt import SYSTEM_PROMPT_ANALYZE_CONTENT  # System prompt for LLM analysis
from models import (
    NewsSourceCreate,
    NewsCategoryCreate,
    User,  # Used for type hinting, though not directly instantiated here often
    ApiKey,
)


logger = logging.getLogger(__name__)


class NewsService:
    """
    Service class for managing user-specific news data and LLM-driven analysis.

    Handles fetching, cleaning, storing, and analyzing news content.
    Provides CRUD operations for news items, sources, and categories, all
    scoped to the authenticated user.
    """

    def __init__(
        self,
        news_repo: NewsRepository,
        source_repo: NewsSourceRepository,
        category_repo: NewsCategoryRepository,
        api_key_repo: ApiKeyRepository,
    ):
        """Initializes the NewsService with necessary data repositories.

        Args:
            news_repo: Repository for news item data operations.
            source_repo: Repository for news source data operations.
            category_repo: Repository for news category data operations.
            api_key_repo: Repository for user API key data operations.

        Side Effects:
            Initializes internal repository attributes.
        """
        self._news_repo = news_repo
        self._source_repo = source_repo
        self._category_repo = category_repo
        self._api_key_repo = api_key_repo

    # -------------------------------------------------------------------------
    # Public CRUD Methods (User-Aware)
    # -------------------------------------------------------------------------

    # --- News Item Methods ---
    async def get_news_by_id(
        self, news_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a specific news item by its ID for a given user.

        Args:
            news_id: The ID of the news item to retrieve.
            user_id: The ID of the user who owns or is associated with the news item.

        Returns:
            A dictionary representing the news item record if found and associated
            with the user, otherwise None.

        Side Effects:
            Reads news item data from the database.
        """
        record = await self._news_repo.get_by_id(news_id, user_id)
        return dict(record) if record else None

    async def get_all_news(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieves all news items for a specific user, with pagination.

        Args:
            user_id: The ID of the user whose news items are to be retrieved.
            limit: The maximum number of news items to return. Defaults to 100.
            offset: The number of news items to skip before starting to collect
                    the result set. Defaults to 0.

        Returns:
            A list of dictionaries, each representing a news item record
            associated with the user. Returns an empty list if no items are found.

        Side Effects:
            Reads news item data from the database.
        """
        records = await self._news_repo.get_all(user_id, limit, offset)
        return [dict(record) for record in records]

    async def get_news_with_filters(
        self,
        user_id: int,
        category_id: Optional[int] = None,
        source_id: Optional[int] = None,
        has_analysis: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
        search_term: Optional[str] = None,
        fetch_date: Optional[date] = None,
        sort_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves news items for a specific user based on various filter criteria,
        including the total count of matching items.

        Args:
            user_id: The ID of the user.
            category_id: Optional ID of the category to filter by.
            source_id: Optional ID of the source to filter by.
            has_analysis: Optional boolean to filter by analysis presence.
            page: Page number for pagination (1-indexed).
            page_size: Number of items per page.
            search_term: Optional term to search in news titles or content.
            fetch_date: Optional date to filter news items fetched on that day.
            sort_by: Optional field to sort the results by (e.g., 'fetch_date_desc').

        Returns:
            A dictionary containing:
                - "items": A list of dictionaries, each representing a news item
                           that matches the filter criteria for the specified user.
                - "total": An integer representing the total count of items
                           matching the filters (before pagination).

        Side Effects:
            Reads news item data from the database using complex filtering.
        """
        return await self._news_repo.get_news_with_filters_as_dict(
            user_id=user_id,
            category_id=category_id,
            source_id=source_id,
            analyzed=has_analysis,
            page=page,
            page_size=page_size,
            search_term=search_term,
            fetch_date=fetch_date,
            sort_by=sort_by,
        )

    async def update_news(
        self, news_id: int, user_id: int, news_item_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates an existing news item for a specific user.

        Note: This method is currently a placeholder and not fully implemented.

        Args:
            news_id: The ID of the news item to update.
            user_id: The ID of the user who owns the news item.
            news_item_data: A dictionary containing the news item fields to update.

        Returns:
            A dictionary representing the updated news item if successful,
            otherwise None. Currently returns None as it's not implemented.

        Side Effects:
            If implemented, would modify a news item record in the database.
            Currently logs a warning.
        """
        # TODO: Implement full news update logic.
        # This would involve fetching the item, verifying ownership (user_id),
        # applying changes from news_item_data, and saving back to the repository.
        logger.warning(
            f"update_news not implemented yet (news_id: {news_id}, user_id: {user_id})"
        )
        return None

    async def delete_news(self, news_id: int, user_id: int) -> bool:
        """Deletes a news item for a specific user.

        Args:
            news_id: The ID of the news item to delete.
            user_id: The ID of the user who owns the news item.

        Returns:
            True if the news item was successfully deleted, False otherwise
            (e.g., item not found or not owned by the user).

        Side Effects:
            Removes a news item record from the database.
        """
        return await self._news_repo.delete(news_id, user_id)

    async def clear_all_news_for_user(self, user_id: int) -> bool:
        """Deletes all news items associated with a specific user.

        Args:
            user_id: The ID of the user whose news items are to be cleared.

        Returns:
            True if all news items for the user were successfully deleted,
            False otherwise (e.g., if an error occurs during deletion).

        Side Effects:
            Removes all news item records for the specified user from the database.
        """
        return await self._news_repo.clear_all_for_user(user_id)

    # --- Category Methods ---
    async def get_all_categories(self, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all news categories for a specific user.

        Args:
            user_id: The ID of the user whose categories are to be retrieved.

        Returns:
            A list of dictionaries, each representing a news category record
            associated with the user.

        Side Effects:
            Reads category data from the database.
        """
        records = await self._category_repo.get_all(user_id)
        return [dict(record) for record in records]

    async def get_all_categories_with_counts(
        self, user_id: int
    ) -> List[Dict[str, Any]]:
        """Retrieves all categories for a user, including counts of associated news sources.

        The news source counts are also user-specific.

        Args:
            user_id: The ID of the user.

        Returns:
            A list of dictionaries, each representing a category along with
            a count of news sources associated with it for that user.
            Example: `[{'id': 1, 'name': 'Tech', 'user_id': 1, 'source_count': 5}, ...]`

        Side Effects:
            Reads category and news source data from the database.
        """
        records = await self._category_repo.get_with_source_count(user_id)
        return [dict(record) for record in records]

    async def get_category_by_id(
        self, category_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a specific news category by its ID for a given user.

        Args:
            category_id: The ID of the category to retrieve.
            user_id: The ID of the user who owns the category.

        Returns:
            A dictionary representing the category record if found and owned
            by the user, otherwise None.

        Side Effects:
            Reads category data from the database.
        """
        record = await self._category_repo.get_by_id(category_id, user_id)
        return dict(record) if record else None

    async def add_category(self, name: str, user_id: int) -> Optional[int]:
        """Adds a new news category for a specific user.

        Args:
            name: The name of the new category.
            user_id: The ID of the user for whom the category is being created.

        Returns:
            The ID of the newly created category if successful, otherwise None.

        Side Effects:
            Adds a new category record to the database for the user.
        """
        name = name.strip()
        if not name:
            logger.warning(
                f"Attempted to add category with empty name for user {user_id}."
            )
            return None
        return await self._category_repo.add(name, user_id)

    async def create_category(
        self, category_data: NewsCategoryCreate, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Creates a new news category for a user based on Pydantic model data.

        Args:
            category_data: A `NewsCategoryCreate` model instance containing the
                           category details (name).
            user_id: The ID of the authenticated user creating the category.

        Returns:
            A dictionary representing the newly created category `{'id': ..., 'name': ..., 'user_id': ...}`
            if successful, otherwise None (e.g., if name is empty or creation fails).

        Side Effects:
            Adds a new category record to the database for the user.
        """
        # user_id for the category is the authenticated user_id, not from payload model
        name = category_data.name.strip()
        if not name:
            logger.warning(
                f"Attempted to create category with empty name for user {user_id} via Pydantic model."
            )
            return None

        category_id = await self._category_repo.add(name, user_id)
        if not category_id:
            logger.error(
                f"Failed to add category '{name}' to database for user {user_id}."
            )
            return None

        return {"id": category_id, "name": name, "user_id": user_id}

    async def update_category(
        self, category_id: int, user_id: int, new_name: str
    ) -> bool:
        """Updates the name of an existing news category for a specific user.

        Args:
            category_id: The ID of the category to update.
            user_id: The ID of the user who owns the category.
            new_name: The new name for the category.

        Returns:
            True if the category was successfully updated, False otherwise
            (e.g., category not found, not owned by user, or update failed).

        Side Effects:
            Modifies a category record's name in the database.
        """
        new_name = new_name.strip()
        if not new_name:
            logger.warning(
                f"Attempted to update category {category_id} with empty name for user {user_id}."
            )
            return False
        return await self._category_repo.update(category_id, user_id, new_name)

    async def update_category_from_dict(
        self, category_id: int, user_id: int, category_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates a category for a user using data from a dictionary.

        Args:
            category_id: The ID of the category to update.
            user_id: The ID of the user who owns the category.
            category_data: A dictionary containing the category data to update.
                           Expected to have a 'name' key.

        Returns:
            A dictionary representing the updated category if successful,
            otherwise None.

        Side Effects:
            Modifies a category record's name in the database.
        """
        new_name = category_data.get("name", "").strip()
        if not new_name:
            logger.warning(
                f"Attempted to update category {category_id} with empty name from dict for user {user_id}."
            )
            return None

        success = await self._category_repo.update(category_id, user_id, new_name)
        if not success:
            return None

        updated_category_record = await self._category_repo.get_by_id(
            category_id, user_id
        )
        return dict(updated_category_record) if updated_category_record else None

    async def delete_category(self, category_id: int, user_id: int) -> bool:
        """Deletes a news category for a specific user.

        Args:
            category_id: The ID of the category to delete.
            user_id: The ID of the user who owns the category.

        Returns:
            True if the category was successfully deleted, False otherwise.

        Side Effects:
            Removes a category record from the database.
        """
        return await self._category_repo.delete(category_id, user_id)

    # --- Source Methods ---
    async def get_all_sources(self, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all news sources for a specific user, including their category information.

        Args:
            user_id: The ID of the user whose news sources are to be retrieved.

        Returns:
            A list of dictionaries, each representing a news source record
            (with associated category details) for the user.

        Side Effects:
            Reads news source and category data from the database.
        """
        records = await self._source_repo.get_all(user_id)
        return [dict(record) for record in records]

    async def get_sources_by_category_id(
        self, category_id: int, user_id: int
    ) -> List[Dict[str, Any]]:
        """Retrieves all news sources for a specific category belonging to a user.

        Args:
            category_id: The ID of the category whose sources are to be retrieved.
            user_id: The ID of the user who owns the category and sources.

        Returns:
            A list of dictionaries, each representing a news source record
            within the specified category for the user.

        Side Effects:
            Reads news source data from the database, filtered by category and user.
        """
        records = await self._source_repo.get_by_category(category_id, user_id)
        return [dict(record) for record in records]

    async def get_source_by_id(
        self, source_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a specific news source by its ID for a given user.

        Includes associated category information.

        Args:
            source_id: The ID of the news source to retrieve.
            user_id: The ID of the user who owns the news source.

        Returns:
            A dictionary representing the news source record (with category details)
            if found and owned by the user, otherwise None.

        Side Effects:
            Reads news source and category data from the database.
        """
        record = await self._source_repo.get_by_id(source_id, user_id)
        return dict(record) if record else None

    async def add_source(
        self, name: str, url: str, category_name: str, user_id: int
    ) -> Optional[int]:
        """Adds a new news source for a user.

        If the specified category name does not exist for the user,
        it attempts to create it.

        Args:
            name: The name of the new news source.
            url: The URL of the new news source.
            category_name: The name of the category for this source.
            user_id: The ID of the user creating the source.

        Returns:
            The ID of the newly created news source if successful, otherwise None.

        Side Effects:
            Adds a new news source record to the database. May also add a new
            category record if `category_name` is new for the user.
        """
        name = name.strip()
        url = url.strip()
        category_name = category_name.strip()

        if not name or not url or not category_name:
            logger.warning(
                f"Attempted to add source with empty name, URL, or category name for user {user_id}."
            )
            return None

        category_record = await self._category_repo.get_by_name(category_name, user_id)
        if category_record:
            category_id = category_record["id"]
        else:
            logger.info(
                f"Category '{category_name}' not found for user {user_id}. Creating it."
            )
            category_id = await self._category_repo.add(category_name, user_id)
            if not category_id:
                logger.error(
                    f"Failed to create category '{category_name}' for user {user_id} while adding source."
                )
                return None

        return await self._source_repo.add(name, url, category_id, user_id)

    async def update_source(
        self, source_id: int, user_id: int, name: str, url: str, category_name: str
    ) -> bool:
        """Updates an existing news source for a user.

        If the specified category name does not exist for the user,
        it attempts to create it.

        Args:
            source_id: The ID of the news source to update.
            user_id: The ID of the user who owns the source.
            name: The new name for the source.
            url: The new URL for the source.
            category_name: The new category name for the source.

        Returns:
            True if the source was successfully updated, False otherwise.

        Side Effects:
            Modifies a news source record in the database. May also add a new
            category record if `category_name` is new for the user.
        """
        name = name.strip()
        url = url.strip()
        category_name = category_name.strip()

        if not name or not url or not category_name:
            logger.warning(
                f"Attempted to update source {source_id} with empty name, URL, or category name for user {user_id}."
            )
            return False

        category_record = await self._category_repo.get_by_name(category_name, user_id)
        if category_record:
            category_id = category_record["id"]
        else:
            logger.info(
                f"Category '{category_name}' not found for user {user_id} during source update. Creating it."
            )
            category_id = await self._category_repo.add(category_name, user_id)
            if not category_id:
                logger.error(
                    f"Failed to create category '{category_name}' for user {user_id} while updating source {source_id}."
                )
                return False

        return await self._source_repo.update(
            source_id, user_id, name, url, category_id
        )

    async def delete_source(self, source_id: int, user_id: int) -> bool:
        """Deletes a news source for a specific user.

        Args:
            source_id: The ID of the news source to delete.
            user_id: The ID of the user who owns the source.

        Returns:
            True if the source was successfully deleted, False otherwise.

        Side Effects:
            Removes a news source record from the database.
        """
        return await self._source_repo.delete(source_id, user_id)

    async def update_news_analysis(
        self, news_id: int, user_id: int, analysis_text: str
    ) -> bool:
        """Updates the analysis text for a specific news item owned by a user.

        Args:
            news_id: The ID of the news item to update.
            user_id: The ID of the user who owns the news item.
            analysis_text: The new analysis text.

        Returns:
            True if the analysis was successfully updated, False otherwise.

        Side Effects:
            Modifies the `analysis_content` (or similar field) of a news item
            record in the database.
        """
        return await self._news_repo.update_analysis(news_id, user_id, analysis_text)

    async def create_source(
        self, source_data: NewsSourceCreate, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Creates a news source for a user from Pydantic model data.

        Validates user ID, checks if the category exists for the user, and
        checks for existing sources with the same name or URL for that user.

        Args:
            source_data: A `NewsSourceCreate` model instance containing source details
                         (name, url, category_id).
            user_id: The ID of the authenticated user creating the source.

        Returns:
            A dictionary representing the newly created (or existing if duplicate)
            news source, including category details. Returns None if creation fails
            due to missing fields, non-existent category, or database error.

        Side Effects:
            Adds a new news source record to the database if it's unique for the user.
            Reads category and source data for validation.
        """
        # user_id for the source is the authenticated user_id, not from payload model
        name = source_data.name.strip()
        url = str(source_data.url).strip()
        category_id = source_data.category_id

        if not name or not url or category_id is None:
            logger.warning(
                f"Missing required fields (name, url, or category_id) for source creation. User: {user_id}, Data: {source_data.model_dump()}"
            )
            return None

        category = await self._category_repo.get_by_id(category_id, user_id)
        if not category:
            logger.warning(
                f"Category ID {category_id} not found or not accessible for user {user_id}."
            )
            return None

        existing_by_name = await self._source_repo.get_by_name(name, user_id)
        if existing_by_name:
            logger.warning(
                f"Source with name '{name}' already exists for user {user_id} (ID: {existing_by_name['id']}). Returning existing."
            )
            return await self.get_source_by_id(existing_by_name["id"], user_id)

        existing_by_url = await self._source_repo.get_by_url(url, user_id)
        if existing_by_url:
            logger.warning(
                f"Source with URL '{url}' already exists for user {user_id} (ID: {existing_by_url['id']}). Returning existing."
            )
            return await self.get_source_by_id(existing_by_url["id"], user_id)

        source_id = await self._source_repo.add(
            name=name, url=url, category_id=category_id, user_id=user_id
        )
        if not source_id:
            logger.error(
                f"Failed to add source '{name}' to database for user {user_id}."
            )
            return None

        new_source_dict = await self.get_source_by_id(source_id, user_id)
        return new_source_dict

    async def analyze_content_streaming(
        self, user_id: int, content: str, instructions: str
    ) -> AsyncGenerator[str, None]:
        """
        Analyzes arbitrary text content using the LLM based on provided instructions
        for a specific user and streams the analysis.

        Args:
            user_id: The ID of the user whose API key should be used.
            content: The text content to analyze.
            instructions: Instructions for the LLM on how to analyze the content.

        Yields:
            str: Chunks of the analysis text or error messages.

        Side Effects:
            Makes external LLM calls.
            Logs information, warnings, or errors related to the process.
        """
        logger.info(
            f"Initiating arbitrary content analysis stream for user_id: {user_id}."
        )
        llm_client: Optional[AsyncLLMClient] = (
            None  # Variable to hold the client instance
        )
        try:
            # Get the client. _get_user_llm_client might return None or raise an exception.
            raw_llm_client = await self._get_user_llm_client(user_id)
            if raw_llm_client is None:
                logger.warning(
                    f"No valid LLM client for user {user_id}. Cannot perform arbitrary content analysis."
                )
                yield "Error: LLM client could not be initialized. Please check your API key configuration."
                return

            llm_client = raw_llm_client  # Assign to the variable in the broader scope for the finally block

            user_prompt = f'{instructions}\\n\\nAnalyze the following content:\\n\\"\\"\\"{content}\\"\\"\\"'
            logger.info(
                f"Streaming arbitrary content analysis from LLM for user_id: {user_id}."
            )

            # Use the client as an async context manager
            async with llm_client as client_instance:
                llm_response_stream = client_instance.stream_completion_content(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an AI assistant performing content analysis based on user instructions.",
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=4096,
                    temperature=0.7,
                )
                async for chunk in llm_response_stream:
                    yield chunk

            logger.info(
                f"LLM stream completed for arbitrary content analysis for user {user_id}."
            )

        except Exception as e_stream:
            logger.error(
                f"Error during arbitrary content analysis streaming for user_id: {user_id}: {e_stream}",
                exc_info=True,
            )
            yield f"Error during analysis process: {str(e_stream)}"
        finally:
            if llm_client:  # If client was obtained
                try:
                    # Attempt to close it, similar to stream_analysis_for_news_item
                    if hasattr(llm_client, "close") and callable(llm_client.close):
                        await llm_client.close()
                    logger.debug(
                        f"LLM client explicitly handled in finally block for arbitrary content analysis, user {user_id}."
                    )
                except Exception as e_close:
                    logger.error(
                        f"Error closing LLM client in finally block for arbitrary content analysis, user {user_id}: {e_close}"
                    )

    async def stream_analysis_for_news_item(
        self, news_id: int, user_id: int, force: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Analyzes content of a specific news item for a user and streams the analysis.

        Args:
            news_id: The ID of the news item to analyze.
            user_id: The ID of the user who owns the news item.
            force: If True, re-analyzes the content even if an analysis already
                   exists. Defaults to False.

        Yields:
            str: Chunks of the analysis text or error messages.

        Side Effects:
            Reads DB, makes external LLM calls, writes to DB.
        """
        logger.info(
            f"Initiating analysis stream for news_id: {news_id}, user_id: {user_id}, force: {force}"
        )

        llm_client: Optional[AsyncLLMClient] = None
        try:
            llm_client = await self._get_user_llm_client(user_id)
            if llm_client is None:
                logger.warning(
                    f"No valid LLM client for user {user_id}. Cannot perform analysis for news {news_id}."
                )
                yield "Error: LLM client could not be initialized. Please check your API key configuration."
                return

            if not force:
                existing_analysis = await self._news_repo.get_analysis_by_id(
                    news_id, user_id
                )
                if existing_analysis and existing_analysis.strip():
                    logger.info(
                        f"Streaming existing analysis for news_id {news_id}, user_id {user_id}."
                    )
                    yield existing_analysis
                    # No need to close client here if it wasn't used with async with yet
                    return

            news_content = await self._news_repo.get_content_by_id(news_id, user_id)
            if not news_content:
                logger.error(
                    f"No content found for news_id {news_id} or item not owned by user {user_id}."
                )
                yield "Error: News content not found or access denied."
                return

            user_prompt = f"""
                Please analyze the following news content:\n\"\"\"\n{news_content}\n\"\"\"
                **Write in the same language as the original content** (e.g., if the original content is in Chinese, the analysis should also be in Chinese).
                """

            full_analysis = ""
            logger.info(
                f"Streaming new analysis from LLM for news_id {news_id}, user_id {user_id}."
            )

            async with llm_client as client_instance:
                llm_response_stream = client_instance.stream_completion_content(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT_ANALYZE_CONTENT},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=4096,
                    temperature=0.7,
                )
                async for chunk in llm_response_stream:
                    full_analysis += chunk
                    yield chunk

            logger.info(
                f"LLM stream completed for news {news_id}. Full analysis length: {len(full_analysis)} chars."
            )

            if full_analysis.strip():
                try:
                    await self._news_repo.update_analysis(
                        news_id, user_id, full_analysis
                    )
                    logger.info(
                        f"Successfully saved new analysis for news_id {news_id}, user_id {user_id}."
                    )
                except Exception as e_save:
                    logger.error(
                        f"Failed to save new analysis for news_id {news_id}, user_id {user_id}: {e_save}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    f"LLM generated an empty or whitespace-only analysis for news {news_id}. Not saving."
                )

        except Exception as e_stream:
            logger.error(
                f"Error during analysis streaming for news_id {news_id}, user_id {user_id}: {e_stream}",
                exc_info=True,
            )
            yield f"Error during analysis process: {str(e_stream)}"
        finally:
            if llm_client:  # Check if client was initialized
                try:
                    if hasattr(llm_client, "close") and callable(llm_client.close):
                        await llm_client.close()
                    logger.debug(
                        f"LLM client explicitly handled in finally block for news {news_id}."
                    )
                except Exception as e_close:
                    logger.error(
                        f"Error closing LLM client in finally block for news {news_id}: {e_close}"
                    )

    async def _get_user_llm_client(self, user_id: int) -> Optional[AsyncLLMClient]:
        """
        Retrieves and initializes an AsyncLLMClient using the user's API key.

        Args:
            user_id: The ID of the user for whom to get the LLM client.

        Returns:
            An instance of `AsyncLLMClient` or `None`.

        Side Effects:
            Reads DB, logs warnings/errors.
        """
        logger.debug(
            f"Fetching API keys for user_id: {user_id} to initialize LLM client."
        )
        api_keys_data = await self._api_key_repo.get_all(user_id)

        if not api_keys_data:
            logger.warning(f"No API keys found in database for user_id: {user_id}.")
            return None

        for key_data_row in api_keys_data:
            try:
                api_key_model = ApiKey.model_validate(dict(key_data_row))
                logger.info(
                    f"Attempting to use API key ID {api_key_model.id} "
                    f"for user {user_id}. Base URL: {api_key_model.base_url}, Model: {api_key_model.model}"
                )
                return AsyncLLMClient(
                    base_url=str(api_key_model.base_url),  # Ensure str
                    api_key=api_key_model.api_key,
                    model=api_key_model.model,
                    context=api_key_model.context,
                    max_output_tokens=api_key_model.max_output_tokens,
                )
            except Exception as e:
                logger.error(
                    f"Failed to validate API key or instantiate LLM client for API key ID "
                    f"{(dict(key_data_row)).get('id', 'N/A')}. Error: {e}",
                    exc_info=True,
                )
                continue

        logger.warning(
            f"No valid API key configuration led to a successful LLM client instantiation for user_id: {user_id}."
        )
        return None
