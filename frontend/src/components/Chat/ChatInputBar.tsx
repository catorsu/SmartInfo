import React from 'react';
import { Input, Button } from 'antd';
import { SendOutlined, PaperClipOutlined } from '@ant-design/icons';
import styles from '../../styles/ChatInputBar.module.css';

interface ChatInputBarProps {
  inputValue: string;
  onInputChange: (value: string) => void;
  onSendMessage: (message: string) => void;
  loading?: boolean;
}

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
