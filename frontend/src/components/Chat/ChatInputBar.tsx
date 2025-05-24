/**
 * @file ChatInputBar.tsx
 * @description Defines the ChatInputBar component for message composition and sending.
 * This component provides a text area for input, a send button, and an optional
 * file attachment button.
 *
 * @file_purpose To provide a reusable UI element for chat input functionality across
 *               different chat views.
 */
import React from 'react';
import { Input, Button } from 'antd';
import { SendOutlined, PaperClipOutlined } from '@ant-design/icons';
import styles from '../../styles/ChatInputBar.module.css';

/**
 * @interface ChatInputBarProps
 * @description Defines the props for the ChatInputBar component.
 */
interface ChatInputBarProps {
  inputValue: string;                         // The current text content of the input area.
  onInputChange: (value: string) => void;     // Callback invoked when the text area content changes.
  onSendMessage: (message: string) => void;   // Callback invoked when the user intends to send the message.
  loading?: boolean;                          // [loading=false] If true, the input and send button are disabled.
}

/**
 * @component ChatInputBar
 * @description A reusable UI component for composing and sending chat messages.
 * It features a dynamically resizing text area for input, an optional file
 * attachment button, and a send button. Handles 'Enter' key (without Shift)
 * for message submission.
 *
 * @param {string} inputValue - The current text content of the input area.
 * @param {(value: string) => void} onInputChange - Callback invoked when the text area content changes.
 * @param {(message: string) => void} onSendMessage - Callback invoked when the user intends to send the message.
 * @param {boolean} [loading=false] - If true, the input and send button are disabled, indicating an ongoing operation.
 *
 * @returns {JSX.Element} The rendered chat input bar.
 *
 * @example
 * <ChatInputBar
 *   inputValue={currentMessage}
 *   onInputChange={setCurrentMessage}
 *   onSendMessage={handleSendMessage}
 *   loading={isSending}
 * />
 */
const ChatInputBar: React.FC<ChatInputBarProps> = ({
  inputValue,
  onInputChange,
  onSendMessage,
  loading,
}) => {
  const handleSendClick = () => {
    if (inputValue.trim()) {
      onSendMessage(inputValue.trim());
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendClick();
    }
  };

  return (
    <div className={styles.chatInputContainer}>
      <Input.TextArea
        value={inputValue}
        onChange={(e) => onInputChange(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Type your message..."
        autoSize={{ minRows: 1, maxRows: 5 }}
        className={styles.chatInputTextArea}
        disabled={loading}
        style={{ paddingRight: '80px' /* Add padding for buttons */ }}
      />
      {/* Container for buttons inside the textarea */}
      <div className={styles.inputButtonsContainer}>
        {/* Add file button */}
        <Button
          type="text"
          shape="circle"
          icon={<PaperClipOutlined />}
          // onClick handler will be added later if functionality is needed
          disabled={loading} // Disable if sending
          aria-label="Attach File"
          style={{ color: 'var(--text-secondary)' }} // Style button color
        />
        {/* Send message button */}
        <Button
          type="primary"
          shape="circle"
          icon={<SendOutlined />}
          onClick={handleSendClick}
          disabled={!inputValue.trim() || loading}
          className={styles.sendButton}
        />
      </div>
    </div>
  );
};

export default ChatInputBar;