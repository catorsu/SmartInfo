# SmartInfo Frontend: Code Commenting Guide

## 1. Introduction

This guide provides the official standards and best practices for writing code comments and documentation within the SmartInfo frontend codebase (TypeScript, TSX, CSS). The primary objective is to enable AI assistants to accurately understand, utilize, and contribute to frontend modules and components. These standards also ensure clarity and maintainability for human developers.

Adherence to this guide is expected for all new and modified frontend code.

## 2. Guiding Principles

1.  **Clarity & Precision:** Use unambiguous English. Be explicit about intent, component props, state, side effects, and user interactions.
2.  **Purpose over Mechanics:** Code (especially JSX) often describes *what* the UI looks like. Comments explain *why* a component is structured a certain way, the logic behind its state, or its role in a user flow.
3.  **Component Props as Contracts:** For React components, `props` (and their TypeScript interfaces) are the primary API. Docstrings must meticulously define them.
4.  **State & Effect Transparency:** Clearly document significant component state, React Context state, and the purpose of `useEffect` hooks.
5.  **Consistency:** Follow the specified formats (JSDoc for TypeScript/TSX, CSS comment conventions) consistently.
6.  **Up-to-Date:** Comments **MUST** be kept synchronized with the code they describe.
7.  **TypeScript is Foundational:** This guide assumes comprehensive and accurate TypeScript usage (interfaces, types). Comments complement and explain types, not duplicate their definitions.

## 3. General Commenting Rules

*   **Line Length:** Comments and docstrings should ideally be wrapped at 80 characters (similar to Google Style for code, but can be slightly more flexible for prose if it aids readability). CSS comments can follow typical CSS formatting.
*   **Sentence Structure:** Comments should generally be complete sentences, capitalized, and end with a period.
*   **Language:** All comments and docstrings must be in English.

## 4. JSDoc for TypeScript/TSX Documentation

JSDoc is the standard for documenting TypeScript and TSX code. Use `/** ... */` for multi-line JSDoc blocks.

### 4.1. File-Level Comments (Top of each significant `.ts`, `.tsx` file)
*   **Purpose:** High-level summary of the file's contents and its primary role.
*   **Content:**
    *   `@file FileName.tsx` (or `.ts`)
    *   `@description One-line summary of the file's purpose.`
    *   (Optional) More detailed explanation of its role (e.g., "Entry point for the chat page," "Contains utility functions for API error handling.").
    *   **(Conceptual Tag) `@file_purpose:`** (Optional, within prose): Clearly state the primary goal (e.g., "Defines the main application layout for authenticated users.").
    *   If it's a module exporting multiple items, briefly list key exports.
*   **Example (`frontend/src/services/api.ts`):**
    ```typescript
    /**
     * @file api.ts
     * @description Axios instance setup and global interceptors for SmartInfo API communication.
     * This module configures the base URL, default headers, and request/response
     * interceptors (e.g., for adding auth tokens and handling global errors like 401).
     *
     * @file_purpose Centralized HTTP client configuration for backend API interactions.
     */
    ```

### 4.2. React Component Docstrings (JSDoc, above component definition)
*   **Purpose:** Explain the component's role in the UI, its props, significant internal state, and event handling.
*   **Key JSDoc Tags:**
    *   `@component ComponentName` (If not a default export, or for clarity)
    *   `@description Detailed explanation of the component's purpose, features, and context of use.`
    *   `@param {PropType} propName - Description of the prop. Mark as `[propName]` if optional. Include default value if any. Explain its effect on the component.
    *   `@returns {JSX.Element}`
    *   `@example Basic JSX usage: <MyComponent title="Example" items={data} />`
    *   **(Conceptual Tag, within `@description` or separate) `@state {StateType} stateVariableName - Description of significant internal state variables and their purpose.`**
    *   **(Conceptual Tag, within `@description`) `@user_flow Part of the 'User Registration', 'News Display' UI flow.`**
    *   **(Conceptual Tag, within `@description`) `@accessibility Notes on ARIA attributes used or specific accessibility considerations.`**
*   **Example (`frontend/src/components/Chat/ChatInputBar.tsx`):**
    ```typescript
    interface ChatInputBarProps {
      inputValue: string;
      onInputChange: (value: string) => void;
      onSendMessage: (message: string) => void;
      loading?: boolean;
    }

    /**
     * @component ChatInputBar
     * @description A reusable UI component for composing and sending chat messages.
     * It features a dynamically resizing text area for input and a send button.
     * Handles 'Enter' key (without Shift) for message submission.
     *
     * @param {string} inputValue - The current text content of the input area.
     * @param {(value: string) => void} onInputChange - Callback invoked when the text area content changes.
     * @param {(message: string) => void} onSendMessage - Callback invoked when the user intends to send the message.
     * @param {boolean} [loading=false] - If true, the input and send button are disabled, indicating an ongoing operation.
     *
     * @returns {JSX.Element} The rendered chat input bar.
     *
     * @user_flow Core component in the 'Chatting with AI' user flow.
     *
     * @example
     * <ChatInputBar
     *   inputValue={currentMessage}
     *   onInputChange={setCurrentMessage}
     *   onSendMessage={handleSendMessage}
     *   loading={isSending}
     * />
     */
    const ChatInputBar: React.FC<ChatInputBarProps> = ({
      inputValue,
      onInputChange,
      onSendMessage,
      loading,
    }) => {
      // ... component logic
    };
    ```

### 4.3. Function and Custom Hook Docstrings (JSDoc, in `.ts` or `.tsx` files)
*   **Purpose:** Explain the function's or hook's behavior, parameters, return value, and any side effects.
*   **Key JSDoc Tags:**
    *   `@function functionName` or `@hook useMyHookName`
    *   `@description Detailed explanation.`
    *   `@param {ParamType} paramName - Description. Mark as `[paramName]` if optional.`
    *   `@returns {ReturnType} - Description of the returned value or hook's output.`
    *   `@throws {ErrorType} - Conditions under which an error might be thrown (if not caught internally).`
    *   `@sideeffect Describe any side effects (e.g., "Makes an API call to /api/auth/login", "Modifies localStorage item 'authToken'").`
    *   `@example Basic usage snippet.`
*   **Example (`frontend/src/services/authService.ts` - `loginUser`):**
    ```typescript
    /**
     * @function loginUser
     * @description Authenticates a user by sending credentials to the backend API.
     *
     * @param {LoginCredentials} credentials - An object containing the username and password.
     * @returns {Promise<LoginResponse>} A promise that resolves with the API response
     *                                  including the access token and user details.
     * @throws {Error} Propagates errors from the API call (typically handled by `apiErrorHandler`).
     * @sideeffect Makes a POST request to the `/api/auth/token` endpoint.
     *             On success, the `AuthContext` typically stores the token.
     */
    export const loginUser = async (credentials: LoginCredentials): Promise<LoginResponse> => {
      // ...
    };
    ```

### 4.4. TypeScript Type and Interface Comments
*   **Purpose:** Explain the structure and purpose of custom types and interfaces.
*   **Format:** Use JSDoc `/** ... */` above the `type` or `interface` definition.
*   **Content:**
    *   `@interface InterfaceName` or `@typedef {object} TypeName` (JSDoc standard for type alias)
    *   `@description What this type/interface represents.`
    *   For each property: `propertyName: type; // Brief description of the property's meaning.` Inline comments are often sufficient for properties if the JSDoc for the interface/type itself is clear.
    *   If a property itself is a complex type, it should also be documented or link to its definition.
*   **Example (`frontend/src/utils/types.ts` - `NewsItem`):**
    ```typescript
    /**
     * @interface NewsItem
     * @description Defines the structure for a single news article object
     * used throughout the frontend, typically fetched from the backend.
     */
    export interface NewsItem {
      id: number;                      // Unique DB identifier
      title: string;                   // Main title of the article
      url?: AnyHttpUrl;                // URL to the original article source
      source_name?: string;            // Name of the news source
      category_name?: string;          // Name of the category it belongs to
      summary?: string;                // A brief summary of the news item
      analysis?: string;               // LLM-generated analysis of the content
      date?: string;                   // Publication date (string format, e.g., ISO)
      top_image?: AnyHttpUrl;          // URL for the article's main image
      created_at?: string;             // Timestamp when the item was saved in SmartInfo
      // Add other fields as necessary
    }
    ```

### 4.5. State Management Contexts (e.g., `frontend/src/context/AuthContext.tsx`)
*   **File-Level Comment:** Overall purpose of the context.
*   **Context Type Interface Docstring (e.g., `AuthContextType`):**
    *   `@interface AuthContextType`
    *   `@description Defines the shape of the authentication context, including state
        variables and action functions provided to consuming components.`
    *   For each property/method: `@property {Type} propertyName - Description.` (e.g., `isAuthenticated (boolean): True if the user is currently authenticated.`)
*   **Provider Component Docstring (e.g., `AuthProvider`):** Explain its role in initializing and providing the context value, and what children it expects.
*   **Custom Hook Docstring (e.g., `useAuth`):** Explain its purpose (to consume the context) and what it returns.

### 4.6. CSS / Styling Comments (`.css`, `.module.css`)
*   **File-Level Comment (Optional, for complex stylesheets):**
    ```css
    /*
     * @file MainLayout.module.css
     * @description Styles for the main application layout, including sidebar
     * and content area structure. Uses CSS Modules.
     */
    ```
*   **Section Comments:** Group related style rules.
    ```css
    /* --- Sidebar Navigation --- */
    .appSider { /* ... */ }
    .siderChatMenu { /* ... */ }

    /* --- Chat Message Bubbles --- */
    .userMessageCard { /* ... */ }
    ```
*   **Complex Rules/Hacks:** Explain non-obvious selectors, CSS properties used for specific effects, or any browser compatibility workarounds.
    ```css
    .gradientLogoText {
        /* Fallback for older browsers if needed, though modern ones support gradient text */
        color: var(--accent-color);
        background: linear-gradient(to right, #4285F4, #9B72CB, #D96570, #F2A600);
        -webkit-background-clip: text; /* Vendor prefix for Safari/Chrome */
        -webkit-text-fill-color: transparent; /* Makes text transparent to show gradient */
        background-clip: text;
        color: transparent; /* Standard property */
    }
    ```

### 4.7. Inline Comments (in `.tsx`, `.ts`)
*   Use `//` for single-line or `/* ... */` for multi-line inline comments.
*   **Purpose:**
    *   Explain complex conditional rendering logic in JSX.
    *   Clarify the purpose of `useEffect` dependencies or cleanup functions if not obvious.
    *   Explain intricate state update logic in reducers or event handlers.
    *   Workarounds or non-standard solutions.
    *   `// TODO(username/issue_link): Description of pending work.`
    *   `// FIXME(username/issue_link): Description of bug and impact.`
    *   `// AI_ASSUMPTION: Code relies on this non-obvious assumption.`
    *   `// AI_WARNING: Caution for AI when refactoring this block.`
*   **Example (within a React component):**
    ```tsx
    useEffect(() => {
      // AI_ASSUMPTION: Assumes `chatId` from router query is stable and
      // a valid number string once router.isReady is true.
      if (router.isReady && id) {
        const chatIdNum = parseInt(id as string);
        // Further logic...
      }
    }, [id, router.isReady]); // Dependencies clearly listed
    ```

## 5. Maintenance

*   **Comments as Code:** Treat comments and docstrings as integral parts of the frontend codebase.
*   **Review Process:** Code reviews **MUST** include a review of associated comments and JSDoc for clarity, accuracy, and completeness according to this guide.
*   **Updates:** When component props, state logic, function signatures, or UI behavior changes, the corresponding comments and docstrings **MUST** be updated in the same commit/PR.

By adhering to this Frontend Code Commenting Guide, we will build a SmartInfo frontend that is understandable, maintainable, and well-suited for efficient collaboration with AI development assistants.
