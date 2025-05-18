# SmartInfo Frontend: Testing Guide

## 1. Introduction

### 1.1. Purpose
This guide outlines the testing philosophy, strategies, tools, and conventions for the SmartInfo frontend application. The goal is to ensure the reliability, maintainability, and correctness of our React components, pages, and user interactions, enabling both human developers and AI assistants to contribute with confidence.

### 1.2. Testing Philosophy
Our frontend testing philosophy is centered around testing the application as a user would experience it:
*   **User-Centric Testing:** Focus on testing component behavior from the user's perspective, not internal implementation details (favored by React Testing Library).
*   **Confidence in Refactoring:** Good tests allow us to refactor UI and logic with greater confidence.
*   **Component & Integration Focus:** Prioritize testing individual components and their integration with services, context, and routing.
*   **Fast Feedback:** Tests should run quickly to encourage frequent execution during development.

## 2. Tools & Frameworks

*   **Test Runner:** [Jest](https://jestjs.io/) - A widely used JavaScript testing framework.
*   **Testing Library:** [React Testing Library (RTL)](https://testing-library.com/docs/react-testing-library/intro/) - For testing React components by interacting with them as a user would.
*   **User Interactions:** [`@testing-library/user-event`](https://testing-library.com/docs/user-event/intro) - Simulates real user interactions more closely than `fireEvent`.
*   **DOM Assertions:** [`@testing-library/jest-dom`](https://github.com/testing-library/jest-dom) - Provides custom Jest matchers for asserting on DOM state (e.g., `toBeInTheDocument`, `toHaveTextContent`).
*   **Mocking:** Jest's built-in mocking capabilities (`jest.fn()`, `jest.mock()`, `jest.spyOn()`).
*   **TypeScript Support:** Jest and RTL work well with TypeScript.
*   **Environment Setup:** `jest.setup.js` for global test configurations (e.g., mocking `next/router`, environment variables).

## 3. Types of Frontend Tests

### 3.1. Unit Tests
*   **Focus:** Testing small, isolated pieces of JavaScript/TypeScript logic.
*   **Examples:** Utility functions (`frontend/src/utils/`), simple custom React hooks (if logic is separable from rendering), helper functions within services.
*   **Dependencies:** External dependencies should be mocked.
*   **Location:** Typically co-located or in a corresponding `__tests__` subdirectory (e.g., `frontend/src/utils/__tests__/apiErrorHandler.test.ts`).

### 3.2. Component / Integration Tests (Primary Focus with RTL)
*   **Focus:** Testing React components by rendering them and interacting with them as a user would. This often involves testing how a component integrates with its children, handles props, manages internal state, and interacts with mocked services or contexts.
*   **Scope:** Can range from a single simple component to a more complex component that composes others (like a page section).
*   **Dependencies:**
    *   API calls (via services) **MUST** be mocked.
    *   React Contexts **SHOULD** be provided with mock values or wrapped with a test-specific provider if the component consumes them.
    *   `next/router` is typically mocked (as done in `jest.setup.js`).
*   **Location:** `frontend/src/__tests__/components/MyComponent.test.tsx` or `frontend/src/__tests__/pages/MyPage.test.tsx`.
*   **Goal:** Verify that components render correctly based on props and state, respond to user interactions as expected, and correctly trigger side effects (like API calls).

### 3.3. End-to-End (E2E) Tests (Future Consideration)
*   **Focus:** Testing complete user flows through the entire application in a real browser environment, interacting with a live (or near-live) backend.
*   **Tools:** Cypress, Playwright (for frontend E2E).
*   **Current Status:** Not formally part of the current testing strategy but may be introduced as the application matures and critical user flows need broader validation.

## 4. Test Organization and Naming Conventions

### 4.1. Directory Structure
*   Primary test location: `frontend/src/__tests__/`.
*   Mirror the `src/` directory structure within `__tests__/` for components, pages, services, utils, etc.
    ```
    frontend/
    └── src/
        ├── __tests__/
        │   ├── components/
        │   │   └── Chat/
        │   │       └── ChatInputBar.test.tsx
        │   ├── pages/
        │   │   └── login.test.tsx
        │   └── services/
        │       └── authService.test.ts
        ├── components/
        ├── pages/
        └── services/
    ```

### 4.2. File Naming
*   Test files **MUST** use the suffix `.test.tsx` (for components/pages) or `.test.ts` (for non-JSX files).
*   Example: `ChatInputBar.test.tsx`, `authService.test.ts`.

### 4.3. Test Suite and Case Naming
*   **`describe('ComponentName or FeatureName', () => { ... });`**: Group related tests for a component, page, or specific feature.
*   **`it('should <expected behavior> when <condition/action>', () => { ... });`** or **`test('should <expected behavior> when <condition/action>', () => { ... });`**: Test case names should be descriptive and clearly state what is being tested and under what conditions.
    *   Example: `it('should display an error message when login fails', () => { ... });`
    *   Example: `it('should call onSendMessage with input value when send button is clicked', () => { ... });`

## 5. Writing Tests with React Testing Library (RTL)

### 5.1. Core Philosophy
*   **Test from the User's Perspective:** Interact with your components in the same way a user would (finding elements by role, label, text; firing user events).
*   **Avoid Testing Implementation Details:** Do not test internal state structure or private methods directly. Test the observable behavior and output.
*   **Accessibility First:** Using queries that reflect accessible markup (e.g., `getByRole`, `getByLabelText`) encourages building more accessible components.

### 5.2. Common RTL Practices
*   **Rendering Components:** Use `render()` from `@testing-library/react`.
    ```typescript
    import { render, screen } from '@testing-library/react';
    import MyComponent from './MyComponent';

    render(<MyComponent title="Test" />);
    ```
*   **Queries:** Prioritize accessible queries. See [RTL Query Priority](https://testing-library.com/docs/queries/about#priority).
    *   `screen.getByRole('button', { name: /submit/i })`
    *   `screen.getByLabelText(/username/i)`
    *   `screen.getByPlaceholderText(/enter your email/i)`
    *   `screen.getByText(/hello world/i)`
    *   `screen.getByDisplayValue(/initial value/i)`
    *   `screen.getByAltText(/logo/i)`
    *   `screen.getByTitle(/close button/i)`
    *   `screen.getByTestId('my-custom-testid')` (use sparingly, as a last resort).
*   **User Interactions:** Use `@testing-library/user-event` for simulating user actions.
    ```typescript
    import userEvent from '@testing-library/user-event';

    await userEvent.click(screen.getByRole('button', { name: /submit/i }));
    await userEvent.type(screen.getByLabelText(/username/i), 'testuser');
    ```
*   **Assertions:** Use `expect()` with matchers from `@testing-library/jest-dom`.
    ```typescript
    expect(screen.getByText(/success/i)).toBeInTheDocument();
    expect(myInput).toHaveValue('testuser');
    expect(myButton).toBeDisabled();
    ```
*   **Asynchronous Operations:** Use `async/await` with `waitFor` or `findBy*` queries when dealing with UI updates that happen asynchronously (e.g., after an API call).
    ```typescript
    await waitFor(() => {
      expect(screen.getByText(/data loaded/i)).toBeInTheDocument();
    });
    // or
    const loadedDataElement = await screen.findByText(/data loaded/i);
    ```

## 6. Mocking Frontend Dependencies

### 6.1. API Calls (Services)
*   Mock the service functions that components call.
    ```typescript
    // In MyComponent.test.tsx
    import * as authService from '@/services/authService';

    jest.mock('@/services/authService'); // Mocks the entire module
    const mockedLoginUser = authService.loginUser as jest.Mock;

    it('should call loginUser on form submission', async () => {
      mockedLoginUser.mockResolvedValue({ access_token: 'fake_token', user: { id: '1', username: 'test' } });
      render(<LoginForm />);
      // ... simulate form fill and submit
      await userEvent.click(screen.getByRole('button', { name: /log in/i }));
      expect(mockedLoginUser).toHaveBeenCalledWith({ username: 'user', password: 'pass' });
    });
    ```

### 6.2. React Context
*   For components consuming context, wrap them in the actual Provider with a mocked value, or create a utility test provider.
    ```typescript
    // Example: Testing a component that uses AuthContext
    import { AuthContext } from '@/context/AuthContext';
    import MyProtectedComponent from './MyProtectedComponent';

    const mockAuthContextValue = {
      isAuthenticated: true,
      user: { id: '1', username: 'testuser' },
      // ... other mocked context values and functions
      login: jest.fn(),
      logout: jest.fn(),
    };

    render(
      <AuthContext.Provider value={mockAuthContextValue}>
        <MyProtectedComponent />
      </AuthContext.Provider>
    );
    ```

### 6.3. Browser APIs
*   Use `jest.spyOn` for `localStorage`, `fetch` (if not using Axios exclusively), `navigator`, etc.
    ```typescript
    const getItemSpy = jest.spyOn(window.localStorage.__proto__, 'getItem');
    getItemSpy.mockReturnValue('fake_token');
    ```

### 6.4. Next.js Router
*   Typically mocked globally in `jest.setup.js`.
    ```javascript
    // frontend/jest.setup.js
    jest.mock('next/router', () => ({
      useRouter: () => ({
        push: jest.fn(),
        replace: jest.fn(),
        // ... other router properties/methods needed
        pathname: '/',
        query: {},
      }),
    }));
    ```
    You can then assert calls to `router.push` on the mock.

### 6.5. Child Components (Shallow Rendering conceptually)
*   While RTL encourages testing integrated components, sometimes you might want to mock a child component if it's complex and irrelevant to the parent's specific test.
    ```typescript
    jest.mock('./MyComplexChildComponent', () => () => <div data-testid="mocked-child">Mocked Child</div>);
    ```

## 7. Testing Specific Scenarios

*   **Props:** Render components with different props and assert the output.
*   **Conditional Rendering:** Test all branches of conditional rendering logic.
*   **Event Handling:** Simulate user events and assert that the correct callbacks are called and UI updates occur.
*   **State Changes:** Trigger actions that change component state and assert that the UI reflects these changes.
*   **API Integration:**
    *   Mock service calls.
    *   Test loading states (e.g., spinner is shown).
    *   Test success states (data is rendered correctly).
    *   Test error states (error message is displayed).

## 8. Running Tests

*   **Run all tests:**
    ```bash
    npm test
    # or
    yarn test
    ```
*   **Watch mode (re-runs tests on file changes):**
    ```bash
    npm test -- --watch
    # or
    yarn test --watch
    ```
*   **Run tests for a specific file:**
    ```bash
    npm test -- ChatInputBar.test.tsx
    # or
    yarn test ChatInputBar.test.tsx
    ```
*   **Coverage Report:**
    ```bash
    npm test -- --coverage
    # or
    yarn test --coverage
    ```
    View the report in `frontend/coverage/lcov-report/index.html`.

## 9. Code Coverage

*   **Target:** Aim for **>80%** statement/line coverage for components and critical utility/service functions.
*   **Focus:** Coverage is a useful metric, but prioritize writing meaningful tests that verify actual behavior over just chasing numbers.

## 10. Best Practices & Guidelines

*   **Test Behavior, Not Implementation:** Focus on what the user experiences.
*   **Keep Tests Small and Focused:** Each `it()` or `test()` block should verify one specific aspect.
*   **Use Descriptive Names:** For `describe` blocks and `it`/`test` cases.
*   **Arrange, Act, Assert (AAA):** Structure your tests clearly.
*   **Avoid Logic in Tests:** Test code should be simple and straightforward.
*   **Clean Up:** Use `afterEach(() => { jest.clearAllMocks(); cleanup(); });` (RTL's `cleanup` is often automatic with modern Jest setup).
*   **Don't Test Third-Party Libraries:** Assume libraries like Ant Design are already tested. Test *your* integration with them.

## 11. AI Contribution Guide for Frontend Tests

When an AI assistant is tasked with generating or modifying frontend code:

*   **New Components/Pages:** **MUST** generate corresponding `.test.tsx` files with tests covering:
    *   Basic rendering with default and various props.
    *   Key user interactions and event handling.
    *   Conditional rendering paths.
    *   Integration with mocked services and contexts if applicable.
*   **New Hooks/Utilities:** **MUST** generate unit tests.
*   **Bug Fixes:** **MUST** provide a regression test.
*   **Refactoring:** Existing relevant tests **MUST** pass, and the AI should update tests if interfaces/behavior change.
*   **Adherence:** Generated tests **MUST** follow the principles and patterns outlined in this guide (RTL usage, mocking, naming).

By following these guidelines, we can ensure the SmartInfo frontend is well-tested, robust, and easier to maintain, whether developed by humans or AI.