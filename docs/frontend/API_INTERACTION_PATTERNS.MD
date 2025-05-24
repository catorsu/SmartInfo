# SmartInfo Frontend: API Interaction Patterns Guide

## 1. Introduction

This guide outlines the standard patterns and practices for interacting with the SmartInfo backend API from the frontend application. Consistent API interaction patterns are crucial for building robust, maintainable, and user-friendly features.

This document is intended for frontend developers and AI assistants to understand how to:
*   Make API calls using the established service layer.
*   Handle API responses, including success and error states.
*   Manage loading states in the UI.
*   Interact with streaming API endpoints.

For details on specific backend API endpoints, refer to the `API_REFERENCE_GUIDE.md` and the auto-generated OpenAPI documentation.

## 2. Core API Client (`frontend/src/services/api.ts`)

All HTTP communication with the backend API is managed through a centralized Axios instance defined in `frontend/src/services/api.ts`.

*   **Base URL:** The `baseURL` for the Axios instance is configured using the `NEXT_PUBLIC_API_URL` environment variable (e.g., `http://localhost:8000`). All API calls made through this instance are relative to `/api` (as the backend API is prefixed with `/api`).
*   **Default Headers:** Default headers like `Content-Type: application/json` are set.
*   **Timeout:** A default request timeout is configured.

### 2.1. Request Interceptor (Authentication)
*   The Axios instance includes a request interceptor that automatically adds the JWT `Authorization` header to outgoing requests if an `authToken` is found in `localStorage`.
    ```typescript
    // Simplified from api.ts
    api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
          config.headers.set('Authorization', `Bearer ${token}`);
        }
        return config;
      }
    );
    ```
*   This ensures that authenticated requests are correctly made without needing to manually add the token for each call.

### 2.2. Response Interceptor (Global Error Handling)
*   A response interceptor is in place to handle global API error responses:
    *   **Network Errors:** Logs network errors to the console.
    *   **`401 Unauthorized`:** If a `401` error is received (and it's not from the login endpoint itself), it dispatches a custom `auth-error` event with `detail: { type: 'token-expired' }`. This event is listened for in `AuthContext.tsx` to trigger a global logout.
    *   Other API errors are logged to the console.

## 3. Service Layer Pattern (`frontend/src/services/*.ts`)

Direct use of the `api.ts` Axios instance in UI components is discouraged. Instead, API calls are encapsulated within service functions.

*   **Purpose:**
    *   **Abstraction:** Components don't need to know the specific API endpoint paths or HTTP methods.
    *   **Reusability:** Service functions can be reused across multiple components.
    *   **Separation of Concerns:** Keeps API interaction logic separate from UI rendering logic.
    *   **Type Safety:** Service functions are typed (arguments and return values), providing better type safety for API interactions.
*   **Structure:**
    *   Each file in `frontend/src/services/` typically groups functions related to a specific backend resource or feature (e.g., `authService.ts`, `newsService.ts`, `chatService.ts`, `settingsService.ts`).
    *   Each function usually maps to one backend API endpoint.
*   **Example (`newsService.ts` - `getNewsItems`):**
    ```typescript
    // frontend/src/services/newsService.ts
    import api from './api';
    import { NewsFilterParams, PaginatedNewsResponse } from '../utils/types'; // Import PaginatedNewsResponse

    export const getNewsItems = async (params: NewsFilterParams): Promise<PaginatedNewsResponse> => {
      // The backend API now returns an object: { items: NewsItem[], total: number, page?: number, page_size?: number }
      const response = await api.get<PaginatedNewsResponse>(`${BASE_PATH}/items`, { params });
      return response.data; 
    };
    ```
*   **Return Values:** Service functions typically return a `Promise` that resolves with the `response.data` from the Axios call (the actual JSON payload from the backend).
*   **Error Handling:** While service functions might catch errors to log them, they often re-throw the error (or Axios throws it) to be handled by the calling component. The `utils/apiErrorHandler.ts` provides helpers for this.

## 4. Common API Call Pattern in Components/Pages

UI components or pages that need to fetch or submit data typically follow this pattern:

### 4.1. State Management for API Calls
*   Use `useState` to manage local component state for:
    *   `loading (boolean)`: To indicate an ongoing API request (e.g., for displaying spinners).
    *   `error (ErrorType | string | null)`: To store any error received from the API call.
    *   `data (DataType | null)`: To store the data successfully fetched from the API.
    ```typescript
    const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [fetchError, setFetchError] = useState<string | null>(null);
    ```

### 4.2. Making the API Call
*   Use `async/await` syntax within an effect hook (`useEffect` for initial data fetching) or an event handler (e.g., form submission).
*   Wrap the API call (to the service function) in a `try/catch` block.
    ```typescript
    // Example in a React component
    // Assume 'totalItems' state exists: const [totalItems, setTotalItems] = useState<number>(0);
    useEffect(() => {
      const fetchNews = async () => {
        setIsLoading(true);
        setFetchError(null);
        try {
          const params: NewsFilterParams = { page: 1, page_size: 10 };
          // newsService.getNewsItems now returns { items: NewsItem[], total: number, ... }
          const response = await newsService.getNewsItems(params); 
          setNewsItems(response.items);
          setTotalItems(response.total); // Assuming you have a state for total items for pagination
        } catch (err) {
          const errorDetails = extractErrorMessage(err); 
          setFetchError(errorDetails.message);
          // message.error(errorDetails.message);
        } finally {
          setIsLoading(false);
        }
      };
      fetchNews();
    }, [/* dependencies for re-fetching, e.g., filters.page, filters.page_size */]);
    ```

### 4.3. UI Feedback
*   **Loading State:** Use Ant Design's `<Spin />` component or similar indicators when `isLoading` is true.
*   **Error State:** Display error messages using Ant Design's `<Alert />` component for persistent errors on a page, or `message.error()` for transient notifications.
*   **Success State:** Render the fetched `data`. Use `message.success()` for successful mutation operations (POST, PUT, DELETE).

## 5. Handling Specific HTTP Responses

*   **2xx (Success):**
    *   `200 OK`: Typically for `GET` requests. Process `response.data`.
    *   `201 Created`: For `POST` requests that create a new resource. `response.data` usually contains the created resource.
    *   `204 No Content`: For `DELETE` requests. No response body to process.
*   **4xx (Client Errors):**
    *   **`401 Unauthorized`:**
        *   Handled globally by the Axios response interceptor in `api.ts`.
        *   It dispatches a `CustomEvent('auth-error', { detail: { type: 'token-expired' } })`.
        *   `AuthContext.tsx` listens for this event and triggers the `logout()` function, which clears local session data and redirects to `/login`.
        *   Individual components generally do not need to handle `401` explicitly unless they are part of the login/registration flow itself.
    *   **`403 Forbidden`:** The user is authenticated but not authorized for the resource. Display an appropriate error message (e.g., "Access Denied").
    *   **`404 Not Found`:** The requested resource does not exist or isn't accessible to the user. Display a "Not Found" message or UI.
    *   **`409 Conflict`:** The request conflicts with existing data (e.g., unique constraint violation). Display a relevant error message.
    *   **`422 Unprocessable Entity`:** Indicates validation errors from the backend (Pydantic). The response body (`error.response.data.detail`) usually contains an array of specific validation errors. While `extractErrorMessage` might provide a generic message, more sophisticated forms might parse this array to display field-specific errors.
*   **5xx (Server Errors):** Display a generic error message to the user (e.g., "An unexpected error occurred. Please try again later."). `extractErrorMessage` will provide the server's detail if available.

## 6. Streaming API Interactions

For endpoints that stream data (e.g., LLM responses for chat or news analysis), the interaction pattern is different.

### 6.1. Chat Streaming (`pages/chat/[id].tsx`)
*   The `chatService.askQuestion()` function is special: it makes a `fetch` API call (not Axios, to directly access the `Response` body stream) and returns the raw `Response` object.
*   The component then uses `response.body.getReader()` to read chunks from the stream:
    ```typescript
    // Simplified from pages/chat/[id].tsx
    const response = await chatService.askQuestion({ chat_id: chat.id, content: userMessageContent });
    if (!response.body) throw new Error('Response body is null');
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let done = false;
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        // Append chunk to message content in React state
        setMessages(prev => prev.map(msg => msg.id === assistantStreamingId ? { ...msg, content: msg.content + chunk } : msg));
      }
    }
    ```
*   State is updated incrementally as chunks arrive.

### 6.2. News Analysis Streaming (`AnalysisStreamManager.ts`)
*   `frontend/src/streaming/AnalysisStreamManager.ts` encapsulates the logic for initiating and managing analysis streams from `newsService.streamAnalysis()`.
*   **Initiation:** Components call `analysisStreamManager.initiateStream(newsItemId)`.
*   **Subscription:** Components subscribe to updates for a specific `newsItemId` using `analysisStreamManager.subscribe(newsItemId, callback)`.
*   **Updates:** The manager reads the stream in the background and calls registered callbacks with the accumulated content, streaming status, and errors.
*   **Usage:** `AnalysisWindowContent.tsx` uses this manager to display streamed analysis.

## 7. Error Reporting and User Feedback

*   **`utils/apiErrorHandler.ts`:**
    *   `extractErrorMessage(error: unknown)`: Parses Axios errors (and other errors) to provide a structured error object (`{ type: string, message: string, status?: number }`).
    *   `handleApiError(error: unknown, customMessage?: string)`: Uses `extractErrorMessage` and displays an Ant Design `message.error()` for general errors, but logs `404/403` errors to console without a global message.
*   **Ant Design Components for Feedback:**
    *   `message.success('Operation successful!')`
    *   `message.error('An error occurred: ' + errorMessage)`
    *   `message.warning('Please check your input.')`
    *   `<Alert type="error" message="Error Title" description={errorMessage} />` for more persistent error displays.

## 8. Best Practices

*   **Always Use Service Layer:** Components should not make direct `api.ts` (Axios) calls. Use the functions provided in `frontend/src/services/`.
*   **Manage Loading/Error States:** Every API call that affects the UI should have associated loading and error states to provide feedback to the user.
*   **Handle Promises Correctly:** Use `async/await` with `try/catch` for cleaner asynchronous code.
*   **Type Safety:** Leverage TypeScript types for request payloads and expected responses to catch errors at build time.
*   **User Feedback:** Provide clear and actionable feedback to the user for both successful operations and errors.

By following these patterns, we ensure that frontend interactions with the backend API are consistent, robust, and easier to develop and maintain for both humans and AI assistants.