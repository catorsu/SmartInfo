import axios, { AxiosHeaders } from 'axios';


const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000, 
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');

    if (token) {
      if (!config.headers) {
        config.headers = new AxiosHeaders();
      }
      config.headers.set('Authorization', `Bearer ${token}`);
    } else {
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.message === 'Network Error') {
      console.error('Network error detected - server might be down or unreachable');
    } else {
      console.error('API Error:', error.response?.data || error.message);
    }

    if (error.response?.status === 401) {
      console.warn('401 Unauthorized error detected.');
      if (error.config && error.config.url !== '/api/auth/token') {
        console.log('401 on a non-login endpoint, dispatching auth-error event.');
        window.dispatchEvent(new CustomEvent('auth-error', { detail: { type: 'token-expired' } }));
      } else {
        console.log('401 on login endpoint, not dispatching auth-error.');
      }
    }

    return Promise.reject(error);
  }
);

export default api;
