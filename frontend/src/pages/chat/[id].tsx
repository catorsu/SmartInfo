import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import {
  Typography,
  Input,
  Button,
  Card,
  message,
  Spin,
  Tooltip
} from 'antd';
import {
  SendOutlined,
  CopyOutlined
} from '@ant-design/icons';
import { Chat, Message, MessageCreate } from '@/utils/types';
import * as chatService from '@/services/chatService';
import { extractErrorMessage } from '@/utils/apiErrorHandler';
import withAuth from '@/components/auth/withAuth';
import ChatInputBar from '@/components/Chat/ChatInputBar';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const ChatPage: React.FC = () => {
  const router = useRouter();
  const { id } = router.query;
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [isSendingInitial, setIsSendingInitial] = useState<boolean>(false);
  const [newMessage, setNewMessage] = useState('');
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageSentRef = useRef<boolean>(false); 

  const loadChat = useCallback(async (chatId: number) => {
    try {
      setLoading(true);
      setError(null);
      const chatData = await chatService.getChat(chatId);

      if (chatData === null) { 
      setChat(null);
        setMessages([]);
        setError({ type: 'notFound', message: `Chat session with ID ${chatId} not found or not owned by user.`, status: 404 });
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
  }, []); 

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

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSendingInitial]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (router.isReady && id && router.query.initialMessage && !initialMessageSentRef.current) {
      const initialMessageContent = router.query.initialMessage as string;
      const currentChatId = id as string;
      const chatIdNum = parseInt(currentChatId);

      if (!isNaN(chatIdNum)) {
        initialMessageSentRef.current = true; 
        setIsSendingInitial(true);

        const sendInitialMessageAsync = async () => {
          try {
            await chatService.createMessage({
              chat_id: chatIdNum,
              sender: 'user',
              content: initialMessageContent
            });

            await chatService.askQuestion({
              chat_id: chatIdNum,
              content: initialMessageContent,
            });

            await loadChat(chatIdNum);

          } catch (error) {
            console.error('Failed to send initial message or get response:', error);
            message.error(extractErrorMessage(error).message || 'Failed to send initial message.');
          } finally {
            if (router.query.initialMessage === initialMessageContent) {
                router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
            }
            setIsSendingInitial(false);
          }
        };
        sendInitialMessageAsync();
      } else {
        setError({ type: 'notFound', message: `Invalid chat ID for initial message: ${currentChatId}`, status: 400 });
        setIsSendingInitial(false);
        initialMessageSentRef.current = true; 
        if (router.query.initialMessage) {
            router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
        }
      }
    }
  }, [
    router.isReady,
    router.query.initialMessage, // Depend explicitly on the query parameter
    id,                          // Depend on the chat ID from the path
    loadChat                     // loadChat is memoized
  ]);


  const handleSendMessage = async () => {
    if (!newMessage.trim() || !chat || sending || isSendingInitial) return;

    const userMessageData: MessageCreate = {
      chat_id: chat.id,
      sender: 'user',
      content: newMessage
    };

    try {
      setSending(true);

      const messageContent = newMessage;
      setNewMessage('');

      // The ChatInputBar component will manage its own internal focus if needed.
      // Focus logic previously tied to textAreaRef is removed.

      await chatService.createMessage(userMessageData);

      await chatService.askQuestion({
        chat_id: chat.id,
        content: messageContent, // Use the stored content
      });

      await loadChat(chat.id);

    } catch (error) {
      console.error('Failed to send message:', error);
      message.error(extractErrorMessage(error).message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const handleCopyMessage = (content: string) => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(content)
        .then(() => message.success('Copied to clipboard'))
        .catch(() => message.error('Failed to copy message'));
    } else {
      message.error('Clipboard functionality is not available in this browser or context');
    }
  };

  const renderMessages = () => {
    return messages.map((msg) => {
      const isUser = msg.sender === 'user';

      return (
        <div
          key={msg.id}
          // className="message-row" // Retained for alignment if used
          style={{
            display: 'flex',
            justifyContent: isUser ? 'flex-end' : 'flex-start',
            marginBottom: 12,
          }}
        >
          <div
            className={`message-bubble-container ${isUser ? 'user-message-container' : 'assistant-message-container'}`}
            style={{
              position: 'relative',
              display: 'inline-block', // Keeps bubble tight to content
            }}
          >
            <Card
              className={isUser ? 'user-message-card' : 'assistant-message-card'}
              style={{ maxWidth: '80%' }} // MaxWidth on card itself is fine
              bodyStyle={{ padding: '10px 14px 30px 35px' }}
            >
              <Paragraph style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: 0 }}>
                {msg.content}
              </Paragraph>
            </Card>
            <div
              className="copy-button-wrapper" // Class for styling via <style jsx>
              style={{
                position: 'absolute',
                bottom: '8px',
                left: '8px',
                // Opacity & visibility controlled by CSS via class a few lines below
                transition: 'opacity 0.2s ease-in-out, visibility 0.2s ease-in-out',
                zIndex: 1,
              }}
            >
              <Tooltip title="Copy message">
                <Button
                  type="text"
                  icon={<CopyOutlined />}
                  size="small"
                  onClick={() => handleCopyMessage(msg.content)}
                  style={{ color: 'var(--text-secondary)', padding: '0 4px' }}
                />
              </Tooltip>
            </div>
          </div>
        </div>
      );
    });
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', marginTop: 50 }}>
        {error.type === 'notFound' ? (
          <>
            <Title level={3}>Chat Not Found</Title>
            <Paragraph>{error.message || "The requested chat could not be found or access is denied."}</Paragraph>
          </>
        ) : error.type === 'forbidden' ? (
            <>
            <Title level={3}>Access Denied</Title>
            <Paragraph>{error.message || "You do not have permission to view this chat."}</Paragraph>
          </>
        ) : (
          <>
            <Title level={3}>Error Loading Chat</Title>
            <Paragraph>{error.message || "An unexpected error occurred while loading the chat."}</Paragraph>
          </>
        )}
        <Button type="primary" onClick={() => router.push('/chat')}>
          Return to Chat List
        </Button>
      </div>
    );
  }

  // If not loading and no error, check if chat data exists
  if (!chat) {
      return (
        <div style={{ textAlign: 'center', marginTop: 50 }}>
          <Title level={3}>Chat Not Found</Title>
          <Paragraph>The requested chat could not be found or has been deleted.</Paragraph>
          <Button type="primary" onClick={() => router.push('/chat')}>
            Return to Chat List
          </Button>
        </div>
      );
  }

  return (
    <>
      <style jsx>{`
        .message-bubble-container .copy-button-wrapper {
          opacity: 0;
          visibility: hidden;
        }
        .message-bubble-container:hover .copy-button-wrapper {
          opacity: 1;
          visibility: visible;
        }
        /* Optional: if you want different background for user/assistant for the card itself */
        /* These would typically be in global.css or theme if Ant variables are used */
        /*
        .user-message-container .ant-card {
           background-color: var(--user-message-bg, #e6f7ff);
        }
        .assistant-message-container .ant-card {
           background-color: var(--assistant-message-bg, #f0f0f0);
        }
        */
      `}</style>
      <div style={{ width: '100%', maxWidth: '750px', margin: '0 auto', maxHeight: '85vh', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 4px' }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', marginTop: 40 }}>
              <Title level={4}>Start a conversation</Title>
              <Paragraph>Ask a question or start a conversation with the AI assistant.</Paragraph>
            </div>
          ) : (
            renderMessages()
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ paddingTop: '16px', paddingBottom: '8px', paddingLeft: 0, paddingRight: 0 }}>
          <ChatInputBar
            inputValue={newMessage}
            onInputChange={setNewMessage}
            onSendMessage={handleSendMessage}
            loading={sending || isSendingInitial}
          />
        </div>
      </div>
    </>
  );
};

export default withAuth(ChatPage);
