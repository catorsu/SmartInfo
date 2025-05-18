import api from './api';
import axios from 'axios';
import {
  Chat,
  ChatCreate,
  Message,
  MessageCreate,
  Question,
  ChatAnswer
} from '../utils/types';

const BASE_PATH = '/api/chat';


export const getChats = async (): Promise<Chat[]> => {
  const response = await api.get(`${BASE_PATH}/`);
  return response.data;
};

export const createChat = async (chat: ChatCreate): Promise<Chat> => {
  const response = await api.post(`${BASE_PATH}/`, chat);
  return response.data;
};

export const getChat = async (chatId: number): Promise<Chat | null> => {
  try {
    const response = await api.get<Chat>(`${BASE_PATH}/${chatId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.warn(`ChatService: Chat with ID ${chatId} not found (404).`);
      return null;
    }
    console.error(`ChatService: Error fetching chat ${chatId}:`, error);
    throw error;
  }
};

export const updateChat = async (chatId: number, chat: ChatCreate): Promise<Chat> => {
  const response = await api.put(`${BASE_PATH}/${chatId}`, chat);
  return response.data;
};

export const deleteChat = async (chatId: number): Promise<void> => {
  await api.delete(`${BASE_PATH}/${chatId}`);
};


export const getMessages = async (chatId: number): Promise<Message[]> => {
  const response = await api.get(`${BASE_PATH}/${chatId}/messages`);
  return response.data;
};

export const createMessage = async (message: MessageCreate): Promise<Message> => {
  const response = await api.post(`${BASE_PATH}/messages`, message);
  return response.data;
};

export const getMessage = async (messageId: number): Promise<Message | null> => {
  try {
    const response = await api.get<Message>(`${BASE_PATH}/messages/${messageId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      console.warn(`ChatService: Message with ID ${messageId} not found (404).`);
      return null;
    }
    console.error(`ChatService: Error fetching message ${messageId}:`, error);
    throw error;
  }
};

export const deleteMessage = async (messageId: number): Promise<void> => {
  await api.delete(`${BASE_PATH}/messages/${messageId}`);
};


export const askQuestion = async (question: Question): Promise<Response> => {
  const token = localStorage.getItem('authToken');
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Construct the full API URL. Assuming api.defaults.baseURL is available and correct.
  // If not, use process.env.NEXT_PUBLIC_API_URL directly.
  const apiUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${BASE_PATH}/ask`;

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(question),
  });

  if (!response.ok) {
    // Attempt to read error details from the response body if it's JSON
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData && errorData.detail) {
        errorDetail = errorData.detail;
      }
    } catch (e) {
      // Ignore if response body is not JSON or empty
    }
    throw new Error(errorDetail);
  }
  return response; // Return the raw Response object for streaming
};
