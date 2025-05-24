/**
 * @file types.ts
 * @description This file contains TypeScript type and interface definitions
 * used throughout the SmartInfo frontend application. These types define the
 * shape of data exchanged with the backend API and used within frontend components
 * and services.
 *
 * @file_purpose To provide a centralized and consistent set of type definitions
 *               for data structures, enhancing code clarity, type safety, and
 *               developer productivity.
 */

// Note: The `AnyHttpUrl` type mentioned in the guide's example for NewsItem
// is not a standard TypeScript type. It would typically be `string` or a
// custom branded type if strict URL validation is enforced at the type level.
// For simplicity and consistency with the provided code, `string` will be used
// for URL fields unless a specific URL type is already in use.

/**
 * @interface NewsCategory
 * @description Defines the structure for a news category object.
 */
export interface NewsCategory {
  id: number;             // Unique identifier for the category.
  name: string;           // Name of the category.
  source_count?: number;  // [source_count] Optional: Number of news sources associated with this category.
}

/**
 * @interface NewsCategoryCreate
 * @description Defines the structure for creating a new news category.
 */
export interface NewsCategoryCreate {
  name: string;           // Name for the new category.
}

/**
 * @interface NewsCategoryUpdate
 * @description Defines the structure for updating an existing news category.
 */
export interface NewsCategoryUpdate {
  name: string;           // New name for the category.
}

// --- News Source Types ---

/**
 * @interface NewsSource
 * @description Defines the structure for a news source object.
 */
export interface NewsSource {
  id: number;             // Unique identifier for the source.
  name: string;           // Name of the news source.
  url: string;            // URL of the news source's website or RSS feed.
  category_id: number;    // ID of the category this source belongs to.
  category_name?: string; // [category_name] Optional: Name of the category (often joined from backend).
}

/**
 * @interface NewsSourceCreate
 * @description Defines the structure for creating a new news source.
 */
export interface NewsSourceCreate {
  name: string;           // Name for the new source.
  url: string;            // URL for the new source.
  category_id: number;    // ID of the category for the new source.
}

/**
 * @interface NewsSourceUpdate
 * @description Defines the structure for updating an existing news source.
 * All properties are optional for partial updates.
 */
export interface NewsSourceUpdate {
  name?: string;          // [name] Optional: New name for the source.
  url?: string;           // [url] Optional: New URL for the source.
  category_id?: number;   // [category_id] Optional: New category ID for the source.
}

// --- News Item Types ---

/**
 * @interface NewsItem
 * @description Defines the structure for a single news article object.
 * This is a core data type used throughout the frontend.
 */
export interface NewsItem {
  id: number;             // Unique database identifier for the news item.
  title: string;          // Main title of the article.
  url: string;            // URL to the original article source.
  source_id?: number;     // [source_id] Optional: ID of the news source this item came from.
  category_id?: number;   // [category_id] Optional: ID of the category this item belongs to.
  summary?: string;       // [summary] Optional: A brief summary of the news item.
  content?: string;       // [content] Optional: Full content of the news item (if fetched).
  analysis?: string;      // [analysis] Optional: LLM-generated analysis of the content.
  date?: string;          // [date] Optional: Publication date (typically ISO string format).
  source_name?: string;   // [source_name] Optional: Name of the news source (often joined).
  category_name?: string; // [category_name] Optional: Name of the category (often joined).
  created_at?: string;    // [created_at] Optional: Timestamp (ISO string) when the item was saved in SmartInfo.
  top_image?: string;     // [top_image] Optional: URL for the article's main image.
}

/**
 * @interface NewsItemCreate
 * @description Defines the structure for creating a new news item.
 */
export interface NewsItemCreate {
  title: string;          // Title of the new news item.
  url: string;            // URL of the new news item.
  source_id?: number;     // [source_id] Optional: Source ID for the item.
  category_id?: number;   // [category_id] Optional: Category ID for the item.
  summary?: string;       // [summary] Optional: Summary for the item.
  content?: string;       // [content] Optional: Full content for the item.
  should_analyze?: boolean; // [should_analyze=false] Optional: Flag to indicate if analysis should be triggered upon creation.
}

/**
 * @interface PaginatedNewsResponse
 * @description Defines the structure for a paginated API response for news items.
 * This is used when fetching a list of news items that supports pagination.
 */
export interface PaginatedNewsResponse {
  items: NewsItem[];      // An array of NewsItem objects for the current page.
  total: number;          // Total number of news items available across all pages.
  page?: number;          // [page] Optional: The current page number (1-indexed).
  page_size?: number;     // [page_size] Optional: The number of items per page.
}

/**
 * @interface NewsItemUpdate
 * @description Defines the structure for updating an existing news item.
 * All properties are optional for partial updates.
 */
export interface NewsItemUpdate {
  title?: string;         // [title] Optional: New title.
  source_id?: number;     // [source_id] Optional: New source ID.
  category_id?: number;   // [category_id] Optional: New category ID.
  summary?: string;       // [summary] Optional: New summary.
  content?: string;       // [content] Optional: New content.
  analysis?: string;      // [analysis] Optional: New or updated analysis.
  date?: string;          // [date] Optional: New publication date.
}

/**
 * @interface NewsFilterParams
 * @description Defines the parameters that can be used to filter and paginate news items
 * when querying the API.
 */
export interface NewsFilterParams {
  category_id?: number;   // [category_id] Optional: Filter by category ID.
  source_id?: number;     // [source_id] Optional: Filter by source ID.
  analyzed?: boolean;     // [analyzed] Optional: Filter by analysis status (true for analyzed, false for not).
  page?: number;          // [page] Optional: Page number for pagination (1-indexed).
  page_size?: number;     // [page_size] Optional: Number of items per page.
  search_term?: string;   // [search_term] Optional: Text to search in title, summary, etc.
  fetch_date?: string;    // [fetch_date] Optional: Filter by fetch date (YYYY-MM-DD format).
  sort_by?: string;       // [sort_by] Optional: Field and direction to sort by (e.g., 'created_at_desc', 'date_asc').
}

// --- Task Types for News Fetching ---

/**
 * @interface FetchTaskItem
 * @description Defines the structure for tracking the progress of a news fetching task for a single source.
 * Used in UI elements like the Task Progress Drawer.
 */
export interface FetchTaskItem {
  sourceId: number;           // ID of the news source being fetched.
  sourceName: string;         // Name of the news source.
  status: string;             // Current status of the task (e.g., "Pending", "Crawling", "Complete", "Error").
  progress?: number;          // [progress] Optional: Progress percentage (0-100).
  error?: boolean;            // [error=false] Optional: True if the task encountered an error.
  skipped?: boolean;          // [skipped=false] Optional: True if the task was skipped (e.g., due to recent fetch).
  items_saved_this_run?: number; // [items_saved_this_run] Optional: Number of items saved in the current run (from WebSocket updates).
  items_saved?: number;       // [items_saved] Optional: Total items saved (typically for completed tasks).
}

/**
 * @interface FetchHistoryItem
 * @description Defines the structure for a historical record of news fetching activity,
 * typically retrieved from an API endpoint for display in the Task Progress Drawer.
 */
export interface FetchHistoryItem {
  source_id: number;          // ID of the news source. (Matches backend field name)
  source_name: string;        // Name of the news source.
  record_date: string;        // Date of the fetch record (YYYY-MM-DD format).
  items_saved_today: number;  // Number of items saved for this source on the record_date.
  last_updated_at: string;    // Timestamp (ISO string) when this history record was last updated.
}

// --- API Request Payloads for Tasks ---

/**
 * @interface UpdateAnalysisRequest
 * @description Defines the payload for updating the analysis of a news item.
 * (Note: This seems to have `task_id`, which might be for a specific analysis task,
 * or it might be a general update structure. Clarify if `task_id` is always present/needed.)
 */
export interface UpdateAnalysisRequest {
  task_id: string;        // Identifier for the analysis task or related entity.
  analysis: string;       // The new analysis content.
}

/**
 * @interface AnalyzeRequest
 * @description Defines the payload for requesting analysis of news items.
 */
export interface AnalyzeRequest {
  news_ids?: number[];    // [news_ids] Optional: Array of news item IDs to analyze. If empty or undefined, might imply "all unanalyzed".
  force?: boolean;        // [force=false] Optional: If true, re-analyze even if analysis already exists.
}

/**
 * @interface FetchSourceRequest
 * @description Defines the payload for requesting to fetch news from a specific source.
 */
export interface FetchSourceRequest {
  source_id: number;      // ID of the news source to fetch from.
}

/**
 * @interface FetchUrlRequest
 * @description Defines the payload for requesting to fetch news from a specific URL.
 */
export interface FetchUrlRequest {
  url: string;            // The URL to fetch and process as a news item.
  source_id?: number;     // [source_id] Optional: If known, the source ID to associate with this URL.
  should_analyze?: boolean; // [should_analyze=false] Optional: Flag to trigger analysis after fetching.
}

/**
 * @interface AnalyzeContentRequest
 * @description Defines the payload for requesting analysis of arbitrary text content.
 */
export interface AnalyzeContentRequest {
  content: string;        // The text content to be analyzed.
  instructions: string;   // Specific instructions for the LLM performing the analysis.
}

// --- API Key Types ---

/**
 * @interface ApiKey
 * @description Defines the structure for an API key object used for LLM services.
 */
export interface ApiKey {
  id: number;                 // Unique identifier for the API key entry.
  model: string;              // Name or identifier of the LLM model this key is for.
  base_url: string;           // Base URL of the LLM service API.
  api_key: string;            // The actual API key (sensitive, handle with care).
  context: number;            // Context window size/limit for the model.
  max_output_tokens: number;  // Maximum number of tokens the model can output in a single response.
  description?: string;       // [description] Optional: User-defined description for the key.
  created_date?: string;      // [created_date] Optional: Timestamp (ISO string) when the key was created.
  modified_date?: string;     // [modified_date] Optional: Timestamp (ISO string) when the key was last modified.
}

/**
 * @interface ApiKeyCreate
 * @description Defines the structure for creating a new API key entry.
 */
export interface ApiKeyCreate {
  model: string;              // Model name.
  base_url: string;           // API base URL.
  api_key: string;            // The API key string.
  context: number;            // Context length.
  max_output_tokens: number;  // Max output tokens.
  description?: string;       // [description] Optional: Description.
}

// --- User Preference Types ---

/**
 * @interface UserPreferenceUpdate
 * @description Defines the structure for updating user preferences (general settings).
 * The `settings` property is a flexible record for various key-value preference pairs.
 */
export interface UserPreferenceUpdate {
  settings: Record<string, any>; // A dictionary of setting keys and their values.
}

// --- Chat Types ---

/**
 * @interface Chat
 * @description Defines the structure for a chat session object.
 */
export interface Chat {
  id: number;                 // Unique identifier for the chat session.
  title: string;              // Title of the chat session (e.g., user-defined or auto-generated).
  created_at?: string;        // [created_at] Optional: Timestamp (ISO string) when the chat was created.
  updated_at?: string;        // [updated_at] Optional: Timestamp (ISO string) when the chat was last updated.
  messages?: Message[];       // [messages] Optional: Array of messages in this chat (if fetched).
}

/**
 * @interface ChatCreate
 * @description Defines the structure for creating a new chat session.
 */
export interface ChatCreate {
  title: string;              // Title for the new chat session.
}

// --- Message Types ---

/**
 * @interface Message
 * @description Defines the structure for a single message within a chat session.
 */
export interface Message {
  id: number;                 // Unique identifier for the message.
  chat_id: number;            // ID of the chat session this message belongs to.
  sender: string;             // Sender of the message (e.g., "user", "assistant", "system").
  content: string;            // Text content of the message.
  sequence_number: number;    // Order of the message within the chat.
  timestamp?: string;         // [timestamp] Optional: Timestamp (ISO string) when the message was created.
}

/**
 * @interface MessageCreate
 * @description Defines the structure for creating a new message.
 */
export interface MessageCreate {
  chat_id: number;            // ID of the chat session for the new message.
  sender: string;             // Sender of the new message.
  content: string;            // Content of the new message.
  sequence_number?: number;   // [sequence_number] Optional: Sequence number (often set by backend).
}

// --- Question/Answer Types (for chat interactions) ---

/**
 * @interface Question
 * @description Defines the structure for sending a question to the chat service.
 */
export interface Question {
  content: string;            // The content of the user's question or prompt.
  chat_id?: number;           // [chat_id] Optional: ID of the chat session this question belongs to.
  // If not provided, the backend might create a new chat or use a default.
}

/**
 * @interface ChatAnswer
 * @description Defines the structure for an answer received from the chat service.
 * (Note: This type might represent the AI's response message content or a wrapper.
 * The guide example for `askQuestion` in `chatService.ts` implies `content` is directly
 * part of the response, potentially along with `chat_id` and `message_id` for context.)
 */
export interface ChatAnswer {
  chat_id: number;            // ID of the chat session the answer pertains to.
  message_id?: number;        // [message_id] Optional: ID of the created assistant message.
  content: string;            // The content of the AI's answer.
}