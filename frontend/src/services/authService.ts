import api from './api';
import { handleApiError } from '../utils/apiErrorHandler';


interface LoginCredentials {
    username: string;
    password: string;
}


export interface LoginResponse {
    access_token: string;
    token_type: string;
    user: User;
}


interface SignupData {
    username: string;
    password: string;

}


export interface User {
    id: string;
    username: string;

}

/**
 * Calls the backend API to log in a user.
 * @param credentials - The user's login credentials (username, password).
 * @returns A promise that resolves with the login response (token, user data).
 */
export const loginUser = async (credentials: LoginCredentials): Promise<LoginResponse> => {
    try {
        const formData = new URLSearchParams();
        formData.append('username', credentials.username);
        formData.append('password', credentials.password);

        const response = await api.post<LoginResponse>('/api/auth/token', formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Login failed');
    }
};

/**
 * Calls the backend API to log out a user.
 * (This might not be strictly necessary if logout is purely client-side token removal,
 * but often includes invalidating the token on the backend).
 * @returns A promise that resolves when the logout is complete.
 */
export const logoutUser = async (): Promise<void> => {
    try {
        // TODO: Replace '/api/auth/logout' with the actual backend endpoint if needed
        // This endpoint might not exist or might not be required depending on backend implementation
        // await api.post('/api/auth/logout');
        console.log("Logout request potentially sent to /api/auth/logout (if implemented).");
    } catch (error) {
        throw handleApiError(error, 'Logout failed');
    }
};

/**
 * Calls the backend API to register a new user.
 * @param userData - The data for the new user.
 * @returns A promise that resolves with the registration response (which is now the same as login response).
 */
export const registerUser = async (userData: SignupData): Promise<LoginResponse> => {
    try {
        const response = await api.post<LoginResponse>('/api/auth/register', userData);
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Registration failed');
    }
};

/**
 * Fetches current user profile using the stored authentication token.
 * This is used to validate if the token is still valid and get current user data.
 * @returns A promise that resolves with the user profile data.
 */
export const fetchUserProfile = async (): Promise<User> => {
    try {
        const response = await api.get<User>('/api/auth/users/me');
        return response.data;
    } catch (error) {
        throw handleApiError(error, 'Failed to fetch user profile');
    }
};


export interface PasswordChangeRequest {
    current_password: string;
    new_password: string;
}

export interface UsernameChangeRequest {
    new_username: string;
    current_password: string;
}

export const changePassword = async (data: PasswordChangeRequest): Promise<{ message: string }> => {
    const response = await api.put<{ message: string }>('/api/auth/users/me/password', data);
    return response.data;
};

export const changeUsername = async (data: UsernameChangeRequest): Promise<User> => {
    const response = await api.put<User>('/api/auth/users/me/username', data);
    return response.data;
};
