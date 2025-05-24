/**
 * @file apiErrorHandler.ts
 * @description Provides utility functions for handling and processing errors
 * originating from API calls, particularly Axios errors. It includes functions
 * to extract meaningful error messages and to display them using Ant Design's
 * message component, as well as a higher-order function to wrap API calls
 * with standardized error handling.
 *
 * @file_purpose Centralized API error handling logic to ensure consistent
 *               error reporting and processing throughout the application.
 */
import { message } from 'antd';
import axios, { AxiosError } from 'axios';

/**
 * @interface ExtractedErrorDetails
 * @description Defines the structure of the object returned by `extractErrorMessage`.
 * It categorizes the error and provides a user-friendly message and status code.
 */
interface ExtractedErrorDetails {
  type: string;      // Category of the error (e.g., 'notFound', 'forbidden', 'apiError', 'unknown').
  message: string;   // User-friendly error message.
  status?: number;   // HTTP status code, if available from an Axios error.
}

/**
 * @function extractErrorMessage
 * @description Extracts and formats a user-friendly error message and type from
 * an unknown error object, with special handling for Axios errors.
 *
 * @param {unknown} error - The error object, which can be an AxiosError, standard Error, or other.
 * @returns {ExtractedErrorDetails} An object containing the error type, message, and optional status.
 *
 * @example
 * try {
 *   // ... API call
 * } catch (err) {
 *   const errorDetails = extractErrorMessage(err);
 *   console.error(errorDetails.type, errorDetails.message);
 * }
 */
export const extractErrorMessage = (error: unknown): ExtractedErrorDetails => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<any>; // `any` for response data flexibility.
    const status = axiosError.response?.status;
    const data = axiosError.response?.data;
    let messageText = axiosError.message; // Default to Axios's own message.

    // Specific handling for common HTTP error statuses.
    if (status === 404) {
      return { type: 'notFound', message: data?.detail || 'The requested resource was not found.', status };
    }
    if (status === 403) {
      return { type: 'forbidden', message: data?.detail || 'You do not have permission to access this resource.', status };
    }
    // Use detailed message from backend response if available.
    if (data?.detail) {
      messageText = data.detail;
    } else if (typeof data === 'string') { // If data is a plain string message.
      messageText = data;
    }

    // For other Axios errors (e.g., 400, 500, network issues).
    return { type: 'apiError', message: messageText, status };
  }

  // Fallback for standard JavaScript Error objects.
  if (error instanceof Error) {
    return { type: 'unknown', message: error.message };
  }

  // Default fallback for truly unknown errors.
  return { type: 'unknown', message: 'An unexpected error occurred. Please try again.' };
};

/**
 * @function handleApiError
 * @description Handles API errors by displaying a global Ant Design message notification.
 * It avoids showing global messages for 404 (Not Found) and 403 (Forbidden) errors,
 * logging them to the console instead, as these often require specific UI handling
 * rather than a generic global message.
 *
 * @param {unknown} error - The error object from an API call.
 * @param {string} [customMessage] - An optional custom prefix for the error message displayed.
 * @returns {void}
 * @sideeffect Displays an Ant Design message or logs to the console.
 *
 * @example
 * try {
 *   // ... API call
 * } catch (err) {
 *   handleApiError(err, "Failed to load data");
 * }
 */
export const handleApiError = (error: unknown, customMessage?: string): void => {
  const errorDetails = extractErrorMessage(error);

  // Log 404/403 errors to console instead of showing a global message,
  // as these often have specific UI implications (e.g., redirect, show empty state).
  if (errorDetails.type === 'notFound' || errorDetails.type === 'forbidden') {
    console.error(`API Error (${errorDetails.status || 'N/A'} - ${errorDetails.type}):`, errorDetails.message, error);
  } else {
    // Show global message for other errors (network, 5xx, 400, etc.).
    const displayMessage = customMessage ? `${customMessage}: ${errorDetails.message}` : errorDetails.message;
    message.error(displayMessage);
  }
};

/**
 * @function withErrorHandling
 * @description A higher-order function that wraps an asynchronous API call with
 * standardized error handling. It uses `extractErrorMessage` and `handleApiError`.
 * For 404 (Not Found) and 403 (Forbidden) errors, it returns `null` to allow
 * the calling component to handle these cases specifically (e.g., display an
 * Empty component or redirect). Other errors are re-thrown after being displayed
 * globally, unless a custom error handler is provided and handles them.
 *
 * @template T - The expected type of the successful API call's response.
 * @param {() => Promise<T>} apiCall - The asynchronous function making the API call.
 * @param {(error: ExtractedErrorDetails) => void} [errorHandler] - Optional custom error handler.
 *        If provided, this handler is called with extracted error details. The function
 *        will then return `null`. If not provided, `handleApiError` is used.
 * @param {string} [customErrorMessage] - Optional custom prefix for the global error message
 *        if the default `handleApiError` is used.
 * @returns {Promise<T | null>} A promise that resolves with the API call's result,
 *                              or `null` if a 404/403 error occurs or if a custom
 *                              errorHandler is used. Other errors are re-thrown if no
 *                              custom handler is provided.
 * @sideeffect May display global error messages via `handleApiError` or call custom `errorHandler`.
 *
 * @example
 * const fetchData = async () => {
 *   return withErrorHandling(() => myApiService.getData(id), undefined, "Could not fetch item");
 * };
 * const item = await fetchData();
 * if (item === null) { // Handle 404/403 or custom handled error
 *   // ...
 * }
 */
export const withErrorHandling = async <T>(
  apiCall: () => Promise<T>,
  errorHandler?: (error: ExtractedErrorDetails) => void,
  customErrorMessage?: string
): Promise<T | null> => {
  try {
    return await apiCall();
  } catch (error) {
    const errorDetails = extractErrorMessage(error);

    if (errorHandler) {
      errorHandler(errorDetails);
      // If a custom error handler is provided, assume it fully handles the error's
      // side effects (like UI updates or logging). We then return null.
      return null;
    } else {
      // Use the default global error handler.
      handleApiError(error, customErrorMessage);
    }

    // For 404/403 errors, return null to allow specific component-level handling.
    if (errorDetails.type === 'notFound' || errorDetails.type === 'forbidden') {
      return null;
    }

    // For other errors, if no custom handler was provided, re-throw the original error
    // after the global message has been shown. This allows components to still
    // catch and react to specific error types if necessary.
    if (!errorHandler) {
      throw error;
    }

    // This line should ideally not be reached if !errorHandler leads to a throw.
    // However, to satisfy TypeScript's path analysis if errorHandler might not throw,
    // and to be explicit: if a custom handler was used and didn't re-throw, return null.
    return null;
  }
};