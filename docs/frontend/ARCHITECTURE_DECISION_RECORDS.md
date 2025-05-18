# SmartInfo Frontend: Architecture Decision Records (ADRs)

## 1. Introduction

This document records significant architectural and technological decisions made for the SmartInfo frontend. Each record outlines the context of the decision, the decision itself, and the rationale behind it. These ADRs serve as a historical log and a guide for future development, ensuring that the reasoning behind key choices is understood and can be built upon by both human developers and AI assistants.

---

## ADR-FE-001: Choice of Next.js as the React Framework

*   **Status:** Accepted
*   **Context:**
    *   The SmartInfo frontend requires a robust, modern framework for building a React-based single-page application (SPA) or a hybrid application.
    *   Features like routing, potential for server-side rendering (SSR) or static site generation (SSG) for landing pages (though primary app is client-side rendered after login), optimized builds, and a good developer experience were considered important.
*   **Decision:**
    *   Next.js was chosen as the primary framework for the React frontend.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **File-System Routing:** Simple and intuitive routing mechanism.
        *   **Rendering Options:** Provides flexibility for SSR, SSG, and CSR (Client-Side Rendering), allowing optimization for different parts of the application (e.g., SEO for public pages, dynamic rendering for authenticated app). SmartInfo currently leans heavily on CSR post-authentication.
        *   **Developer Experience:** Rich feature set, active community, good TypeScript support, built-in optimizations (image optimization, code splitting).
        *   **Ecosystem:** Well-integrated with tools like Vercel for deployment.
        *   **API Routes (Optional):** Ability to create backend-for-frontend (BFF) API routes within the Next.js app if needed, though SmartInfo has a separate FastAPI backend.
    *   **Alternatives Considered:**
        *   **Create React App (CRA):** Simpler for basic SPAs, but lacks built-in routing, SSR/SSG, and other advanced features without significant manual configuration or ejecting.
        *   **Remix:** Another strong contender with a focus on web standards, but Next.js had a larger ecosystem and more established patterns at the time of decision for a broader range of use cases.
        *   **Vite + React:** Excellent build speed and developer experience, but requires more manual setup for routing and SSR/SSG compared to Next.js's integrated solution.
    *   **Trade-offs:** Next.js can have a slightly steeper learning curve than CRA for simple projects due to its breadth of features. Some build configurations can be complex.

---

## ADR-FE-002: Adoption of TypeScript for Frontend Development

*   **Status:** Accepted
*   **Context:**
    *   A need for improved code quality, maintainability, and early error detection in a growing JavaScript-based frontend.
    *   Better tooling support (autocompletion, refactoring) was desired.
*   **Decision:**
    *   TypeScript was adopted as the primary language for all new frontend development.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **Static Typing:** Catches many common errors at compile-time rather than runtime.
        *   **Improved Readability & Maintainability:** Types make code easier to understand and refactor with confidence. Interfaces act as contracts.
        *   **Enhanced Developer Experience:** Better autocompletion, type checking in IDEs.
        *   **Scalability:** Makes it easier to manage larger codebases and teams.
        *   **Ecosystem:** Strong support in React, Next.js, and major UI libraries like Ant Design.
    *   **Alternatives Considered:**
        *   **Plain JavaScript (with JSDoc for types):** Less robust type checking, relies heavily on discipline and tooling for JSDoc parsing.
        *   **Flow:** Another static type checker for JavaScript, but TypeScript has gained significantly more community adoption and tooling support.
    *   **Trade-offs:**
        *   Initial learning curve for developers new to TypeScript.
        *   Requires a compilation step.
        *   Sometimes requires more verbose type definitions, though often inferred.

---

## ADR-FE-003: UI Component Library - Ant Design

*   **Status:** Accepted
*   **Context:**
    *   The need for a comprehensive set of pre-built, high-quality UI components to accelerate development and ensure a consistent, professional look and feel for the SmartInfo application.
*   **Decision:**
    *   Ant Design (`antd`) was chosen as the primary UI component library.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **Rich Component Set:** Offers a wide variety of components covering most common UI needs (forms, tables, modals, navigation, data display, etc.).
        *   **Theming & Customization:** Provides good support for theming (used in `_app.tsx` via `ConfigProvider`) and individual component styling.
        *   **Accessibility:** Generally good accessibility baked into components.
        *   **Enterprise-Ready:** Mature, well-documented, and widely used in enterprise applications.
        *   **TypeScript Support:** Excellent TypeScript definitions.
    *   **Alternatives Considered:**
        *   **Material-UI (MUI):** Another popular and comprehensive React component library. Ant Design was chosen based on perceived aesthetic fit or team familiarity at the time.
        *   **Chakra UI, Mantine, etc.:** Newer libraries with strong focus on developer experience and accessibility. Ant Design offered a more extensive set of mature components needed for a data-intensive application like SmartInfo.
        *   **Building from Scratch / Minimalist Libraries (e.g., Tailwind CSS + Headless UI):** Provides maximum flexibility but significantly increases development time for common components. Not suitable for rapid feature development.
    *   **Trade-offs:**
        *   Can lead to a somewhat "AntD look" if not customized sufficiently.
        *   Bundle size can be a concern if not managed properly (though tree-shaking helps).
        *   Some complex components might have a steeper learning curve for customization.

---

## ADR-FE-004: State Management with React Context API

*   **Status:** Accepted (for current scale)
*   **Context:**
    *   Need for managing global or widely shared state, such as user authentication status and triggers for global UI actions (modals/drawers managed by the main layout).
*   **Decision:**
    *   The React Context API is the primary mechanism for managing global/shared state (`AuthContext`, `PageActionContext`).
    *   Local component state (`useState`, `useReducer`) is preferred for state not needed outside a component or its immediate children.
*   **Rationale/Consequences:**
    *   **Benefits:**
        *   **Built-in to React:** No external dependencies needed for basic global state.
        *   **Simplicity:** Relatively easy to understand and implement for common use cases like authentication.
        *   **Good for Low-Frequency Updates:** Suitable for state that doesn't change very frequently (e.g., auth status, registered modal trigger functions).
    *   **Alternatives Considered:**
        *   **Redux / Redux Toolkit:** Very powerful and scalable, excellent dev tools, but introduces more boilerplate and complexity, which was deemed overkill for SmartInfo's current needs.
        *   **Zustand / Jotai / Recoil:** Lighter-weight global state managers. Could be considered if React Context performance becomes an issue or more complex state interactions are needed.
    *   **Trade-offs/Considerations:**
        *   **Performance:** React Context can cause re-renders in all consuming components when the context value changes, even if a component only uses a part of the context that didn't change. This is managed by creating focused contexts and memoizing context values where appropriate.
        *   **Scalability:** For applications with very complex and frequently updating global state, React Context might become less performant or harder to manage than dedicated state libraries. This will be monitored as SmartInfo evolves. (See `STATE_MANAGEMENT.md`).

---

## ADR-FE-005: Styling Strategy - CSS Modules and Global CSS

*   **Status:** Accepted
*   **Context:**
    *   Need for a consistent and maintainable approach to styling components and the overall application.
    *   Desire for scoped styles to avoid class name collisions and global namespace pollution.
*   **Decision:**
    *   **CSS Modules (`*.module.css`):** Adopted as the primary method for component-level styling, providing local scoping.
    *   **Global CSS (`styles/globals.css`):** Used for application-wide base styles, CSS custom properties (theme variables), and global overrides for Ant Design components.
*   **Rationale/Consequences:**
    *   **Benefits of CSS Modules:**
        *   **Local Scope:** Prevents style conflicts between components.
        *   **Explicit Dependencies:** Styles are imported like JavaScript modules, making dependencies clear.
        *   Integrates well with Next.js.
    *   **Benefits of Global CSS:**
        *   Useful for base typography, resets, and defining global theme variables.
        *   Necessary for overriding Ant Design's global styles.
    *   **Alternatives Considered:**
        *   **Styled-Components / Emotion (CSS-in-JS):** Powerful, allows dynamic styling with JavaScript, co-locates styles with components. Can have a slight runtime overhead and a different developer experience. CSS Modules were chosen for closer adherence to standard CSS and build-time scoping.
        *   **Tailwind CSS:** Utility-first CSS framework. Offers rapid development but can lead to verbose HTML and a different styling paradigm. Not chosen to maintain more traditional CSS/component styling.
        *   **Plain Global CSS / BEM:** Prone to naming collisions and harder to manage scope in larger applications.
    *   **Trade-offs:** Managing the interplay between global styles, Ant Design styles, and CSS module styles requires some discipline.

---
## ADR-FE-006: API Client - Axios with Service Layer

*   **Status:** Accepted
*   **Context:**
    *   The frontend needs a reliable way to make HTTP requests to the backend API.
    *   Centralized configuration for base URL, headers (like Auth tokens), and global error handling is desirable.
    *   API call logic should be abstracted from UI components.
*   **Decision:**
    *   **Axios** was chosen as the HTTP client library.
    *   A centralized Axios instance is configured in `frontend/src/services/api.ts` with request/response interceptors.
    *   A **Service Layer** pattern is used (`frontend/src/services/*.ts`), where specific service files encapsulate API calls related to different backend resources.
*   **Rationale/Consequences:**
    *   **Benefits of Axios:**
        *   Popular, mature, and feature-rich (interceptors, request/response transformation, error handling).
        *   Good TypeScript support.
        *   Easy to configure a base instance.
    *   **Benefits of Service Layer:**
        *   Decouples components from direct API endpoint knowledge.
        *   Centralizes API call logic, making it easier to manage and modify.
        *   Improves testability (services can be mocked when testing components).
    *   **Interceptors:**
        *   Request interceptor automatically adds JWT for authenticated requests.
        *   Response interceptor handles global errors like 401 (token expiry) by dispatching an event for `AuthContext` to handle.
    *   **Alternatives Considered:**
        *   **Native `fetch` API:** Built-in, but requires more boilerplate for features like interceptors, JSON parsing, and error handling compared to Axios.
        *   **Other HTTP clients (e.g., `ky`):** Axios is widely adopted and well-understood.
    *   **Trade-offs:** Adds a small dependency (Axios). The service layer adds an extra layer of abstraction, which is beneficial for larger apps but might feel like slight overhead for very simple calls.

---
*(More ADRs could be added for choices like Jest + RTL for testing, specific state management contexts if their introduction involved significant debate, or decisions around the `AnalysisStreamManager`.)*