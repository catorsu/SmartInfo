/**
 * @file chat.tsx
 * @description Main chat page. If no specific chat ID is provided in the URL,
 * it displays a default view (DefaultChatView) allowing users to start a new
 * conversation or select an existing one from the sidebar (managed by MainLayout).
 * This specific file handles the scenario where the route is just '/chat'.
 * For chats with an ID, `pages/chat/[id].tsx` is used.
 *
 * @file_purpose To provide the primary interface for user interaction with the
 *               chat system, showing a default state or an active chat session.
 */
import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import {
  Layout,
  List,
  Input,
  Button,
  Avatar,
  Spin,
  Empty,
  Typography,
  Space,
  Card,
  message,
  Alert,
  Tooltip
} from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  SendOutlined,
  CopyOutlined
} from '@ant-design/icons';

import * as chatService from '@/services/chatService';
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';
import { Chat, Message, Question } from '@/utils/types'; // MessageCreate is not used here directly
import withAuth from '@/components/auth/withAuth';
import DefaultChatView from '@/components/Chat/DefaultChatView'; // Component for when no chat is selected

const { Content } = Layout; // Layout parts are not directly used here, MainLayout provides them.
const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input; // Not directly used, ChatInputBar handles input.

import { useAuth } from '@/context/AuthContext'; // To get user info and refresh chat list trigger

/**
 * @component ChatPageInternal
 * @description The core logic for the `/chat` page. It primarily manages the state
 * for displaying the `DefaultChatView` when no specific chat ID is active.
 * It handles input for initiating a new chat, which then redirects to `/chat/[id]`.
 *
 * @returns {JSX.Element} The rendered chat interface, typically the DefaultChatView.
 */
const ChatPageInternal: React.FC = () => {
  // This page (`/chat`) primarily shows the DefaultChatView.
  // Active chat sessions are handled by `pages/chat/[id].tsx`.
  // State here is for the input bar in DefaultChatView if a new chat is initiated.
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessingFirstMessage, setIsProcessingFirstMessage] = useState<boolean>(false);
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  const router = useRouter();
  const { user, refreshChatList } = useAuth(); // Get user for greeting, refreshChatList for sidebar update

  // Handler for sending the first message, which creates a new chat.
  const handleSendMessage = async () => {
    if (!inputMessage.trim()) {
      return;
    }

    setIsProcessingFirstMessage(true);
    setError(null);
    const originalInputMessage = inputMessage; // Store before clearing

    try {
      // Create a new chat session. The title might be derived from the first message.
      const newChat = await chatService.createChat({ title: originalInputMessage.substring(0, 30) + (originalInputMessage.length > 30 ? '...' : '') });
      setInputMessage(''); // Clear input after successful creation attempt

      // Redirect to the new chat session's page, passing the initial message as a query param
      // so `pages/chat/[id].tsx` can send it.
      router.replace({
        pathname: `/chat/${newChat.id}`,
        query: { initialMessage: originalInputMessage }
      });

      refreshChatList(); // Trigger sidebar update in MainLayout

    } catch (err) {
      console.error('Failed to create new chat session:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
      // Do not clear inputMessage on error, allow user to retry.
      handleApiError(err, 'Failed to start new chat'); // Show error to user
    } finally {
      setIsProcessingFirstMessage(false);
    }
  };

  const handleDefaultViewInputChange = (value: string) => {
    setInputMessage(value);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputMessage(suggestion);
    // Optionally, could immediately trigger handleSendMessage if desired.
  };

  const username = user?.username || "User"; // Use authenticated user's name or a default.

  return (
    <div style={{
      height: '100%', // Fill the parent Content area from MainLayout
      display: 'flex',
      flexDirection: 'column',
      padding: 24, // Standard padding, can be adjusted
      borderRadius: 8, // Consistent with other content areas
    }}>
      {error && (
        <Alert
          message="Error"
          description={error.message || "An unexpected error occurred."}
          type="error"
          showIcon
          closable
          onClose={() => setError(null)}
          style={{ marginBottom: 16 }}
        />
      )}
      {/* Always show DefaultChatView on the base /chat route */}
      <DefaultChatView
        username={username}
        onSuggestionClick={handleSuggestionClick}
        inputValue={inputMessage}
        onInputChange={handleDefaultViewInputChange}
        onSendMessage={handleSendMessage}
        loading={isProcessingFirstMessage}
      />
    </div>
  );
};

// Wrap the internal component with authentication.
const ChatPage = withAuth(ChatPageInternal);
export default ChatPage;