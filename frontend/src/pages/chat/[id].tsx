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

  // Modified useEffect for initialMessage to support streaming
  useEffect(() => {
    if (router.isReady && id && router.query.initialMessage && !initialMessageSentRef.current) {
      const initialMessageContent = router.query.initialMessage as string;
      const currentChatId = id as string; // This is the NEW chat ID created by the previous page
      const chatIdNum = parseInt(currentChatId);

      if (isNaN(chatIdNum)) {
        setError({ type: 'notFound', message: `Invalid chat ID for initial message: ${currentChatId}`, status: 400 });
        setIsSendingInitial(false);
        initialMessageSentRef.current = true;
        if (router.query.initialMessage) {
            router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
        }
        return;
      }
      
      initialMessageSentRef.current = true;
      setIsSendingInitial(true);

      const sendInitialMessageAndStreamAsync = async () => {
        try {
          // 1. Create the user's first message in the backend
          await chatService.createMessage({
            chat_id: chatIdNum,
            sender: 'user',
            content: initialMessageContent,
          });
          
          // Optimistically add user message to UI (or wait for loadChat below)
          // For simplicity with initial message, we'll let loadChat handle it after streaming.

          // 2. Prepare for streaming AI response
          const assistantStreamingId = `assistant-streaming-initial-${Date.now()}`;
          const placeholderAssistantMessage: Message = {
            id: assistantStreamingId as any,
            chat_id: chatIdNum,
            sender: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            // Sequence number will be fixed by loadChat
            sequence_number: 1, // Assuming user message is 0 or will be set by backend
          };
          // Add user message and placeholder to UI if chat is loaded
          // This part is tricky because `loadChat` might not have run yet to set `chat`
          // For now, we'll add the placeholder directly and rely on `loadChat` in finally to correct sequence.
          // A better approach might be to ensure `chat` is loaded before this effect runs or pass chat data.
          
          // Let's fetch the chat first to ensure we have messages context if any (though unlikely for initial)
          await loadChat(chatIdNum); // This will set `messages` state

          setMessages(prev => [
            ...prev.filter(m => m.content !== initialMessageContent || m.sender !== 'user'), // remove potential duplicates if any
            { 
              id: `user-initial-${Date.now()}` as any, 
              chat_id: chatIdNum, 
              sender: 'user', 
              content: initialMessageContent, 
              timestamp: new Date().toISOString(), 
              sequence_number: (prev.length > 0 ? Math.max(...prev.map(m => m.sequence_number)) : -1) +1 
            },
            placeholderAssistantMessage
          ]);


          // 3. Call askQuestion and process stream
          const response = await chatService.askQuestion({ // This is the new askQuestion
            chat_id: chatIdNum,
            content: initialMessageContent,
          });

          if (!response.body) {
            throw new Error('Response body is null for initial message');
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
                  msg.id === assistantStreamingId
                    ? { ...msg, content: msg.content + chunk }
                    : msg
                )
              );
            }
          }
        } catch (error: any) {
          console.error('Failed to send initial message or stream response:', error);
          message.error(extractErrorMessage(error).message || 'Failed to process initial message.');
           //const assistantStreamingId = `assistant-streaming-initial-${Date.now()}`; // This ID might be different
           setMessages(prevMessages =>
            prevMessages.map(msg =>
              (msg.id.toString().startsWith('assistant-streaming-initial-')) && msg.content === ''
                ? { ...msg, content: `Error: ${error.message || 'Failed to get response'}` }
                : msg
            )
          );
        } finally {
          if (router.query.initialMessage === initialMessageContent) {
            router.replace(`/chat/${currentChatId}`, undefined, { shallow: true });
          }
          setIsSendingInitial(false);
          loadChat(chatIdNum); // Refresh message list from backend
        }
      };
      sendInitialMessageAndStreamAsync();
    }
  }, [
    router.isReady,
    router.query.initialMessage,
    id,
    loadChat // loadChat is memoized
    // Removed `chat` from dependencies as it might cause re-runs if loadChat updates it.
  ]);


  // Modified handleSendMessage for streaming
  const handleSendMessage = async () => {
    if (!newMessage.trim() || !chat || sending || isSendingInitial) return;

    const userMessageContent = newMessage;
    setNewMessage(''); // Clear input immediately

    // Optimistically add user message to UI
    // Backend createMessage will be called before streaming AI response
    const tempUserMessageId = `user-${Date.now()}`;
    const optimisticUserMessage: Message = {
      id: tempUserMessageId as any, // Temporary ID
      chat_id: chat.id,
      sender: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString(),
      sequence_number: (messages.length > 0 ? Math.max(...messages.map(m => m.sequence_number)) : 0) + 1,
    };
    setMessages(prev => [...prev, optimisticUserMessage]);
    setSending(true);

    try {
      // 1. Save user message to backend
      await chatService.createMessage({
        chat_id: chat.id,
        sender: 'user',
        content: userMessageContent,
      });
      // Optionally, refresh chat here to get the real user message ID, or wait till end.
      // For now, we'll rely on the final loadChat.

      // 2. Prepare for streaming AI response
      const assistantStreamingId = `assistant-streaming-${Date.now()}`;
      const placeholderAssistantMessage: Message = {
        id: assistantStreamingId as any, // Temporary ID
        chat_id: chat.id,
        sender: 'assistant',
        content: '', // Start with empty content
        timestamp: new Date().toISOString(),
        sequence_number: optimisticUserMessage.sequence_number + 1,
      };
      setMessages(prev => [...prev, placeholderAssistantMessage]);

      // 3. Call askQuestion and process stream
      const response = await chatService.askQuestion({
        chat_id: chat.id,
        content: userMessageContent,
      });

      if (!response.body) {
        throw new Error('Response body is null');
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
              msg.id === assistantStreamingId
                ? { ...msg, content: msg.content + chunk }
                : msg
            )
          );
        }
      }
    } catch (error: any) {
      console.error('Failed to send message or stream response:', error);
      message.error(extractErrorMessage(error).message || 'Failed to process message.');
      // Update placeholder with error message
      // const assistantStreamingId = `assistant-streaming-${Date.now()}`; // This ID might be different if error occurs before placeholder is set.
                                                                      // It's better to find the existing placeholder if one was added.
      setMessages(prevMessages =>
        prevMessages.map(msg =>
          (msg.id.toString().startsWith('assistant-streaming-')) && msg.content === '' // A way to find the placeholder
            ? { ...msg, content: `Error: ${error.message || 'Failed to get response'}` }
            : msg
        )
      );
    } finally {
      setSending(false);
      if (chat) { // Ensure chat is not null
        loadChat(chat.id); // Refresh message list from backend
      }
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
      const bubbleContainerClass = isUser ? 'user-message-container' : 'assistant-message-container';

      // This style is for the div that directly wraps the Card and the copy button.
      // `display: 'inline-block'` makes this container only as wide as its content (the Card).
      const messageContainerStyles: React.CSSProperties = {
        position: 'relative',
        display: 'inline-block', 
      };

      return (
        <div
          key={msg.id}
          style={{
            display: 'flex',
            justifyContent: isUser ? 'flex-end' : 'flex-start',
            marginBottom: 8,
            width: '100%',
          }}
        >
          <div
            className={`message-bubble-container ${bubbleContainerClass}`}
            style={messageContainerStyles}
          >
            <Card
              className={isUser ? 'user-message-card' : 'assistant-message-card'}
            >
              <Paragraph
              style={{
                margin: 0,
              }}
              >
                {msg.content}
              </Paragraph>
            </Card>
            {!isUser && (
              <div
                className="copy-button-wrapper assistant-copy-button"
                style={{
                  marginTop: '8px',
                  marginLeft: '8px',
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
      {/* Removed the <style jsx> block that was here */}
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
