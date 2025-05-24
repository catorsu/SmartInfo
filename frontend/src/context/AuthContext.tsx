/**
 * @file AuthContext.tsx
 * @description Defines the authentication context, provider, and hook for managing
 * user authentication state across the SmartInfo frontend application.
 * It handles login, logout, signup, token validation, and user profile management.
 *
 * @file_purpose To provide a centralized and easily accessible way to manage and
 *               consume user authentication state and actions throughout the application.
 */
import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/router';
import { loginUser, logoutUser, registerUser, fetchUserProfile, User as UserType } from '../services/authService';
import api from '../services/api';

/**
 * @typedef {object} User
 * @description Represents the structure of a user object, mirroring the User type
 * defined in `../services/authService`.
 * @property {string} id - The unique identifier for the user.
 * @property {string} username - The username of the user.
 * // Other user properties would be listed here if applicable.
 */
type User = UserType;

/**
 * @interface AuthContextType
 * @description Defines the shape of the authentication context, including state
 * variables and action functions provided to consuming components.
 * @property {boolean} isAuthenticated - True if the user is currently authenticated.
 * @property {User | null} user - The authenticated user object, or null if not authenticated.
 * @property {string | null} token - The authentication token (e.g., JWT), or null if not available.
 * @property {boolean} loading - True if an authentication operation (e.g., login, token validation) is in progress.
 * @property {(username: string, password: string) => Promise<void>} login - Function to log in a user.
 * @property {() => Promise<void>} logout - Function to log out the current user.
 * @property {(username: string, password: string) => Promise<void>} signup - Function to register and log in a new user.
 * @property {() => void} refreshChatList - Function to trigger a refresh of the chat list (typically in MainLayout).
 * @property {(callback: (() => void) | null) => void} setRefreshChatListCallback - Function used by MainLayout to register its chat list refresh logic.
 * @property {(updatedUser: User) => void} updateUserProfile - Function to update the local user profile state, e.g., after a username change.
 */
interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  signup: (username: string, password: string) => Promise<void>;
  refreshChatList: () => void;
  setRefreshChatListCallback: (callback: (() => void) | null) => void;
  updateUserProfile: (updatedUser: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * @interface AuthProviderProps
 * @description Defines the props for the AuthProvider component.
 * @property {ReactNode} children - The child components that will have access to the AuthContext.
 */
interface AuthProviderProps {
  children: ReactNode;
}

/**
 * @component AuthProvider
 * @description Provides the authentication context to its children. It manages
 * the authentication state (user, token, loading status), handles login, logout,
 * and signup operations, validates tokens on initial load, and exposes these
 * functionalities and state through the `AuthContext`. It also handles global
 * auth error events (e.g., token expiry).
 *
 * @param {AuthProviderProps} props - The props for the component, primarily `children`.
 * @returns {JSX.Element} The AuthProvider component wrapping its children, making the context available.
 *
 * @example
 * // In _app.tsx:
 * // <AuthProvider>
 * //   <MyApp />
 * // </AuthProvider>
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [refreshChatListCallback, setRefreshChatListCallbackInternal] = useState<(() => void) | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true); // Start with loading true for initial token validation.
  const router = useRouter();

  useEffect(() => {
    // Validates the stored token on initial application load.
    const validateToken = async () => {
      const storedToken = localStorage.getItem('authToken');
      if (storedToken) {
        setToken(storedToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
        
        try {
          const fetchedUser = await fetchUserProfile();
          setUser(fetchedUser);
          setIsAuthenticated(true);
        } catch (error: any) {
          console.error("Token validation failed:", error.message);
          // Clear invalid token and user state.
          localStorage.removeItem('authToken');
          setToken(null);
          setUser(null);
          setIsAuthenticated(false);
          if (api.defaults.headers.common['Authorization']) {
            delete api.defaults.headers.common['Authorization'];
          }
        }
      } else {
        // No token found, user is not authenticated.
        setIsAuthenticated(false);
        setUser(null);
        setToken(null);
      }
      setLoading(false); // Finished initial loading/validation.
    };

    validateToken();
  }, []); // Empty dependency array ensures this runs only once on mount.


  // Effect to update Axios default headers when the token changes.
  useEffect(() => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else if (api.defaults.headers.common['Authorization']) {
      // Remove auth header if token is nullified (e.g., on logout).
      delete api.defaults.headers.common['Authorization'];
    }
  }, [token]);

  /**
   * @function logout
   * @description Logs out the current user by clearing local token and state,
   * and redirecting to the login page.
   * @sideeffect Clears 'authToken' from localStorage, updates context state,
   *             removes Authorization header from Axios defaults, and navigates to '/login'.
   */
  const logout = async () => {
    setLoading(true);
    try {
      // Call backend logout endpoint if it exists and is necessary.
      // await authService.logoutUser(); // Example if backend logout is implemented.
    } catch (error) {
        console.error('Backend logout failed (if applicable):', error);
    } finally {
        localStorage.removeItem('authToken');
        setToken(null);
        setUser(null);
        setIsAuthenticated(false);
        // Axios header is cleared by the `token` useEffect.
        setLoading(false);
        router.push('/login');
    }
  };

  // Effect to listen for global 'auth-error' events (e.g., token expiry from API interceptor).
  useEffect(() => {
    const handleAuthError = (event: CustomEvent) => {
      if (event.detail?.type === 'token-expired') {
        logout(); // Trigger logout if token is reported as expired.
      }
    };

    window.addEventListener('auth-error', handleAuthError as EventListener);

    return () => {
      window.removeEventListener('auth-error', handleAuthError as EventListener);
    };
  }, [logout]); // `logout` is a dependency as it's called by the event handler.

  /**
   * @function login
   * @description Authenticates a user with the given credentials.
   * On success, stores the token, updates user state, and navigates.
   * @param {string} username - The user's username.
   * @param {string} password - The user's password.
   * @throws {Error} Propagates error from `loginUser` service if login fails.
   * @sideeffect Stores 'authToken' in localStorage, updates context state,
   *             sets Authorization header via `token` useEffect, and navigates.
   */
  const login = async (username: string, password: string) => {
    setLoading(true);
    try {
      const { access_token: receivedToken, user: loggedInUser } = await loginUser({ username, password });

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);

      // Navigate to intended return URL or default to home.
      const returnUrl = (router.query.returnUrl as string) || '/';
      router.push(returnUrl);

    } catch (error) {
      console.error('Login failed:', error);
      // Ensure state is cleared on login failure.
      localStorage.removeItem('authToken');
      setToken(null);
      setUser(null);
      setIsAuthenticated(false);
      throw error; // Re-throw for the calling component to handle (e.g., display error message).
    } finally {
      setLoading(false);
    }
  };

  /**
   * @function signup
   * @description Registers a new user and then logs them in.
   * On success, stores the token, updates user state, and navigates.
   * @param {string} username - The new user's username.
   * @param {string} password - The new user's password.
   * @throws {Error} Propagates error from `registerUser` service if signup fails.
   * @sideeffect Stores 'authToken' in localStorage, updates context state,
   *             sets Authorization header via `token` useEffect, and navigates to '/'.
   */
  const signup = async (username: string, password: string) => {
    setLoading(true);
    try {
      // Assumes registerUser also returns token and user data similar to login.
      const { access_token: receivedToken, user: loggedInUser } = await registerUser({ username, password });

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);

      router.push('/'); // Navigate to home page after successful registration and login.

    } catch (error) {
      console.error('Registration failed:', error);
      localStorage.removeItem('authToken');
      setToken(null);
      setUser(null);
      setIsAuthenticated(false);
      throw error; // Re-throw for the calling component.
    } finally {
      setLoading(false);
    }
  };

  /**
   * @function refreshChatList
   * @description Invokes the callback provided by `MainLayout` to refresh its chat list.
   * @sideeffect Calls the registered `refreshChatListCallback`.
   */
  const refreshChatList = () => {
    if (refreshChatListCallback) {
      refreshChatListCallback();
    } else {
      // This warning is useful for development if the callback mechanism is not correctly set up.
      console.warn('AuthContext: refreshChatList called, but no callback is set from MainLayout.');
    }
  };

  /**
   * @function updateUserProfile
   * @description Updates the local user profile state within the context.
   * Typically called after a successful profile update operation (e.g., username change).
   * @param {User} updatedUser - The new user object containing updated profile information.
   * @sideeffect Updates the `user` state in the context.
   */
  const updateUserProfile = (updatedUser: User) => {
    setUser(updatedUser);
  };

  /**
   * @function setRefreshChatListCallback
   * @description Allows `MainLayout` (or another component) to register a callback function
   * that can be triggered by `refreshChatList`.
   * @param {(() => void) | null} callback - The callback function to be registered, or null to clear it.
   * @sideeffect Updates the internal `refreshChatListCallback` state.
   */
  const setRefreshChatListCallback = (callback: (() => void) | null) => {
    // Wrapping with another function to ensure stable identity if callback is passed directly.
    setRefreshChatListCallbackInternal(() => callback);
  };

  const contextValue: AuthContextType = {
    isAuthenticated,
    user,
    token,
    loading,
    login,
    logout,
    signup,
    refreshChatList,
    setRefreshChatListCallback,
    updateUserProfile,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * @hook useAuth
 * @description Custom hook to easily consume the authentication context (`AuthContext`).
 * It provides access to the authentication state (isAuthenticated, user, token, loading)
 * and action functions (login, logout, signup, etc.).
 * Throws an error if used outside of an `AuthProvider`.
 *
 * @returns {AuthContextType} The authentication context value.
 * @throws {Error} If used outside of an `AuthProvider`.
 *
 * @example
 * // In a component:
 * // const { isAuthenticated, user, login } = useAuth();
 * // if (isAuthenticated) { console.log(user.username); }
 * // const handleLogin = async () => await login('user', 'pass');
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};