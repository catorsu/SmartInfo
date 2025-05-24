/**
 * @file AnalysisModal.tsx
 * @description Defines a modal component for displaying news analysis content.
 * This component wraps the AnalysisWindowContent in an Ant Design Modal.
 *
 * @file_purpose To provide a reusable modal interface for news analysis.
 */
import React from 'react';
import { Modal } from 'antd';
import AnalysisWindowContent from './AnalysisWindowContent';

/**
 * @interface AnalysisModalProps
 * @description Defines the props for the AnalysisModal component.
 */
interface AnalysisModalProps {
  newsItemId: number;      // The ID of the news item to be analyzed or displayed.
  isOpen: boolean;         // Controls the visibility of the modal.
  onClose: () => void;     // Callback function invoked when the modal is requested to close.
}

/**
 * @component AnalysisModal
 * @description A modal dialog that displays the detailed analysis of a news item.
 * It utilizes the `AnalysisWindowContent` component to render the actual analysis.
 * The modal's visibility and closing behavior are controlled by props.
 *
 * @param {number} newsItemId - The ID of the news item for which analysis is displayed.
 * @param {boolean} isOpen - If true, the modal is visible.
 * @param {() => void} onClose - Callback function to handle the modal close event.
 *
 * @returns {JSX.Element} The rendered modal component.
 *
 * @example
 * <AnalysisModal
 *   newsItemId={123}
 *   isOpen={isModalOpen}
 *   onClose={handleCloseModal}
 * />
 */
const AnalysisModal: React.FC<AnalysisModalProps> = ({ newsItemId, isOpen, onClose }) => {
  return (
    <Modal
      open={isOpen}
      onCancel={onClose}
      footer={null}
      width={1000}
      styles={{ body: { padding: '0' } }}
      destroyOnClose={true}
      maskClosable={true}
    >
      <AnalysisWindowContent newsItemId={newsItemId} />
    </Modal>
  );
};

export default AnalysisModal;