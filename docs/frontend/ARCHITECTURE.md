# SmartInfo Frontend: Architecture Guide

## 1. Introduction

### 1.1. Purpose
This document provides a high-level overview of the SmartInfo frontend architecture. It describes the core technologies, key structural components, their responsibilities, and how they interact to deliver the user interface and experience.

### 1.2. Guiding Principles
*   **Component-Based:** Built using React, emphasizing reusable and encapsulated UI components.
*   **Modularity:** Code is organized into logical directories based on functionality (pages, components, services, context).
*   **Type Safety:** TypeScript is used throughout the project for improved code quality and developer experience.
*   **Separation of Concerns:** UI rendering, state management, API interaction, and utility functions are kept as distinct as possible.
*   **User Experience:** Aims to provide a responsive, intuitive, and informative interface for users.

## 2. Core Technologies & Frameworks

*   **Next.js (v13+):**
    *   **Role:** The primary React framework. Used for server-side rendering (SSR) or static site generation (SSG) capabilities (though SmartInfo primarily uses client-side rendering after initial page load), file-system based routing, API routes (if needed, though backend is separate), and overall project structure.
*   **React (v18+):**
    *   **Role:** The core UI library for building user interfaces with a component-based architecture. Utilizes hooks for state and lifecycle management.
*   **TypeScript:**
    *   **Role:** Provides static typing for JavaScript, enhancing code quality, maintainability, and developer productivity. All `.ts` and `.tsx` files leverage TypeScript.
*   **Ant Design (`antd`):**
    *   **Role:** The primary UI component library, providing a wide range of pre-built, customizable React components (buttons, forms, modals, layout elements, etc.) to accelerate development and ensure a consistent look and feel. See `COMPONENT_LIBRARY_GUIDE.md` for more on custom vs. AntD usage.
*   **Axios:**
    *   **Role:** HTTP client used for making requests to the SmartInfo backend API. A configured instance is available in `services/api.ts`. See `API_INTERACTION_PATTERNS.md`.
*   **React Context API:**
    *   **Role:** Used for managing global or widely shared state that doesn't fit well into local component state (e.g., authentication status, page action triggers). See `STATE_MANAGEMENT.md`.
*   **CSS Modules & Global CSS:**
    *   **Role:** CSS Modules (`*.module.css`) are used for component-scoped styling. `styles/globals.css` is used for application-wide base styles and Ant Design overrides.

## 3. High-Level Architectural Diagram

```mermaid
graph TD
    A[User's Browser] --> B{Next.js / React App};

    subgraph B
        direction LR
        C[Pages (`pages/`)] --> D[Reusable Components (`components/`)];
        C --> E[Layout Component (`MainLayout.tsx`)];
        D --> E;
        D --> F[UI Logic & Local State];
        E --> G[Global UI Elements (e.g., Modals, FABs)];
        C --> H{React Context API (`context/`)};
        D --> H;
        E --> H;
        H --> I[Global State (Auth, Page Actions)];
        C --> J[API Services (`services/`)];
        D --> J;
        J -- Axios --> K((SmartInfo Backend API));
        L[Streaming Managers (e.g., AnalysisStreamManager)] --> K;
        C --> L;
        M[Utility Functions (`utils/`)] --> C;
        M --> D;
        M --> J;
        N[Styling (CSS Modules, globals.css)] -.-> C;
        N -.-> D;
        N -.-> E;
    end

    K <--> O[(Backend Database)];
```

**Key:**
*   `{}` - Logical Grouping / Framework
*   `[]` - Directory / Component Type
*   `(())` - External Service (Backend API)
*   Arrows indicate primary flow of data or control.

## 4. Key Structural Components & Layers

### 4.1. Pages (`frontend/src/pages/`)
*   **Responsibility:** Define the application's routes and serve as the top-level containers for views. Each file in this directory (excluding those starting with `_`) typically maps to a URL path (e.g., `pages/chat.tsx` -> `/chat`).
*   **Implementation:** Next.js file-system based routing. Dynamic routes like `pages/chat/[id].tsx` handle parameterized URLs.
*   **Content:** Pages usually orchestrate multiple reusable and specialized components to build a complete view. They are often responsible for initial data fetching for the view and passing data down to child components. Many pages are wrapped with the `withAuth` HOC for authentication.

### 4.2. Reusable Components (`frontend/src/components/`)
*   **Responsibility:** Encapsulated UI building blocks designed for reuse across different pages and other components.
*   **Structure:** Organized into subdirectories based on functionality (e.g., `components/Chat/`, `components/analysis/`, `components/layout/`).
*   **Examples:** `ChatInputBar.tsx`, `DefaultChatView.tsx`, `AnalysisWindowContent.tsx`.
*   **Documentation:** Refer to `COMPONENT_LIBRARY_GUIDE.md` for an overview and guidelines. Individual components have JSDoc comments.

### 4.3. Layout Component (`frontend/src/components/layout/MainLayout.tsx`)
*   **Responsibility:** Provides the consistent shell for all authenticated views of the application. This includes the sidebar for navigation, main content area, and potentially global elements like a header or footer. The main content area is designed to allow the browser's native scrollbar to manage page overflow, enabling child elements (like sticky headers within pages) to position themselves relative to the viewport.
*   **Key Features:**
    *   Integrates `AuthContext` for user-related information and logout functionality.
    *   Manages the display of global modals (e.g., Settings) and drawers (e.g., Task Progress) often triggered via `PageActionContext`.
    *   Handles sidebar chat list display and "New Chat" functionality.
    *   Contains global Floating Action Buttons (FABs).

### 4.4. State Management (`frontend/src/context/`)
*   **Responsibility:** Manages global or widely shared state that is inconvenient to pass down through props.
*   **Current Implementation:** Primarily uses React Context API.
    *   **`AuthContext.tsx`:** Manages user authentication state (token, user object, loading status) and authentication actions (login, logout, signup).
    *   **`PageActionContext.tsx`:** Facilitates communication between pages/components and `MainLayout` to trigger global UI actions (e.g., opening modals/drawers managed by the layout).
*   **Documentation:** Refer to `STATE_MANAGEMENT.md` for detailed explanations and usage guidelines.

### 4.5. API Services (`frontend/src/services/`)
*   **Responsibility:** Abstract all communication with the SmartInfo backend API. Components and pages should not make direct Axios calls.
*   **Structure:**
    *   `api.ts`: Configured Axios instance with interceptors for auth tokens and global error handling.
    *   Service files (e.g., `authService.ts`, `newsService.ts`): Group related API call functions. Each function typically corresponds to a backend endpoint and returns a Promise with the response data.
*   **Documentation:** Refer to `API_INTERACTION_PATTERNS.md` for how to use these services and handle responses.

### 4.6. Styling (`frontend/src/styles/`)
*   **`globals.css`:** Contains application-wide base styles, CSS custom properties (theme variables), and global overrides for Ant Design components.
*   **CSS Modules (`*.module.css`):** Used for component-scoped styling to prevent class name collisions and promote modularity. Each component typically has its own `.module.css` file.
*   **Ant Design:** Leveraged for base styling and components. Customizations are applied via `globals.css` or within component styles.

### 4.7. Utilities (`frontend/src/utils/`)
*   **Responsibility:** Contains helper functions, type definitions (`types.ts`), and utility modules that are used across various parts of the frontend.
*   **Examples:** `apiErrorHandler.ts`, `types.ts`.

### 4.8. Streaming Logic (`frontend/src/streaming/AnalysisStreamManager.ts`)
*   **Responsibility:** Provides a dedicated manager for handling real-time streaming of data from the backend, specifically for news analysis content.
*   **Mechanism:** Encapsulates `ReadableStreamDefaultReader` logic, accumulates content, and notifies subscribed React components of updates.

## 5. Data Flow Patterns

*   **Page Load & Initial Data:**
    1.  A Next.js page component mounts.
    2.  `useEffect` hook often triggers a data fetch function.
    3.  This function calls a relevant API service function from `services/*.ts`.
    4.  The service function uses the `api.ts` Axios instance to make a backend request.
    5.  Loading state is set in the page/component.
    6.  Upon response, data state is updated, loading state is cleared, and the UI re-renders. Errors are caught and error state is set.
*   **User Actions & Mutations:**
    1.  User interacts with a UI element (e.g., clicks a button, submits a form).
    2.  An event handler is triggered.
    3.  The handler may call an API service function to send data to the backend (e.g., creating a new chat, updating settings).
    4.  Loading state is managed.
    5.  On success, UI state might be updated, `localStorage` might be modified (e.g., auth token), or navigation might occur. Ant Design `message` component is often used for feedback.
    6.  Errors are caught and displayed.
*   **Global State Access:**
    *   Components that need authentication status or user information call `useAuth()` from `AuthContext`.
    *   Components or pages needing to trigger global actions (like showing a modal managed by `MainLayout`) call trigger functions from `usePageActions()` provided by `PageActionContext`.

## 6. Routing

*   **Next.js File-System Routing:** The primary routing mechanism. Files in the `pages` directory automatically become routes.
    *   `pages/index.tsx` -> `/`
    *   `pages/chat.tsx` -> `/chat`
    *   `pages/login.tsx` -> `/login`
*   **Dynamic Routes:** Used for pages that depend on parameters, e.g., `pages/chat/[id].tsx` maps to `/chat/some-chat-id`. The `id` is accessible via `useRouter().query`.
*   **Programmatic Navigation:** `useRouter().push('/new-path')` or `useRouter().replace('/new-path')` is used for navigation within component logic.
*   **Authentication Guarding:** The `withAuth` HOC (`components/auth/withAuth.tsx`) wraps protected pages and redirects unauthenticated users to `/login`.

## 7. Build & Deployment (Brief Overview)

*   **Build:** `npm run build` or `yarn build` creates an optimized production build of the Next.js application in the `.next/` directory.
*   **Deployment:** The output from the build can be deployed to various platforms that support Next.js applications (e.g., Vercel, AWS Amplify, Docker containers on any cloud provider).
*   **Environment Variables:** `NEXT_PUBLIC_API_URL` is crucial for connecting to the correct backend API instance in different environments.

This architecture aims to provide a scalable and maintainable foundation for the SmartInfo frontend. As the application grows, specific areas like state management or data fetching might evolve with the introduction of more specialized libraries if deemed necessary.
