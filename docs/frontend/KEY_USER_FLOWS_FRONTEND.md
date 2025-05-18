# SmartInfo Frontend: Key User Flows

## 1. Introduction

This document describes key user flows within the SmartInfo frontend application. Understanding these flows helps developers and AI assistants grasp how users interact with the application to achieve their goals, and how different pages, components, and services collaborate to deliver the user experience.

Each flow outlines the user's goal, entry points, key components involved, a sequence of actions and system responses, and important state/API interactions.

## 2. Core User Flows

### 2.1. User Registration

*   **Goal:** Allow a new user to create an account.
*   **Trigger/Entry Point:** Clicking the "Register" link on the Login page (`/login`) or navigating directly to `/register`.
*   **Key Pages & Components:**
    *   `pages/register.tsx`
    *   `components/auth/withAuth.tsx` (indirectly, as public paths bypass it)
    *   `styles/LoginPage.module.css` (shared with login)
    *   Ant Design components (`Form`, `Input`, `Button`, `Alert`, `Card`)
*   **Sequence of Steps / User Actions:**
    1.  **Navigation:** User navigates to the `/register` page.
    2.  **Form Display:** `RegisterPage` component renders a registration form with fields for username, password, and confirm password.
    3.  **User Input:** User fills in the required fields.
        *   *Component:* Ant Design `Input` components within a `Form`.
        *   *State:* Local component state in `RegisterPage` manages form input and validation messages.
    4.  **Submission:** User clicks the "Register" button.
        *   *Component:* Ant Design `Button`.
        *   *Action:* `onFinish` handler in `RegisterPage` is triggered.
    5.  **Client-Side Validation:** Ant Design `Form` performs initial client-side validation (e.g., required fields, password match).
    6.  **API Call:** If client-side validation passes, `RegisterPage` calls `authContext.signup(username, password)`.
        *   *Context:* `AuthContext.signup()` is invoked.
        *   *Service:* `authService.registerUser()` is called internally by `AuthContext`.
        *   *API Endpoint:* `POST /api/auth/register`.
    7.  **Loading State:** `AuthContext` sets its `loading` state to true. `RegisterPage` might display a spinner.
    8.  **Backend Processing:** Backend attempts to create the user.
    9.  **API Response & State Update:**
        *   **Success (201 Created):**
            *   `AuthContext` receives the `LoginResponse` (token, user details).
            *   It stores the auth token in `localStorage`.
            *   Updates `isAuthenticated`, `user`, and `token` state.
            *   Sets `loading` to false.
            *   `RegisterPage` (via `AuthContext` logic) navigates the user to the main application page (e.g., `/` or `/index.tsx`) using `router.push('/')`.
        *   **Failure (e.g., 400 Bad Request - username taken, 500 Internal Server Error):**
            *   `AuthContext` catches the error.
            *   Sets `loading` to false.
            *   The error is propagated to `RegisterPage`.
            *   `RegisterPage` displays an error message using Ant Design `Alert`.
*   **Key State Management Contexts Used:** `AuthContext`.
*   **Outcome:**
    *   **Success:** New user account created, user is logged in and redirected to the application's main page.
    *   **Failure:** User remains on the registration page with an error message displayed.

### 2.2. User Login

*   **Goal:** Allow an existing user to log into their account.
*   **Trigger/Entry Point:** Navigating to `/login` (default for unauthenticated users or direct navigation).
*   **Key Pages & Components:**
    *   `pages/login.tsx`
    *   `components/auth/withAuth.tsx` (indirectly)
    *   `styles/LoginPage.module.css`
    *   Ant Design components (`Form`, `Input`, `Button`, `Alert`, `Card`)
*   **Sequence of Steps / User Actions:**
    1.  **Navigation:** User navigates to `/login`.
    2.  **Form Display:** `LoginPage` component renders a login form (username, password).
    3.  **User Input:** User enters credentials.
    4.  **Submission:** User clicks "Log in."
    5.  **API Call:** `LoginPage` calls `authContext.login(username, password)`.
        *   *Context:* `AuthContext.login()` invoked.
        *   *Service:* `authService.loginUser()` called internally.
        *   *API Endpoint:* `POST /api/auth/token`.
    6.  **Loading State:** `AuthContext` sets `loading` to true. `LoginPage` may show a spinner.
    7.  **Backend Processing:** Backend validates credentials.
    8.  **API Response & State Update:**
        *   **Success (200 OK):**
            *   `AuthContext` receives `LoginResponse`.
            *   Stores token, updates `isAuthenticated`, `user`, `token` state.
            *   Sets `loading` to false.
            *   Navigates user to the main application page (or `returnUrl` if specified) using `router.push()`.
        *   **Failure (e.g., 401 Unauthorized - bad credentials):**
            *   `AuthContext` catches error, sets `loading` to false.
            *   Error propagated to `LoginPage`, which displays an error `Alert`.
*   **Key State Management Contexts Used:** `AuthContext`.
*   **Outcome:**
    *   **Success:** User is authenticated, token stored, redirected to the main app.
    *   **Failure:** User stays on login page with an error message.

### 2.3. News Browsing, Filtering, and Searching

*   **Goal:** Allow users to view their aggregated news items, filter them by category/source, and search by keywords.
*   **Trigger/Entry Point:** Navigating to the homepage (`/` or `/index.tsx`), which is the main news feed.
*   **Key Pages & Components:**
    *   `pages/index.tsx` (`NewsPage`)
    *   `components/layout/MainLayout.tsx` (provides filter toggles, action buttons)
    *   Ant Design components (`Select`, `Input`, `List`, `Card`, `Pagination`, `FloatButton`)
*   **Sequence of Steps / User Actions:**
    1.  **Initial Load:**
        *   `NewsPage` mounts. `useEffect` hook triggers `loadNews(initialFilters)`.
        *   `loadNews` sets local `loading` state to true.
        *   `newsService.getNewsItems(filters)` is called.
        *   *API Endpoint:* `GET /api/news/items` (with default filters).
        *   On response, `news` and `total` items state are updated, `loading` set to false.
        *   News items are rendered in an Ant Design `List` of `Card`s.
        *   Filter controls (Category `Select`, Source `Select`, Search `Input`) are populated from `categories` and `sources` state (fetched in a separate `useEffect`).
    2.  **User Applies a Filter (e.g., Selects a Category):**
        *   User interacts with a filter `Select` component.
        *   `handleCategoryChange` (or similar handler) in `NewsPage` updates the `filters` state (e.g., sets `category_id` and resets `page` to 1).
        *   The `useEffect` hook dependent on `filters` re-triggers `loadNews(updatedFilters)`.
        *   A new API call `GET /api/news/items` is made with the updated filters.
        *   The news list re-renders.
    3.  **User Enters Search Term:**
        *   User types into the Search `Input`.
        *   `onChange` triggers a debounced function (`debouncedSearch`).
        *   After debounce, `filters` state is updated with `search_term` and `page` is reset.
        *   `loadNews` is called, new API request, list re-renders.
    4.  **User Navigates Pages (Pagination):**
        *   User clicks a page number in the `Pagination` component.
        *   `onChange` handler updates `filters.page`.
        *   `loadNews` is called, new API request (with `page` parameter), list re-renders.
    5.  **Toggle Filter Visibility:**
        *   User clicks the `FilterOutlined` `FloatButton` (managed by `MainLayout`, visibility controlled by `NewsPage`'s `isFilterRowVisible` state).
        *   The filter row's visibility toggles.
*   **Key State Management Contexts Used:** None directly for filtering/display, mainly local component state in `NewsPage`. `AuthContext` for authentication.
*   **Outcome:** User can view a dynamically updated list of news items based on their selected criteria.

### 2.4. Initiating News Fetch & Monitoring Progress

*   **Goal:** Allow users to select news sources and trigger a background fetch, then monitor its progress.
*   **Trigger/Entry Point:**
    *   Clicking the "Get News" (`DownloadOutlined`) `FloatButton` in `MainLayout.tsx`.
*   **Key Pages & Components:**
    *   `pages/index.tsx` (`NewsPage` - manages modal visibility state and task drawer logic indirectly via context).
    *   `components/layout/MainLayout.tsx` (contains the FABs that trigger context actions).
    *   Ant Design components (`Modal` for fetch settings, `Drawer` for progress, `Checkbox`, `Select`, `Progress`).
*   **Sequence of Steps / User Actions:**
    1.  **Open Fetch Modal:**
        *   User clicks "Get News" FAB.
        *   `MainLayout` calls `pageActionContext.triggerShowFetchModal()`.
        *   `NewsPage` (which registered a handler with `pageActionContext.registerShowFetchModal`) sets its local state `isFetchModalVisible` to true.
        *   The "News Fetch Settings" `Modal` appears.
    2.  **Configure Fetch:**
        *   User selects a category (optional) to filter sources.
        *   User selects one or more news sources using `Checkbox.Group`.
        *   State for selected category and sources is managed locally in `NewsPage`.
    3.  **Start Fetch Tasks:**
        *   User clicks "Add to Task List" (OK button) in the modal.
        *   `NewsPage.handleFetchConfirm()` is called.
        *   *API Endpoint:* `POST /api/news/tasks/fetch/batch-group` is called with selected `source_ids`.
        *   Backend responds with `202 ACCEPTED` and a `task_group_id`.
        *   `NewsPage` initializes `tasksToMonitor` state with pending tasks for the selected sources.
        *   `isFetchModalVisible` is set to false.
        *   `isTaskDrawerVisible` is set to true (or `pageActionContext.triggerShowTaskDrawer()` is called, which `NewsPage` handles).
    4.  **Monitor Progress in Drawer:**
        *   The "Task Progress" `Drawer` opens.
        *   `NewsPage` establishes a WebSocket connection to `WS /api/tasks/ws/tasks/group/{task_group_id}?token=<jwt_token>`.
        *   As Celery tasks in the backend publish progress to Redis, the WebSocket endpoint forwards these messages.
        *   `NewsPage`'s WebSocket `onmessage` handler updates the `tasksToMonitor` state, re-rendering the progress bars and status for each source.
        *   Key WebSocket events: `source_progress`, `batch_task_completed`, `overall_batch_completed`.
    5.  **View Fetched Items:**
        *   When `overall_batch_completed` is received, `NewsPage` re-calls `loadNews()` to refresh the main news feed, which should now include newly fetched items. It also calls `fetchTodaysHistory()`.
        *   The WebSocket connection might be closed.
*   **Key State Management Contexts Used:** `PageActionContext` (to coordinate modal/drawer visibility between `MainLayout` and `NewsPage`), `AuthContext` (for the token in WebSocket URL).
*   **Outcome:** News fetching tasks are initiated in the background. User can monitor real-time progress. The news feed updates upon completion.

### 2.5. Viewing Detailed News Analysis

*   **Goal:** Allow users to view an in-depth, LLM-generated analysis of a specific news item.
*   **Trigger/Entry Point:**
    *   Clicking on a news item card in the list on `pages/index.tsx`.
    *   Clicking the "Analyze News" (`ExperimentOutlined`) icon on a news item card (which can also initiate analysis if not present).
*   **Key Pages & Components:**
    *   `pages/analyze/[id].tsx` (`AnalyzePage`) - If navigating to a dedicated page.
    *   `components/analysis/AnalysisWindowContent.tsx` - Core content display.
    *   `components/analysis/AnalysisModal.tsx` - If showing analysis in a modal (currently used when clicking card on `index.tsx`).
    *   `streaming/AnalysisStreamManager.ts` - Manages the streaming of analysis data.
*   **Sequence of Steps / User Actions (Modal Flow from News Feed):**
    1.  **User Action:** User clicks on a news item card on `pages/index.tsx`.
    2.  **Open Modal:** `NewsPage.openAnalysisModal(newsItemId)` sets state to show `AnalysisModal`.
    3.  **Modal Renders `AnalysisWindowContent`:**
        *   `AnalysisWindowContent` receives `newsItemId`.
        *   `useEffect` hook fetches full news item details via `newsService.getNewsById(newsItemId)` if not all details were passed as props (or to check for existing analysis). Sets local `fetchedNewsItem` state.
        *   It subscribes to `analysisStreamManager` for `newsItemId`.
    4.  **Analysis Streaming/Display:**
        *   **If `startAnalysisImmediately` prop is true (e.g., user clicked "Analyze" icon):**
            *   `AnalysisWindowContent` calls `analysisStreamManager.initiateStream(newsItemId, true)`.
            *   `AnalysisStreamManager` calls `newsService.streamAnalysis(newsItemId, true)` (backend API: `POST /api/news/items/{news_id}/analyze/stream`).
            *   The backend LLM generates analysis, and chunks are streamed back.
            *   `AnalysisStreamManager` receives chunks, updates its internal state, and notifies `AnalysisWindowContent` via the subscribed callback.
            *   `AnalysisWindowContent` updates its local `analysisContent` state, re-rendering to display the streamed text.
        *   **If analysis already exists on `fetchedNewsItem` and not forcing re-analysis:**
            *   `AnalysisWindowContent` displays `fetchedNewsItem.analysis`.
        *   **If no analysis exists and not forcing re-analysis immediately:**
            *   Displays an empty state or a button to "Analyze News". Clicking this button would call `handleForceAnalysis` which then uses `analysisStreamManager.initiateStream(newsItemId, true)`.
    5.  **User Closes Modal:** `NewsPage.closeAnalysisModal()` sets state to hide the modal. `AnalysisWindowContent`'s `useEffect` cleanup unsubscribes from `analysisStreamManager`.
*   **Key State Management Contexts Used:** None directly for this flow, mainly local component state and the singleton `analysisStreamManager`.
*   **Outcome:** User views the detailed analysis of a news item, potentially streamed in real-time.

### 2.6. Chatting with AI

*(This flow has two main variants: starting a new chat and continuing an existing one.)*

#### 2.6.1. Starting a New Chat
*   **Goal:** User initiates a new conversation with the AI.
*   **Trigger/Entry Point:**
    *   Being on the `/chat` page (`pages/chat.tsx`) with no chat selected.
    *   Typing a message into the `ChatInputBar` (rendered by `DefaultChatView`) and sending.
    *   Clicking the "New Chat" button in `MainLayout.tsx`.
*   **Key Pages & Components:**
    *   `pages/chat.tsx` (`ChatPageInternal`)
    *   `components/Chat/DefaultChatView.tsx`
    *   `components/Chat/ChatInputBar.tsx`
    *   `components/layout/MainLayout.tsx`
*   **Sequence of Steps / User Actions:**
    1.  **User Input:** User is on `/chat`, sees `DefaultChatView`. They type their first message into the `ChatInputBar` and click send (or press Enter).
    2.  **Handle First Message:** `ChatPageInternal.handleSendMessage()` detects `selectedChatId` is null.
        *   Sets local `isProcessingFirstMessage` to true (for loading state).
        *   Calls `chatService.createChat({ title: "First 50 chars of message..." })`.
        *   *API Endpoint:* `POST /api/chat/`.
    3.  **Backend Creates Chat:** Backend creates a new chat session, returns the new `Chat` object.
    4.  **Navigation with Initial Message:**
        *   `ChatPageInternal` receives the new chat ID.
        *   It uses `router.replace` to navigate to `/chat/{newChat.id}` and passes the `initialMessage` as a query parameter.
        *   Calls `authContext.refreshChatList()` so `MainLayout` can update its chat list.
    5.  **Individual Chat Page Loads (`pages/chat/[id].tsx`):**
        *   `ChatPage` (for `[id].tsx`) mounts.
        *   Its `useEffect` hook detects `router.query.initialMessage`.
        *   It calls `chatService.createMessage()` to save the user's initial message to the backend for the new chat ID.
        *   *API Endpoint:* `POST /api/chat/messages`.
        *   It then immediately calls `chatService.askQuestion()` with the initial message and chat ID to get the AI's first response, streaming it to the UI.
        *   *API Endpoint:* `POST /api/chat/ask` (streaming).
        *   The `initialMessage` query parameter is removed from the URL via `router.replace` (shallow).
*   **Key State Management Contexts Used:** `AuthContext` (for `refreshChatList`).
*   **Outcome:** A new chat session is created, the user's first message is sent, the AI's response is streamed, and the user is now on the page for this new chat session.

#### 2.6.2. Continuing an Existing Chat
*   **Goal:** User continues an existing conversation.
*   **Trigger/Entry Point:**
    *   Clicking an existing chat session in the `MainLayout.tsx` sidebar.
    *   Navigating directly to `/chat/{chat_id}`.
*   **Key Pages & Components:**
    *   `pages/chat/[id].tsx` (`ChatPage`)
    *   `components/Chat/ChatInputBar.tsx`
    *   `components/layout/MainLayout.tsx`
*   **Sequence of Steps / User Actions:**
    1.  **Navigation/Selection:** User navigates to or selects an existing chat. `MainLayout` updates its `selectedKey` and `router.push('/chat/{chat_id}')`.
    2.  **Load Chat & Messages:** `ChatPage` (`[id].tsx`) mounts.
        *   `useEffect` calls `loadChat(chatIdNum)`.
        *   `loadChat` calls `chatService.getChat(chatId)` and `chatService.getMessages(chatId)`.
        *   *API Endpoints:* `GET /api/chat/{chat_id}` and `GET /api/chat/{chat_id}/messages`.
        *   Component state `chat` and `messages` are updated, and messages are rendered.
    3.  **User Sends New Message:**
        *   User types into `ChatInputBar` and sends.
        *   `ChatPage.handleSendMessage()` is called.
        *   Optimistically adds user's message to the local `messages` state for immediate UI update.
        *   Calls `chatService.createMessage()` to save the user's message.
        *   *API Endpoint:* `POST /api/chat/messages`.
        *   Calls `chatService.askQuestion()` with the new message and current `chat.id`.
        *   *API Endpoint:* `POST /api/chat/ask` (streaming).
    4.  **Stream AI Response:**
        *   `ChatPage` reads the streaming response from `askQuestion`.
        *   A placeholder assistant message is added to the UI, and its content is incrementally updated as chunks arrive.
    5.  **Finalize:** After the stream ends, `loadChat(chat.id)` is called again to refresh the message list from the backend, ensuring consistency and getting final IDs/timestamps.
*   **Key State Management Contexts Used:** None directly for message sending, mainly local component state. `AuthContext` for overall authentication.
*   **Outcome:** User's message is sent, AI's response is streamed and displayed, and the conversation history is updated.

---

This `KEY_USER_FLOWS_FRONTEND.md` provides a narrative walkthrough of how users achieve their primary goals. It connects individual components and API calls into coherent sequences, which is essential for an AI to understand the dynamic aspects and context of different UI parts.