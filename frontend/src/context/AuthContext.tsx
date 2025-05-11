import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/router';
import { loginUser, logoutUser, registerUser, fetchUserProfile, User as UserType } from '../services/authService';
import api from '../services/api';


type User = UserType;

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

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [refreshChatListCallback, setRefreshChatListCallbackInternal] = useState<(() => void) | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    const validateToken = async () => {
      const storedToken = localStorage.getItem('authToken');
      if (storedToken) {
        console.log("Found token in localStorage. Validating...");
        setToken(storedToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
        
        try {
          const fetchedUser = await fetchUserProfile();
          console.log("Token validation successful. User:", fetchedUser);
          setUser(fetchedUser);
          setIsAuthenticated(true);
          console.log("Auth state initialized from validated token.");
        } catch (error: any) {
          console.error("Token validation failed:", error.message);
          localStorage.removeItem('authToken');
          setToken(null);
          setUser(null);
          setIsAuthenticated(false);
          if (api.defaults.headers.common['Authorization']) {
            delete api.defaults.headers.common['Authorization'];
          }
        }
      } else {
        console.log("No token found in localStorage.");
        setIsAuthenticated(false);
        setUser(null);
        setToken(null);
      }
      setLoading(false);
    };

    validateToken();
  }, []);


  useEffect(() => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else if (api.defaults.headers.common['Authorization']) {
      delete api.defaults.headers.common['Authorization'];
    }
  }, [token]);

  const logout = async () => {
    setLoading(true);
    console.log("Logging out user.");
    try {
      console.log("Backend logout call skipped/successful (if implemented).");
    } catch (error) {
        console.error('Backend logout failed:', error);
    } finally {
        localStorage.removeItem('authToken');
        setToken(null);
        setUser(null);
        setIsAuthenticated(false);
        if (api.defaults.headers.common['Authorization']) {
            delete api.defaults.headers.common['Authorization'];
        }
        console.log("Token removed, state reset.");
        setLoading(false);
        router.push('/login');
    }
  };

  useEffect(() => {
    const handleAuthError = (event: CustomEvent) => {
      console.log('Auth error event received:', event.detail);
      if (event.detail?.type === 'token-expired') {
        console.log('Token expired, logging out...');
        logout(); // Call the logout function
      }
    };

    window.addEventListener('auth-error', handleAuthError as EventListener);

    return () => {
      console.log('Removing auth-error event listener.');
      window.removeEventListener('auth-error', handleAuthError as EventListener);
    };
  }, [logout]);

  const login = async (username: string, password: string) => {
    setLoading(true);
    try {
      console.log(`Attempting login for user: ${username}`);
      const { access_token: receivedToken, user: loggedInUser } = await loginUser({ username, password });

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);
      console.log("Login successful, token stored.");

      const returnUrl = (router.query.returnUrl as string) || '/';
      router.push(returnUrl);

    } catch (error) {
      console.error('Login failed:', error);
      localStorage.removeItem('authToken');
      setToken(null);
      setUser(null);
      setIsAuthenticated(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const signup = async (username: string, password: string) => {
    setLoading(true);
    try {
      console.log(`Attempting to register user: ${username}`);

      const { access_token: receivedToken, user: loggedInUser } = await registerUser({ username, password });

      console.log("Registration successful, automatically logging in.");

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);
      console.log("Registration and auto-login successful, token stored.");

      router.push('/');

    } catch (error) {
      console.error('Registration failed:', error);
      localStorage.removeItem('authToken');
      setToken(null);
      setUser(null);
      setIsAuthenticated(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const refreshChatList = () => {
    if (refreshChatListCallback) {
      console.log("AuthContext: refreshChatList called, invoking callback.");
      refreshChatListCallback();
    } else {
      console.warn('AuthContext: refreshChatList called, but no callback is set from MainLayout.');
    }
  };

  const updateUserProfile = (updatedUser: User) => {
    setUser(updatedUser);
    console.log("AuthContext: User profile updated.", updatedUser);
  };

  const setRefreshChatListCallback = (callback: (() => void) | null) => {
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

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
