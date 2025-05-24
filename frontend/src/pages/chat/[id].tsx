/**
 * @file [id].tsx
 * @description Dynamically routed page for displaying an active chat session.
 * It fetches chat details and messages based on the ID from the URL.
 * Handles sending new messages and displaying the conversation history, including
 * streaming responses for AI messages.
 *
 * @file_purpose To provide the UI for an individual, ongoing chat conversation.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import {
  Typography,
  Input, // TextArea is part of Input
  Button,
  Card,
  message,
  Spin,
  Tooltip,
  Empty, // Added for better empty states
  Alert // Added for error display
} from 'antd';
import {
  SendOutlined,
  CopyOutlined
} from '@ant-design/icons';
import { Chat, Message, MessageCreate } from '@/utils/types';
import * as chatService from '@/services/chatService';
import { extractErrorMessage, handleApiError } from '@/utils/apiErrorHandler';
import withAuth from '@/components/auth/withAuth';
import ChatInputBar from '@/components/Chat/ChatInputBar'; // Reusable input component

const { Title, Text, Paragraph } = Typography;
// const { TextArea } = Input; // Not directly used, ChatInputBar handles this.

/**
 * @page ChatSessionPage (Conceptual name for this dynamic page)
 * @description Displays an individual chat session. It fetches the chat history
 * for the given `id`, allows the user to send new messages, and displays
 * incoming messages, including streaming AI responses.
 * If an `initialMessage` query parameter is present (e.g., after creating a new chat),
 * it sends that message automatically.
 * This page is protected and requires authentication.
 *
 * @param {object} props - Props passed by Next.js (empty in this case as data is fetched).
 * @returns {JSX.Element} The rendered chat session interface.
 *
 * @example
 * // Navigation to this page:
 * // router.push('/chat/123'); // Opens chat session with ID 123
 * // router.push('/chat/456?initialMessage=Hello'); // Opens chat 456 and sends "Hello"
 */
const ChatPage: React.FC = () => {
  const router = useRouter();
  const { id, initialMessage: initialMessageQuery } = router.query; // Chat ID and optional initial message
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true); // For initial chat load
  const [sending, setSending] = useState(false); // For when a message is being sent/streamed
  const [isSendingInitial, setIsSendingInitial] = useState<boolean>(false); // Specifically for the initial message
  const [newMessage, setNewMessage] = useState(''); // Content of the input bar
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null); // For scrolling to the bottom
  const initialMessageSentRef = useRef<boolean>(false); // To ensure initial message is sent only once

  // Loads chat details and messages.
  const loadChat = useCallback(async (chatId: number) => {
    try {
      setLoading(true);
      setError(null);
      const chatData = await chatService.getChat(chatId);

      if (chatData === null) {
        setChat(null);
        setMessages([]);
        setError({ type: 'notFound', message: `Chat session with ID ${chatId} not found or access denied.`, status: 404 });
        return;
      }
      setChat(chatData);

      const messagesData = await chatService.getMessages(chatId);
      setMessages(messagesData);

    } catch (err: any) {
      console.error('Failed to load chat:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
      setChat(null);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }, []); // `id` is not a dependency here, it's passed as an argument.

  // Effect for initial load of chat data based on URL ID.
  useEffect(() => {
    if (router.isReady && id) {
      const chatIdNum = parseInt(id as string);
      if (!isNaN(chatIdNum)) {
        loadChat(chatIdNum);
      } else {
        setError({ type: 'notFound', message: `Invalid chat ID: ${id}`, status: 400 });
        setLoading(false);
      }
    }
  }, [id, router.isReady, loadChat]);

  // Effect to scroll to the bottom of messages list when new messages are added or streaming.
  useEffect(() => {
    scrollToBottom();
  }, [messages, isSendingInitial]); // Dependency on `isSendingInitial` for initial message stream

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Effect to handle sending an initial message if provided in query params.
  useEffect(() => {
    if (router.isReady && id && initialMessageQuery && !initialMessageSentRef.current) {
      const initialMessageContent = initialMessageQuery as string;
      const currentChatId = id as string;
      const chatIdNum = parseInt(currentChatId);

      if (isNaN(chatIdNum)) {
        setError({ type: 'notFound', message: `Invalid chat ID for initial message: ${currentChatId}`, status: 400 });
        setIsSendingInitial(false);
        initialMessageSentRef.current = true; // Mark as attempted
        // Clean up query param if it was processed or invalid
        if (router.query.initialMessage) {
            router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
        }
        return;
      }
      
      initialMessageSentRef.current = true; // Mark as processed
      setIsSendingInitial(true);

      const sendInitialMessageAndStreamAsync = async () => {
        try {
          // 1. Create the user's first message in the backend
          await chatService.createMessage({
            chat_id: chatIdNum,
            sender: 'user',
            content: initialMessageContent,
          });
          
          // Fetch chat again to get all messages including the new user message and its sequence.
          await loadChat(chatIdNum);

          // 2. Prepare for streaming AI response: Add a placeholder for the assistant's message.
          const assistantStreamingId = `assistant-streaming-initial-${Date.now()}`;
          const placeholderAssistantMessage: Message = {
            id: assistantStreamingId as any, // Temporary ID
            chat_id: chatIdNum,
            sender: 'assistant',
            content: '', // Starts empty, will be filled by stream
            timestamp: new Date().toISOString(),
            sequence_number: (messages.length > 0 ? Math.max(...messages.map(m => m.sequence_number)) : -1) + 2, // Placeholder sequence
          };
          
          // Add user message (if not already loaded by `loadChat`) and placeholder to UI
          setMessages(prev => {
            const userMessageExists = prev.some(m => m.content === initialMessageContent && m.sender === 'user');
            const newMessages = [...prev];
            if (!userMessageExists) {
              newMessages.push({ 
                id: `user-initial-${Date.now()}` as any, 
                chat_id: chatIdNum, 
                sender: 'user', 
                content: initialMessageContent, 
                timestamp: new Date().toISOString(), 
                sequence_number: (prev.length > 0 ? Math.max(...prev.map(m => m.sequence_number)) : -1) +1 
              });
            }
            newMessages.push(placeholderAssistantMessage);
            return newMessages;
          });


          // 3. Call askQuestion and process stream
          const response = await chatService.askQuestion({
            chat_id: chatIdNum,
            content: initialMessageContent,
          });

          if (!response.body) {
            throw new Error('Response body is null for initial message stream.');
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let done = false;

          while (!done) {
            const { value, done: readerDone } = await reader.read();
            done = readerDone;
            if (value) {
              const chunk = decoder.decode(value, { stream: true });
              setMessages(prevMessages =>
                prevMessages.map(msg =>
                  msg.id.toString() === assistantStreamingId
                    ? { ...msg, content: msg.content + chunk } // Append chunk to placeholder
                    : msg
                )
              );
            }
          }
        } catch (error: any) {
          console.error('Failed to send initial message or stream response:', error);
          message.error(extractErrorMessage(error).message || 'Failed to process initial message.');
           setMessages(prevMessages =>
            prevMessages.map(msg =>
              // Identify the placeholder by its temporary ID pattern and empty content
              (msg.id.toString().startsWith('assistant-streaming-initial-')) && msg.content === ''
                ? { ...msg, content: `Error: ${error.message || 'Failed to get AI response.'}` }
                : msg
            )
          );
        } finally {
          // Clean up the initialMessage query parameter from URL after processing.
          if (router.query.initialMessage === initialMessageContent) {
            router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
          }
          setIsSendingInitial(false);
          loadChat(chatIdNum); // Refresh message list from backend to get final state.
        }
      };
      sendInitialMessageAndStreamAsync();
    }
  }, [
    router.isReady,
    initialMessageQuery, // Use the destructured query param
    id,
    loadChat
  ]);


  // Handles sending a new message from the input bar.
  const handleSendMessage = async () => {
    if (!newMessage.trim() || !chat || sending || isSendingInitial) return;

    const userMessageContent = newMessage;
    setNewMessage(''); // Clear input immediately

    // Optimistically add user message to UI.
    const tempUserMessageId = `user-${Date.now()}`;
    const optimisticUserMessage: Message = {
      id: tempUserMessageId as any,
      chat_id: chat.id,
      sender: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString(),
      sequence_number: (messages.length > 0 ? Math.max(...messages.map(m => m.sequence_number)) : 0) + 1,
    };
    setMessages(prev => [...prev, optimisticUserMessage]);
    setSending(true);

    try {
      // 1. Save user message to backend.
      await chatService.createMessage({
        chat_id: chat.id,
        sender: 'user',
        content: userMessageContent,
      });

      // 2. Prepare for streaming AI response: Add placeholder.
      const assistantStreamingId = `assistant-streaming-${Date.now()}`;
      const placeholderAssistantMessage: Message = {
        id: assistantStreamingId as any,
        chat_id: chat.id,
        sender: 'assistant',
        content: '', // Start with empty content
        timestamp: new Date().toISOString(),
        sequence_number: optimisticUserMessage.sequence_number + 1,
      };
      setMessages(prev => [...prev, placeholderAssistantMessage]);

      // 3. Call askQuestion and process stream.
      const response = await chatService.askQuestion({
        chat_id: chat.id,
        content: userMessageContent,
      });

      if (!response.body) {
        throw new Error('Response body is null for streaming message.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          setMessages(prevMessages =>
            prevMessages.map(msg =>
              msg.id.toString() === assistantStreamingId
                ? { ...msg, content: msg.content + chunk }
                : msg
            )
          );
        }
      }
    } catch (error: any) {
      console.error('Failed to send message or stream response:', error);
      message.error(extractErrorMessage(error).message || 'Failed to process message.');
      // Update placeholder with error message if streaming failed.
      setMessages(prevMessages =>
        prevMessages.map(msg =>
          (msg.id.toString().startsWith('assistant-streaming-')) && msg.content === ''
            ? { ...msg, content: `Error: ${error.message || 'Failed to get AI response.'}` }
            : msg
        )
      );
    } finally {
      setSending(false);
      if (chat) {
        loadChat(chat.id); // Refresh message list from backend for final state.
      }
    }
  };

  // Copies message content to clipboard.
  const handleCopyMessage = (content: string) => {
    if (navigator.clipboard && window.isSecureContext) { // Check for secure context
      navigator.clipboard.writeText(content)
        .then(() => message.success('Copied to clipboard'))
        .catch(() => message.error('Failed to copy message'));
    } else {
      message.warning('Clipboard functionality is not available or requires a secure context (HTTPS).');
    }
  };

  // Renders the list of messages.
  const renderMessages = () => {
    return messages.map((msg) => {
      const isUser = msg.sender === 'user';
      // Class for styling based on sender (user or assistant)
      const bubbleContainerClass = isUser ? 'user-message-container' : 'assistant-message-container';

      const messageContainerStyles: React.CSSProperties = {
        position: 'relative', // For positioning copy button if needed
        display: 'inline-block', // Makes container only as wide as its content (Card)
      };

      return (
        <div
          key={msg.id} // Use message ID as key
          style={{
            display: 'flex',
            justifyContent: isUser ? 'flex-end' : 'flex-start', // Align messages
            marginBottom: 8, // Spacing between messages
            width: '100%',
          }}
        >
          <div
            className={`message-bubble-container ${bubbleContainerClass}`} // For global styles
            style={messageContainerStyles}
          >
            <Card
              className={isUser ? 'user-message-card' : 'assistant-message-card'} // For global styles
            >
              <Paragraph
              style={{
                margin: 0, // Remove default paragraph margin
                whiteSpace: 'pre-wrap', // Preserve line breaks and spaces
                wordBreak: 'break-word', // Break long words
              }}
              >
                {msg.content}
              </Paragraph>
            </Card>
            {/* Copy button for assistant messages */}
            {!isUser && msg.content && ( // Show copy button only for non-empty assistant messages
              <div
                className="copy-button-wrapper assistant-copy-button" // For global styles
                style={{
                  marginTop: '8px', // Spacing for copy button
                  marginLeft: '8px', // Align with message bubble
                }}
              >
                <Tooltip title="Copy message">
                  <Button
                    type="text"
                    icon={<CopyOutlined />}
                    size="small"
                    onClick={() => handleCopyMessage(msg.content)}
                  />
                </Tooltip>
              </div>
            )}
          </div>
        </div>
      );
    });
  };

  // Loading state for initial chat data.
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 120px)' /* Adjust height */ }}>
        <Spin size="large" tip="Loading chat..." />
      </div>
    );
  }

  // Error state if chat loading failed.
  if (error) {
    return (
      <div style={{ textAlign: 'center', marginTop: 50, padding: 20 }}>
        <Alert
          message={error.type === 'notFound' ? "Chat Not Found" : "Error Loading Chat"}
          description={error.message || "An unexpected error occurred."}
          type="error"
          showIcon
        />
        <Button type="primary" onClick={() => router.push('/chat')} style={{ marginTop: 20 }}>
          Return to Chat List
        </Button>
      </div>
    );
  }

  // State if chat data is successfully loaded but chat is null (e.g., not found after load).
  if (!chat) {
      return (
        <div style={{ textAlign: 'center', marginTop: 50, padding: 20 }}>
          <Empty description="The requested chat could not be found or has been deleted." />
          <Button type="primary" onClick={() => router.push('/chat')} style={{ marginTop: 20 }}>
            Return to Chat List
          </Button>
        </div>
      );
  }

  return (
    <>
      {/* Main container for chat messages and input bar */}
      <div style={{ width: '100%', maxWidth: '750px', margin: '0 auto', maxHeight: 'calc(100vh - 110px)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Message display area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 4px' }}>
          {messages.length === 0 && !isSendingInitial ? ( // Show empty state if no messages and not processing initial
            <div style={{ textAlign: 'center', marginTop: 40 }}>
              <Title level={4}>Chat with SmartInfo</Title>
              <Paragraph>Ask a question or start a conversation about your news items.</Paragraph>
            </div>
          ) : (
            renderMessages()
          )}
          <div ref={messagesEndRef} /> {/* Anchor for scrolling to bottom */}
        </div>

        {/* Chat input bar area */}
        <div style={{ paddingTop: '16px', paddingBottom: '8px', paddingLeft: 0, paddingRight: 0 }}>
          <ChatInputBar
            inputValue={newMessage}
            onInputChange={setNewMessage}
            onSendMessage={handleSendMessage}
            loading={sending || isSendingInitial} // Disable input when sending any message
          />
        </div>
      </div>
    </>
  );
};

export default withAuth(ChatPage); // Protect this page