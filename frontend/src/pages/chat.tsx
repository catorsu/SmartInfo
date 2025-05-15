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
import { Chat, Message, Question } from '@/utils/types';
import withAuth from '@/components/auth/withAuth';
import DefaultChatView from '@/components/Chat/DefaultChatView';

const { Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

import { useAuth } from '@/context/AuthContext';

const ChatPageInternal: React.FC = () => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [isProcessingFirstMessage, setIsProcessingFirstMessage] = useState<boolean>(false); 
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null); 

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { refreshChatList } = useAuth();
  useEffect(() => {
    fetchChats();
  }, []);

  useEffect(() => {
    if (selectedChatId) {
      fetchMessages(selectedChatId);
    } else {
      setMessages([]);
    }
  }, [selectedChatId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchChats = async () => {
    try {
      setLoadingChats(true);
      setError(null);
      const response = await chatService.getChats();
      setChats(response);


    } catch (err: any) {
      console.error('Failed to fetch chats:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setLoadingChats(false);
    }
  };

  const fetchMessages = async (chatId: number) => {
    try {
      setLoadingMessages(true);
      setError(null);
      const response = await chatService.getMessages(chatId);
      setMessages(response);
    } catch (err: any) {
      console.error('Failed to fetch messages:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setLoadingMessages(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) {
      return;
    }

    if (selectedChatId === null) {
      setIsProcessingFirstMessage(true); 
      const originalInputMessage = inputMessage;

      try {
        const newChat = await chatService.createChat({ title: originalInputMessage.substring(0, 50) + '...' });

        setInputMessage('');

        router.replace({
          pathname: `/chat/${newChat.id}`,
          query: { initialMessage: originalInputMessage }
        });

        refreshChatList();

      } catch (error) {
        console.error('Failed to create new chat session:', error);
        handleApiError(error, 'Failed to create new chat session');
        setIsProcessingFirstMessage(false);
      }

    } else {

      const userMessageObj: Message = {
        id: Date.now(),
        chat_id: selectedChatId,
        sender: 'user',
        content: inputMessage,
        timestamp: new Date().toISOString(),
        sequence_number: messages.length + 1
      };

      try {
        setSending(true);

        setMessages(prev => [...prev, userMessageObj]);
        setInputMessage('');

        await chatService.createMessage({
          chat_id: selectedChatId,
          sender: 'user',
          content: inputMessage
        });

        const question: Question = {
          chat_id: selectedChatId,
          content: inputMessage
        };

        const answer = await chatService.askQuestion(question);

        const assistantMessageObj: Message = {
          id: answer.message_id || Date.now() + 1,
          chat_id: selectedChatId,
          sender: 'assistant',
          content: answer.content,
          timestamp: new Date().toISOString(),
          sequence_number: messages.length + 2
        };

        setMessages(prev => [...prev, assistantMessageObj]);

        await fetchMessages(selectedChatId);

      } catch (error) {
        console.error('Failed to send message to existing chat:', error);
        handleApiError(error, 'Failed to send message');
      } finally {
        setSending(false);
      }
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCopyMessage = (content: string) => {
    navigator.clipboard.writeText(content)
      .then(() => message.success('复制成功'))
      .catch(() => message.error('复制失败'));
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputMessage(suggestion);
  };

  const handleDefaultViewInputChange = (value: string) => {
    setInputMessage(value);
  };

  // TODO: Replace with actual username from authentication context or state
  const username = "User";

  return (

    <div style={{
      height: '100%', // Fill the parent Content area from MainLayout
      display: 'flex',
      flexDirection: 'column',
      // background: '#fff', // Removed explicit background
      padding: 24,
      borderRadius: 8,
    }}>
      {error ? (
        error.type === 'notFound' ? (
          <Empty description={error.message || "Chat or messages not found."} style={{ margin: '60px 0' }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : error.type === 'forbidden' ? (
          <Alert
            message="Access Denied"
            description={error.message || "You do not have permission to view this chat."}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
          />
        ) : (
          <Alert
            message="Error"
            description={error.message || "An unexpected error occurred."}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )
      ) : (
        selectedChatId === null ? (
          <DefaultChatView
            username={username} // Use the placeholder username
            onSuggestionClick={handleSuggestionClick}
            inputValue={inputMessage}
            onInputChange={handleDefaultViewInputChange} // Use the new handler
            onSendMessage={handleSendMessage}
            loading={isProcessingFirstMessage} // Pass the new loading state
        />
        ) : (
          <>

            <div
              style={{
                flexGrow: 1,
                overflowY: 'auto',
                padding: '0 16px',
                marginBottom: 16,
                border: '1px solid #f0f0f0',
                borderRadius: 4
              }}
              ref={messageListRef}
            >
              {loadingMessages ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
                  <Spin size="large" />
                </div>
              ) : messages.length === 0 ? (
                <Empty
                  description="没有消息"
                  style={{ margin: '60px 0' }}
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              ) : (
                <div style={{ padding: '16px 0' }}>
                  {messages.map((msg) => {
                    const isUser = msg.sender === 'user';
                    return (
                      <div
                        key={msg.id}
                        style={{
                          display: 'flex',
                          justifyContent: isUser ? 'flex-end' : 'flex-start',
                          marginBottom: 16,
                        }}
                      >
                        <Card
                          className={isUser ? 'user-message-card' : 'assistant-message-card'}
                          style={{ maxWidth: '75%' }}
                          bodyStyle={{ padding: '10px 14px' }}
                        >
                          <Space align="start" size={8}>
                            {!isUser && (
                              <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#788596' }} />
                            )}
                            <div style={{ flex: 1 }}>
                              <Paragraph style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: 4 }}>
                                {msg.content}
                              </Paragraph>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Text type="secondary" style={{ fontSize: '11px' }}>
                                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                </Text>
                                <Tooltip title="Copy message">
                                  <Button
                                    type="text"
                                    icon={<CopyOutlined />}
                                    size="small"
                                    onClick={() => handleCopyMessage(msg.content)}
                                    style={{color: 'var(--text-secondary)', padding: '0 4px'}}
                                  />
                                </Tooltip>
                              </div>
                            </div>
                            {isUser && (
                              <Avatar icon={<UserOutlined />} style={{ backgroundColor: 'var(--accent-color)' }} />
                            )}
                          </Space>
                        </Card>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>


            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <TextArea
                value={inputMessage}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="输入消息..."
                autoSize={{ minRows: 2, maxRows: 6 }}
                style={{ flex: 1, marginRight: 8 }}
                disabled={sending}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                loading={sending} 
                disabled={!inputMessage.trim() || sending}
                style={{ height: 'auto', padding: '8px 16px' }}
              >
                发送
              </Button>
            </div>
          </>
        )
      )}
    </div>
  );
};

const ChatPage = withAuth(ChatPageInternal);
export default ChatPage;
