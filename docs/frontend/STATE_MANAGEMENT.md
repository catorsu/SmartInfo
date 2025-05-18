# SmartInfo Frontend: State Management Guide

## 1. Introduction

### 1.1. Purpose
This document outlines the state management strategy for the SmartInfo frontend application. It details how local component state is handled, how global or widely shared state is managed using React Context, and provides guidelines for future state management decisions.

### 1.2. Philosophy
SmartInfo's frontend state management philosophy emphasizes:
*   **Simplicity:** Prefer the simplest solution that meets the need.
*   **Colocation:** Keep state as close as possible to where it's used. Start with local component state.
*   **Explicitness:** Make data flow and state dependencies clear.
*   **Performance:** Be mindful of unnecessary re-renders caused by broad context changes.
*   **Leverage React Features:** Utilize built-in React hooks (`useState`, `useReducer`, `useContext`) as the primary tools.

## 2. Local Component State

*   **Primary Tools:** `useState` and `useReducer` (for more complex state logic within a component).
*   **Guideline:** For state that is only relevant to a single component or a small tree of closely related child components, use local state.
*   **Lifting State Up:** If multiple sibling components need access to the same state, lift the state up to their closest common ancestor component and pass it down via props.
*   **When to Avoid Local State for Shared Data:** If state needs to be accessed by components far apart in the tree, or by many unrelated components, prop drilling becomes cumbersome and React Context (or another global state solution) is more appropriate.

## 3. Global / Shared State: React Context API

For state that needs to be accessible across many components at different levels of the component tree, SmartInfo primarily uses the React Context API.

### 3.1. General Principles for Using Context
*   **Granularity:** Create focused contexts for specific concerns (e.g., authentication, page-level actions) rather than a single monolithic context. This helps minimize unnecessary re-renders for components that only care about a subset of the global state.
*   **Provider Placement:** Context Providers are typically placed high in the component tree, often in `frontend/src/pages/_app.tsx`, to wrap the parts of the application that need access to that context.
*   **Custom Hooks for Consumption:** Each context should provide a custom hook (e.g., `useAuth()`) to make consuming its state and actions easier and more idiomatic. This hook also typically includes a check to ensure it's used within the Provider.
*   **Memoization:** Use `useMemo` and `useCallback` within context providers where appropriate to prevent unnecessary re-renders of consuming components, especially if the context value is an object or function.

### 3.2. Existing Contexts

#### 3.2.1. `AuthContext`
*   **File Location:** `frontend/src/context/AuthContext.tsx`
*   **Purpose:** Manages global authentication state, user information, and provides authentication-related actions (login, logout, signup).
*   **Provided State & Actions (`AuthContextType`):**
    *   `isAuthenticated (boolean)`: True if the user is currently authenticated, false otherwise.
    *   `user (User | null)`: The authenticated user object (from `authService.User`) or null if not authenticated. Contains `id` and `username`.
    *   `token (string | null)`: The JWT access token, or null.
    *   `loading (boolean)`: True while the initial authentication status is being validated (e.g., checking `localStorage` for a token on app load).
    *   `login(username, password) (Promise<void>)`: Function to log in the user. Handles API calls, updates state, and manages token storage in `localStorage`.
    *   `logout() (Promise<void>)`: Function to log out the user. Clears state, removes the token from `localStorage`, and redirects to the login page.
    *   `signup(username, password) (Promise<void>)`: Function to register a new user. Handles API calls, updates state, and manages token storage.
    *   `refreshChatList() (() => void)`: A function that, when called, triggers a callback to refresh the chat list (typically in `MainLayout.tsx`).
    *   `setRefreshChatListCallback((callback: (() => void) | null) => void)`: Used by `MainLayout` to register the actual chat list refresh function.
    *   `updateUserProfile(updatedUser: User) (() => void)`: Function to update the local user profile state (e.g., after a username change).
*   **How to Consume:**
    ```typescript
    import { useAuth } from '@/context/AuthContext';
    // ...
    const { isAuthenticated, user, login, loading } = useAuth();
    if (loading) return <Spin />;
    if (!isAuthenticated) // redirect or show login
    // ...
    ```
*   **Provider Location:** `<AuthProvider>` wraps the entire application in `frontend/src/pages/_app.tsx`.

#### 3.2.2. `PageActionContext`
*   **File Location:** `frontend/src/context/PageActionContext.tsx`
*   **Purpose:** Facilitates communication between deeply nested child components/pages and the `MainLayout.tsx` component to trigger global UI actions like showing modals or drawers that are managed at the layout level. This avoids excessive prop drilling for action triggers.
*   **Provided State & Actions (`PageActionContextType`):**
    *   `registerShowFetchModal(handler: (() => void) | null) (() => void)`: Called by `MainLayout` to register the function that shows the "Fetch News" modal.
    *   `triggerShowFetchModal() (() => void)`: Called by child components (e.g., a button on the News page via a FAB in `MainLayout`) to request the "Fetch News" modal to be shown.
    *   `registerShowTaskDrawer(handler: (() => void) | null) (() => void)`: Called by `MainLayout` to register the function that shows the "Task Progress" drawer.
    *   `triggerShowTaskDrawer() (() => void)`: Called by child components to request the "Task Progress" drawer to be shown.
*   **How to Consume:**
    *   **Registering an action (in `MainLayout.tsx` or similar):**
        ```typescript
        import { usePageActions } from '@/context/PageActionContext';
        // ...
        const { registerShowFetchModal } = usePageActions();
        useEffect(() => {
          registerShowFetchModal(() => setIsFetchModalVisible(true)); // setIsFetchModalVisible is local state in MainLayout
          return () => registerShowFetchModal(null); // Cleanup
        }, [registerShowFetchModal, /* local modal visibility setter */]);
        ```
    *   **Triggering an action (in a child component/page, often via a FAB in `MainLayout`):**
        ```typescript
        import { usePageActions } from '@/context/PageActionContext';
        // ...
        const { triggerShowFetchModal } = usePageActions();
        // ...
        // <Button onClick={triggerShowFetchModal}>Fetch News</Button>
        // (In SmartInfo, FABs in MainLayout call these triggers)
        ```
*   **Provider Location:** `<PageActionProvider>` wraps the application content within `MainLayout` in `frontend/src/pages/_app.tsx`.

## 4. Data Fetching and Server Cache State

*   **Current Approach:**
    *   Data fetching is primarily handled by service functions in `frontend/src/services/` (e.g., `newsService.ts`, `chatService.ts`) which use an Axios instance (`api.ts`).
    *   Individual pages or components are responsible for calling these service functions, then managing their own local state for loading, error, and the fetched data (e.g., using `useState` for `newsItems`, `isLoadingNews`, `newsError`).
    *   Examples can be seen in `frontend/src/pages/index.tsx` (News page) and `frontend/src/pages/chat/[id].tsx` (Chat session page).
*   **`AnalysisStreamManager.ts` (`frontend/src/streaming/`):**
    *   This is a specialized client-side manager for handling streaming data, specifically for news analysis. It manages the lifecycle of a `ReadableStreamDefaultReader`, accumulates content, and notifies subscribers (React components) of updates. This is a form of client-side caching/management for a specific type of server data stream.
*   **Considerations for API State:**
    *   **Caching:** Currently, there's no built-in client-side caching layer for API responses beyond what the browser might do or what `AnalysisStreamManager` does for its specific stream. Each data fetch typically re-fetches from the server.
    *   **Synchronization:** Keeping data fresh or synchronized across different components that might display the same data requires manual re-fetching or prop drilling.
    *   **Optimistic Updates:** Not currently implemented systematically.

*   **Future Enhancements (If Needed):**
    *   If client-side caching, automatic re-fetching, request deduplication, and optimistic updates for API data become critical needs as the application scales, consider dedicated server state management libraries like:
        *   **React Query (TanStack Query)**
        *   **SWR**
    *   These libraries provide hooks and mechanisms to simplify managing server cache state, reducing boilerplate for loading/error/data states and improving UX.

## 5. Guidelines for Adding New Shared State

1.  **Prefer Local State:** Always start by considering if the state can be managed locally within a component or lifted to a nearby common ancestor.
2.  **When to Use Existing Contexts:**
    *   If the new state is directly related to authentication or user profile, extend `AuthContext` (carefully, to avoid making it too broad).
    *   If it's a global UI action triggerable from anywhere and managed by `MainLayout`, consider if `PageActionContext` is appropriate or if a new, more specific action context is needed.
3.  **When to Create a New Context:**
    *   If the state is shared across a significant portion of the application but is not universally global like authentication (e.g., "Current Theme Context," "User Preferences Display Context" if these preferences are widely used directly in UI).
    *   Ensure the new context has a clear, focused responsibility.
    *   Provide a custom hook for consuming the new context.
    *   Place the provider appropriately in the component tree.
4.  **Performance:**
    *   Be mindful of context value stability. If the context value is an object or function that changes on every render of the provider, all consumers will re-render. Use `useMemo` for context values and `useCallback` for functions provided via context where necessary.
    *   Split contexts if different parts of the state update at different frequencies and are consumed by different sets_of components.

By following these guidelines, SmartInfo's frontend state can be managed in a predictable, maintainable, and performant way, facilitating easier development and collaboration for both human and AI developers.
