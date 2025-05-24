/**
 * @file testBackendConnection.ts
 * @description A utility script to test connectivity with all major backend API endpoints.
 * This script is intended to be run from the command line using `ts-node`
 * (e.g., `npx ts-node src/utils/testBackendConnection.ts`). It helps verify
 * that the frontend can communicate with the backend services as expected.
 *
 * @file_purpose To provide a quick and easy way to diagnose backend connectivity issues
 *               during development or deployment.
 */
import axios from 'axios';

// API_URL is determined from environment variables, defaulting to localhost:8000.
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * @function testBackendConnections
 * @description Asynchronously tests connections to various backend API endpoints.
 * It makes GET requests to predefined endpoints and logs the status and a summary
 * of the response. If any test fails, it logs detailed error information.
 *
 * @returns {Promise<void>} A promise that resolves when all tests are completed or an error occurs.
 * @sideeffect Logs output to the console regarding the status of each test and any errors.
 *
 * @example
 * // To run this script:
 * // npx ts-node src/utils/testBackendConnection.ts
 */
async function testBackendConnections() {
  console.log('Testing backend connections...');
  console.log(`API URL: ${API_URL}`);

  try {
    // Test 1: API Root / Health Check
    console.log('\n--- Testing API Health ---');
    const healthCheck = await axios.get(`${API_URL}/health`);
    console.log('Health check:', healthCheck.status, healthCheck.data);

    // Test 2: News Endpoints (e.g., fetching a list of news)
    console.log('\n--- Testing News Endpoints ---');
    const news = await axios.get(`${API_URL}/api/news`); // Assuming /api/news is a valid list endpoint
    console.log('News endpoint:', news.status, `Retrieved ${news.data.length} news items (or similar list summary)`);

    // Test 3: Categories Endpoint
    console.log('\n--- Testing Categories Endpoint ---');
    const categories = await axios.get(`${API_URL}/api/news/categories`);
    console.log('Categories endpoint:', categories.status, `Retrieved ${categories.data.length} categories`);

    // Test 4: Sources Endpoint
    console.log('\n--- Testing Sources Endpoint ---');
    const sources = await axios.get(`${API_URL}/api/news/sources`);
    console.log('Sources endpoint:', sources.status, `Retrieved ${sources.data.length} sources`);

    // Test 5: Chat History Endpoint (example, might require auth or specific user context)
    // This test might fail if authentication is required and not handled by this script.
    console.log('\n--- Testing Chat History Endpoint ---');
    const chatHistory = await axios.get(`${API_URL}/api/chat/history`);
    console.log('Chat history endpoint:', chatHistory.status, `Retrieved ${chatHistory.data.length} chat sessions (or similar)`);

    // Test 6: Settings Endpoint (example, might require auth)
    console.log('\n--- Testing Settings Endpoint ---');
    const settings = await axios.get(`${API_URL}/api/settings`);
    console.log('Settings endpoint:', settings.status, 'Settings retrieved successfully (or summary)');

    console.log('\n✅ All backend tests completed successfully!');

  } catch (error) {
    console.error('\n❌ Backend connection test failed:');
    if (axios.isAxiosError(error)) {
      console.error(`Error Message: ${error.message}`);
      if (error.response) {
        console.error(`Status: ${error.response.status}`);
        console.error(`Response Data:`, error.response.data);
      } else if (error.request) {
        console.error('No response received. Request details:', error.request);
      }
    } else {
      // For non-Axios errors
      console.error(error);
    }
    console.error('\nPlease ensure the backend server is running and accessible at:', API_URL);
    console.error('Also, check if any tested endpoints require authentication that is not provided by this script.');
  }
}

// Run the tests when the script is executed.
testBackendConnections();