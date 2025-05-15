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
        setToken(storedToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
        
        try {
          const fetchedUser = await fetchUserProfile();
          setUser(fetchedUser);
          setIsAuthenticated(true);
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
    try {
      // Backend logout call logic was here or intended here
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
        setLoading(false);
        router.push('/login');
    }
  };

  useEffect(() => {
    const handleAuthError = (event: CustomEvent) => {
      if (event.detail?.type === 'token-expired') {
        logout(); // Call the logout function
      }
    };

    window.addEventListener('auth-error', handleAuthError as EventListener);

    return () => {
      window.removeEventListener('auth-error', handleAuthError as EventListener);
    };
  }, [logout]);

  const login = async (username: string, password: string) => {
    setLoading(true);
    try {
      const { access_token: receivedToken, user: loggedInUser } = await loginUser({ username, password });

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);

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

      const { access_token: receivedToken, user: loggedInUser } = await registerUser({ username, password });

      localStorage.setItem('authToken', receivedToken);
      setToken(receivedToken);
      setUser(loggedInUser);
      setIsAuthenticated(true);

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
      refreshChatListCallback();
    } else {
      console.warn('AuthContext: refreshChatList called, but no callback is set from MainLayout.');
    }
  };

  const updateUserProfile = (updatedUser: User) => {
    setUser(updatedUser);
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
