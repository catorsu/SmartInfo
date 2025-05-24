/**
 * @file DefaultChatView.tsx
 * @description Defines the DefaultChatView component, displayed when no specific
 * chat session is selected. It provides a welcome message and suggestions.
 *
 * @file_purpose To provide a welcoming and suggestive UI for initiating new chat
 *               conversations or guiding the user.
 */
import React from 'react';
import { Typography, Button, Space, Row, Col } from 'antd';
import ChatInputBar from './ChatInputBar';
import styles from '../../styles/DefaultChatView.module.css';

const { Title, Text } = Typography;

/**
 * @interface DefaultChatViewProps
 * @description Defines the props for the DefaultChatView component.
 */
interface DefaultChatViewProps {
  username: string;                                 // The name of the user for a personalized greeting.
  onSuggestionClick: (suggestion: string) => void;  // Callback when a suggestion button is clicked.
  inputValue: string;                               // Current value for the chat input bar.
  onInputChange: (value: string) => void;           // Callback for chat input bar changes.
  onSendMessage: (message: string) => void;         // Callback to send a message from the chat input bar.
  loading?: boolean;                                // [loading=false] Loading state for the chat input bar.
}

/**
 * @component DefaultChatView
 * @description A component displayed when no specific chat is active. It greets the
 * user, offers conversation starter suggestions, and includes a `ChatInputBar`
 * for initiating a new chat.
 *
 * @param {string} username - The name of the currently logged-in user to personalize the greeting.
 * @param {(suggestion: string) => void} onSuggestionClick - Callback invoked when a suggestion button is clicked.
 * @param {string} inputValue - The current text content for the shared input area (passed to ChatInputBar).
 * @param {(value: string) => void} onInputChange - Callback for changes in the shared input area (passed to ChatInputBar).
 * @param {(message: string) => void} onSendMessage - Callback to handle sending a message from the shared input area (passed to ChatInputBar).
 * @param {boolean} [loading=false] - If true, indicates an ongoing operation, typically disabling the input bar.
 *
 * @returns {JSX.Element} The rendered default chat view.
 *
 * @example
 * <DefaultChatView
 *   username="Alice"
 *   onSuggestionClick={handleSuggestion}
 *   inputValue={currentMessage}
 *   onInputChange={setCurrentMessage}
 *   onSendMessage={handleSend}
 *   loading={isSending}
 * />
 */
const DefaultChatView: React.FC<DefaultChatViewProps> = ({
  username,
  onSuggestionClick,
  inputValue,
  onInputChange,
  onSendMessage,
  loading,
}) => {
  const suggestions = [
    "Summarize today's top news.",
    "Analyze an article...",
    "What are the latest updates on AI?",
  ];

  return (
    <div className={styles.defaultChatViewContainer}>
      <div className={styles.greetingArea}>
        <Title level={2} className={styles.greetingTitle}>
          Hello, {username}.
        </Title>
        <Text type="secondary" className={styles.subGreeting}>
          What can SmartInfo help you with today?
        </Text>
      </div>

      <div className={styles.suggestionsArea}>
        <Row gutter={[16, 16]} justify="center">
          {suggestions.map((suggestion, index) => (
            <Col key={index}>
              <Button
                className={styles.suggestionCard}
                onClick={() => onSuggestionClick(suggestion)}
              >
                {suggestion}
              </Button>
            </Col>
          ))}
        </Row>
      </div>

      <div className={styles.chatInputArea}>
        <ChatInputBar
          inputValue={inputValue}
          onInputChange={onInputChange}
          onSendMessage={onSendMessage}
          loading={loading}
        />
      </div>
    </div>
  );
};

export default DefaultChatView;