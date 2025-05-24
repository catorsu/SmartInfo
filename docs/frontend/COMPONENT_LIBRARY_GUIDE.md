# SmartInfo Frontend: Component Library Guide

## 1. Introduction

### 1.1. Purpose
This guide provides an overview of the custom reusable React components developed for the SmartInfo frontend. It aims to promote consistency in user interface design, encourage code reuse, and provide clear guidelines for both using existing components and creating new ones.

### 1.2. Philosophy
*   **Reusability (DRY):** Create reusable components for UI patterns or elements that appear in multiple places.
*   **Encapsulation:** Components should encapsulate their own logic and styling where possible.
*   **Clarity:** Props should be clear, and component behavior should be predictable.
*   **Accessibility:** Strive to make components accessible.
*   **Leverage Base Library:** Build upon Ant Design components where appropriate.

## 2. Core UI Library: Ant Design

SmartInfo heavily utilizes **Ant Design (`antd`)** as its foundational UI component library. Developers should familiarize themselves with Ant Design's components and documentation: [https://ant.design/components/overview/](https://ant.design/components/overview/)

*   **Guideline:** Before creating a new custom component, always check if a suitable Ant Design component (or a combination thereof) can fulfill the requirement.
*   **Wrapping AntD Components:** Custom components may wrap Ant Design components to:
    *   Apply project-specific styling consistently.
    *   Set common default props for SmartInfo's use cases.
    *   Encapsulate specific interaction logic related to an AntD component.

## 3. Custom Reusable Component Overview

This section highlights key custom reusable components found in `frontend/src/components/`. For detailed prop information and specific implementation, always refer to the JSDoc comments within the respective `.tsx` files, following the `FRONTEND_CODE_COMMENTING_GUIDE.md`.

### 3.1. Layout Components

Located in `frontend/src/components/layout/`.

*   **`MainLayout.tsx`**
    *   **Purpose:** Provides the primary authenticated application layout, including the sidebar for navigation (News Feed, Chat History), the main content area, and global UI elements like the settings modal trigger and action FloatButtons. The main content area allows the browser's native scrollbar to handle page overflow, ensuring that elements within pages (such as sticky filter bars) behave as expected relative to the viewport.
    *   **Key Features:**
        *   Integrates with `AuthContext` to manage user authentication state and display user information.
        *   Integrates with `PageActionContext` to allow child pages/components to trigger modals/drawers managed by the layout (e.g., Fetch News Modal, Task Progress Drawer).
        *   Handles responsive collapsing of the sidebar.
        *   Displays a list of user chats and allows creation of new chats.
    *   **Usage:** Wraps all authenticated pages in `frontend/src/pages/_app.tsx`.

### 3.2. Chat Components

Located in `frontend/src/components/Chat/`.

*   **`ChatInputBar.tsx`**
    *   **Purpose:** A reusable input bar for composing and sending chat messages. Features a dynamically resizing text area and a send button.
    *   **Key Props:** `inputValue`, `onInputChange`, `onSendMessage`, `loading`.
    *   **Usage:** Used on the main chat page (`pages/chat.tsx` via `DefaultChatView`) and individual chat session pages (`pages/chat/[id].tsx`).
    *   **Example:**
        ```tsx
        <ChatInputBar
          inputValue={message}
          onInputChange={setMessage}
          onSendMessage={handleSend}
          loading={isSending}
        />
        ```

*   **`DefaultChatView.tsx`**
    *   **Purpose:** The view displayed on the main chat page (`/chat`) when no specific chat session is selected. It provides a greeting, suggestion prompts, and integrates `ChatInputBar`.
    *   **Key Props:** `username`, `onSuggestionClick`, `inputValue`, `onInputChange`, `onSendMessage`, `loading`.
    *   **Usage:** Primarily on `frontend/src/pages/chat.tsx`.

### 3.3. Analysis Components

Located in `frontend/src/components/analysis/`.

*   **`AnalysisWindowContent.tsx`**
    *   **Purpose:** Displays the detailed analysis of a news item. It handles fetching news item details if not fully provided, manages the streaming of LLM-generated analysis via `AnalysisStreamManager`, and displays existing or streamed analysis content.
    *   **Key Props:** `newsItemId`, `startAnalysisImmediately` (optional props for initial data like `newsItemTitle` can also be passed).
    *   **Usage:** Used directly by the `pages/analyze/[id].tsx` page and potentially within `AnalysisModal.tsx`.
    *   **Key Feature:** Integrates with `AnalysisStreamManager.ts` for real-time streaming of analysis.

*   **`AnalysisModal.tsx`**
    *   **Purpose:** A modal component that wraps `AnalysisWindowContent.tsx` to display news analysis in a pop-up window.
    *   **Key Props:** `newsItemId`, `isOpen`, `onClose`.
    *   **Usage:** Can be invoked from various parts of the application where a user requests to see an analysis (e.g., from the news feed page - `pages/index.tsx`).

### 3.4. Settings Components

Located in `frontend/src/components/settings/`.

*   **`SettingsContent.tsx`**
    *   **Purpose:** Provides the UI for managing all user-specific settings, including general application preferences, API key management, news source/category management, and account settings (password/username change).
    *   **Key Features:** Tabbed interface for different setting categories. Forms for creating/editing API keys, sources. Tables for displaying lists of configurations.
    *   **Usage:** Typically displayed within a modal triggered from `MainLayout.tsx`.

### 3.5. Authentication HOC

Located in `frontend/src/components/auth/`.

*   **`withAuth.tsx`**
    *   **Purpose:** A Higher-Order Component (HOC) that wraps pages or components requiring user authentication.
    *   **Behavior:** If the user is not authenticated (checked via `AuthContext`), it redirects them to the login page. While checking authentication status, it can display a loading indicator.
    *   **Usage:** Wraps page components in `frontend/src/pages/` that require login (e.g., `chat.tsx`, `index.tsx`).
    *   **Example:** `export default withAuth(ChatPage);`

## 4. Guidelines for Creating New Reusable Components

When developing new UI elements, consider if they can be made into reusable components.

1.  **Identify Reusability:**
    *   Is this UI element or pattern used in more than one place?
    *   Is it likely to be used in the future with minor variations?
    *   Does it encapsulate a distinct piece of UI and logic?
2.  **Props Design:**
    *   Design props to be clear, explicit, and well-typed (using TypeScript interfaces).
    *   Provide sensible default values for optional props.
    *   Avoid overly complex prop objects if simpler, individual props suffice.
    *   Clearly document all props using JSDoc as per the `FRONTEND_CODE_COMMENTING_GUIDE.md`.
3.  **State Management:**
    *   Prefer local component state (`useState`, `useReducer`) for state that is not needed outside the component.
    *   For state that needs to be shared across multiple components, use React Context (like `AuthContext` or `PageActionContext`) or consider other project-approved state management solutions if contexts become unwieldy.
    *   Design components to be "controlled" by props where appropriate, allowing parent components to manage their state.
4.  **Styling:**
    *   **CSS Modules (`*.module.css`):** Preferred for component-specific styles to ensure encapsulation and avoid style conflicts. Import styles as `import styles from './MyComponent.module.css';`.
    *   **Global Styles (`globals.css`):** Use for application-wide base styles, theme variables (CSS custom properties), and Ant Design overrides.
    *   **Ant Design Components:** Utilize AntD's styling capabilities and theme provider. Wrap and re-style AntD components carefully and consistently.
5.  **Accessibility (a11y):**
    *   Use semantic HTML elements where appropriate.
    *   Ensure keyboard navigability.
    *   Add ARIA attributes if needed to enhance accessibility for assistive technologies.
    *   Test with accessibility tools if possible.
6.  **Documentation:**
    *   **ALL** new reusable components **MUST** have comprehensive JSDoc comments as outlined in the `FRONTEND_CODE_COMMENTING_GUIDE.md`. This includes a description, all props, return value, and examples.
7.  **Directory Structure:**
    *   Place genuinely reusable components in appropriate subdirectories within `frontend/src/components/` (e.g., `components/common/`, `components/forms/` if such categories emerge).
    *   Components that are highly specific to a single page or a very narrow feature might reside closer to that feature's code, or within `components/` but clearly named to indicate their specific use.

## 5. Using This Guide

*   **Discoverability:** Before building a new UI element, check this guide and `frontend/src/components/` to see if a suitable reusable component already exists.
*   **Correct Usage:** Refer to the JSDoc and examples for existing components to understand how to use them correctly.
*   **Contribution:** When creating new reusable components, adhere to the guidelines above to ensure they integrate well into the SmartInfo component ecosystem.

By fostering a library of well-documented, reusable components, we can accelerate frontend development, improve UI consistency, and make it easier for both human developers and AI assistants to build and maintain SmartInfo's user interface.