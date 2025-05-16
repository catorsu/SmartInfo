# Project Brief: SmartInfo (Version 1.0)

## 1. Project Title
SmartInfo: News Aggregation, Analysis, and Chat

## 2. Project Goal
To develop a full-stack application for intelligent news aggregation, automated content analysis using Large Language Models (LLMs), and interactive chat functionalities. The application aims to provide a modern user experience with a FastAPI backend for robust data processing and API management, and a React/Next.js frontend.

## 3. Core Requirements
The system must support:
*   **User Management:** Secure user authentication and management (JWT-based).
*   **News Aggregation:**
    *   Management of news sources and categories (CRUD per user).
    *   Asynchronous web crawling (Aiohttp, Playwright, Selenium) for fetching news content.
    *   Background task processing (Celery, Redis) for fetching news.
*   **Content Analysis (LLM-Powered):**
    *   Integration with OpenAI-compatible LLM APIs.
    *   Extraction of relevant article links from source pages.
    *   Generation of concise summaries and fact-based titles for articles.
    *   On-demand in-depth analysis of news content.
*   **Chat Functionality:**
    *   LLM-powered conversational chat interface.
    *   WebSocket support for real-time task progress monitoring (for news fetching/analysis).
*   **Configuration & Personalization:**
    *   API key management for user-specific LLM configurations.
    *   Persistent user preference storage.
*   **Technology Stack:**
    *   **Backend:** FastAPI (Python 3.12+), PostgreSQL, Celery, Redis.
    *   **Frontend:** Next.js (TypeScript), Ant Design, React Context API, Axios.
*   **API Documentation:** Auto-generated via Swagger UI and ReDoc.

## 4. Scope
*   **In Scope:**
    *   Full-stack development of backend and frontend as described.
    *   User authentication and authorization.
    *   News source/category management.
    *   Automated news fetching and processing pipeline.
    *   LLM integration for link extraction, summarization, analysis, and chat.
    *   Real-time progress updates for background tasks.
    *   User settings for API keys and preferences.
*   **Out of Scope (Initially):**
    *   Advanced social sharing features beyond basic link presentation.
    *   Mobile-native applications (web-first).
    *   Deployment to production environments (focus on development setup initially).
    *   User-to-user interaction features.

## 5. Target Users
Users interested in:
*   Aggregating news from various sources.
*   Leveraging AI for quick content summarization and analysis.
*   Engaging in a conversational manner with an AI about news or other topics.

## 6. Success Criteria (Initial)
*   Functional user registration and login.
*   Ability to add, view, and manage news sources and categories.
*   Successful fetching of news content from configured sources.
*   LLM-generated summaries and titles for fetched articles.
*   Functional chat interface powered by an LLM.
*   Users can manage their LLM API keys.