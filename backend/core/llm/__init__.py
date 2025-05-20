"""
LLM Interaction Package for SmartInfo.

This package provides the necessary tools for interacting with Large Language
Models (LLMs). It includes client implementations for both synchronous and
asynchronous communication with OpenAI-compatible LLM APIs, and a connection
pool for managing and reusing asynchronous client instances efficiently.

@module_purpose: To abstract and manage interactions with LLMs, providing
                 a consistent interface for other parts of the SmartInfo
                 backend to leverage language model capabilities.
@primary_consumers: - `backend.core.workflow.*` (e.g., `news_fetch` for content processing)
                    - `backend.services.ChatService` (for conversational AI)
                    - `backend.services.NewsService` (for content analysis)
                    - Background tasks in `backend.background.tasks.*`
@primary_dependencies: - `openai` (the official Python library for OpenAI APIs)
                       - `asyncio` (for asynchronous operations)
@Key Components/Exports:
  - AsyncLLMClient: Asynchronous client for LLM API interaction.
  - SyncLLMClient: Synchronous client for LLM API interaction.
  - LLMClientPool: Manages a pool of AsyncLLMClient instances.
"""
