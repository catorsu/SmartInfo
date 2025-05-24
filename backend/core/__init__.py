"""
Core backend logic for SmartInfo, including web crawling, security, and LLM interactions.

This package encapsulates fundamental backend functionalities essential for
the SmartInfo application. It provides modules for web content retrieval,
security mechanisms like authentication and password management, WebSocket
connection handling for real-time updates, and interactions with Large
Language Models (LLMs).

Key Modules:
    crawler: Provides tools for fetching and processing web page content.
    security: Handles user authentication, password hashing, and JWT
              management.
    ws_manager: Manages WebSocket connections for real-time communication.
    llm (sub-package): Contains clients and connection pools for
                       interacting with Large Language Models.
"""
