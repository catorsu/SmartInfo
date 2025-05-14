// frontend/src/components/analysis/AnalysisWindowContent.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { Typography, Spin, Alert, Space, Divider, Empty, Tooltip, Button } from 'antd';
import { LinkOutlined, ExperimentOutlined } from '@ant-design/icons';
import { NewsItem } from '@/utils/types'; // Assuming NewsItem might still be fetched for metadata
import * as newsService from '@/services/newsService';
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';
import analysisStreamManager from '@/streaming/AnalysisStreamManager'; // IMPORT THE NEW MANAGER

const { Title, Text, Paragraph } = Typography;

interface AnalysisWindowContentProps {
  newsItemId: number;
  newsItemTitle?: string; // Optional: If title is passed from parent
  newsItemDate?: string;
  newsItemSourceName?: string;
  newsItemUrl?: string;
  newsItemSummary?: string;
  startAnalysisImmediately?: boolean;
}

const FIXED_CONTENT_HEIGHT = '65vh';

const AnalysisWindowContent: React.FC<AnalysisWindowContentProps> = ({
  newsItemId,
  newsItemTitle,
  newsItemDate,
  newsItemSourceName,
  newsItemUrl,
  newsItemSummary,
  startAnalysisImmediately,
}) => {
  // State for news item details (if not passed as props or to supplement)
  const [fetchedNewsItem, setFetchedNewsItem] = useState<NewsItem | null>(null);
  const [isItemLoading, setIsItemLoading] = useState<boolean>(true); // For loading the news item itself
  const [itemError, setItemError] = useState<string | null>(null);

  // State for analysis stream, driven by the manager
  const [analysisContent, setAnalysisContent] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Determine display values, preferring props if available
  const displayTitle = newsItemTitle ?? fetchedNewsItem?.title;
  const displayDate = newsItemDate ?? fetchedNewsItem?.date;
  const displaySourceName = newsItemSourceName ?? fetchedNewsItem?.source_name;
  const displayUrl = newsItemUrl ?? fetchedNewsItem?.url;
  const displaySummary = newsItemSummary ?? fetchedNewsItem?.summary;
  const displayAnalysis = fetchedNewsItem?.analysis; // Original analysis from fetched item

  // Callback for stream manager updates
  const handleManagerStateUpdate = useCallback((newState: {
    content: string;
    isStreaming: boolean;
    isComplete: boolean;
    error: string | null;
  }) => {
    // console.log(`[AnalysisWindowContent] Received manager update for ${newsItemId}:`, newState);
    setAnalysisContent(newState.content);
    setIsStreaming(newState.isStreaming);
    setIsComplete(newState.isComplete);
    setStreamError(newState.error);
    if (newState.isStreaming) {
      setIsItemLoading(false); // If streaming starts, item loading part is done
    }
  }, [newsItemId]);


  useEffect(() => {
    // Fetch news item details if not all provided via props,
    // or if we need to check for pre-existing analysis on the item.
    const fetchNewsItemDetails = async () => {
        if (!newsItemId) return;
        setIsItemLoading(true);
        setItemError(null);
        setFetchedNewsItem(null); // Reset

        // Reset stream states as well, as they are tied to newsItemId
        setAnalysisContent('');
        setIsStreaming(false);
        setIsComplete(false);
        setStreamError(null);

        try {
            const item = await newsService.getNewsById(newsItemId);
            if (!item) {
                setItemError(`News item with ID ${newsItemId} not found.`);
                setFetchedNewsItem(null);
            } else {
                setFetchedNewsItem(item);
                // If the item has pre-existing analysis and we are not told to start immediately,
                // display it. The manager will handle if a stream for this item already exists.
                if (item.analysis && !startAnalysisImmediately) {
                    setAnalysisContent(item.analysis);
                    setIsComplete(true); // Mark as complete if displaying pre-existing
                }
            }
        } catch (err) {
            const errorDetails = extractErrorMessage(err);
            setItemError(errorDetails.message || "Failed to load news item details.");
            console.error("Failed to fetch news item:", err);
        } finally {
            setIsItemLoading(false);
        }
    };

    fetchNewsItemDetails();
  }, [newsItemId]);


  useEffect(() => {
    if (!newsItemId || isItemLoading) { // Don't subscribe or initiate until item details are attempted/loaded
        return;
    }

    // Subscribe to the stream manager for this news item
    analysisStreamManager.subscribe(newsItemId, handleManagerStateUpdate);

    // Get initial state from manager (e.g., if stream was already active from another component/tab)
    const initialState = analysisStreamManager.getStreamStateSnapshot(newsItemId);
    if (initialState) {
        // console.log(`[AnalysisWindowContent] Initial state from manager for ${newsItemId}:`, initialState);
        handleManagerStateUpdate(initialState);
    }

    // Logic to auto-start analysis if prop is set and conditions are met
    // This should happen *after* initial state is potentially set from manager
    if (startAnalysisImmediately) {
        const currentSnapshot = analysisStreamManager.getStreamStateSnapshot(newsItemId);
        const shouldInitiate = !currentSnapshot || (!currentSnapshot.isStreaming && currentSnapshot.isComplete); // Start if no stream or if completed (allows re-analysis if startImmediately is true)

        if (shouldInitiate) {
            // console.log(`[AnalysisWindowContent] ${newsItemId}: startAnalysisImmediately=true. Initiating stream (forceRestart=false).`);
            analysisStreamManager.initiateStream(newsItemId, false); // false = don't force if already active from another source/tab
        } else if (currentSnapshot && currentSnapshot.isStreaming) {
            // console.log(`[AnalysisWindowContent] ${newsItemId}: startAnalysisImmediately=true, but stream already active. Component will display it.`);
        } else if (currentSnapshot && !currentSnapshot.isStreaming && !currentSnapshot.isComplete) {
             // console.log(`[AnalysisWindowContent] ${newsItemId}: startAnalysisImmediately=true, stream exists but not active and not complete (e.g. initial empty state). Initiating stream.`);
             analysisStreamManager.initiateStream(newsItemId, false);
        }
    } else if (fetchedNewsItem?.analysis && (!initialState || !initialState.content) && !initialState?.isStreaming) {
        // If not starting immediately, but fetched item has analysis, and manager has no content/stream for it,
        // set the analysis content from fetched item.
        setAnalysisContent(fetchedNewsItem.analysis);
        setIsComplete(true);
        setIsStreaming(false);
    }


    // Cleanup on unmount or when newsItemId changes
    return () => {
      // console.log(`[AnalysisWindowContent] Unsubscribing for newsItemId ${newsItemId}`);
      analysisStreamManager.unsubscribe(newsItemId, handleManagerStateUpdate);
    };
  }, [newsItemId, startAnalysisImmediately, handleManagerStateUpdate, isItemLoading, fetchedNewsItem]); // Added fetchedNewsItem to deps


  const handleForceAnalysis = () => {
    if (!newsItemId) return;
    // console.log(`[AnalysisWindowContent] Forcing analysis for newsItemId ${newsItemId}`);
    setStreamError(null); // Clear previous stream errors
    // Content, isStreaming, isComplete will be updated by the manager via subscription
    analysisStreamManager.initiateStream(newsItemId, true); // true for forceRestart
  };

  // Combined loading state: true if item is loading OR (if item is loaded but stream is starting and no content yet)
  const showInitialLoadingSpinner = isItemLoading || (isStreaming && !analysisContent && !streamError);

  if (showInitialLoadingSpinner && !itemError) {
    return (
      <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        <Spin size="large" tip={isItemLoading ? "Loading news item..." : "Initiating analysis..."} />
      </div>
    );
  }

  if (itemError) { // Error fetching the item itself
    return (
      <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        <Empty description={itemError} />
      </div>
    );
  }

  if (!displayTitle && !isItemLoading) { // No item details could be loaded (and not because it's still loading)
     return (
        <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <Empty description="News item details could not be loaded." />
        </div>
      );
  }

  // Display stream-specific error if one occurred
  if (streamError) {
    return (
      <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        <Alert
          message="Analysis Error"
          description={streamError}
          type="error"
          showIcon
          style={{ marginBottom: '20px' }}
        />
        <Button onClick={handleForceAnalysis}>Try Re-analyzing</Button>
      </div>
    );
  }

  return (
    <div style={{
      height: FIXED_CONTENT_HEIGHT,
      display: 'flex',
      flexDirection: 'column',
      padding: '20px',
      overflow: 'hidden'
    }}>
      {displayTitle && (
        <div style={{ flexShrink: 0 }}>
          <Title level={4} style={{ marginBottom: '8px', marginTop: 0 }}>{displayTitle}</Title>
          <Space size={16} wrap style={{ marginBottom: '12px', fontSize: '12px' }}>
            {displayDate && <Text type="secondary">{new Date(displayDate).toLocaleDateString()}</Text>}
            {displaySourceName && (
              <Text type="secondary">{displaySourceName}</Text>
            )}
            {displayUrl && (
              <Tooltip title="View Original Source">
                <a href={displayUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', display: 'inline-flex', alignItems: 'center' }}>
                  <LinkOutlined />
                </a>
              </Tooltip>
            )}
            {/* Show analyze button if not streaming and (either no content or analysis has an error or is incomplete) */}
            {(!isStreaming || streamError) && (
              <Tooltip title={analysisContent ? "Re-analyze News" : "Analyze News"}>
                <Button
                  type="text"
                  icon={<ExperimentOutlined style={{ color: 'var(--accent-color)', fontSize: '15px' }} />}
                  onClick={handleForceAnalysis}
                  loading={isStreaming && !streamError} // Only show loading if actively trying to stream without error
                  style={{ padding: '0 4px', color: 'var(--accent-color)', marginLeft: '8px' }}
                  size="small"
                />
              </Tooltip>
            )}
          </Space>
          {displaySummary && <Paragraph type="secondary" style={{ marginBottom: '12px' }}>{displaySummary}</Paragraph>}
          <Divider style={{ marginTop: '0px', marginBottom: '12px' }} />
        </div>
      )}

      <div style={{
        flexGrow: 1,        
        overflowY: 'auto',   
        minHeight: 0,       
        paddingRight: '8px',
      }}>
          {analysisContent ? (
            <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
              {analysisContent}
            </Paragraph>
          ) : !isStreaming && isComplete && !streamError ? ( // Completed but no content
             <Empty description="Analysis complete, but no content was generated." image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : null }


          {isStreaming && !streamError && ( // Show streaming indicator only if actively streaming and no error
            <div style={{ textAlign: 'left', padding: '10px 0 0 0', color: 'var(--text-secondary)' }}>
              <Spin size="small" style={{ marginRight: '8px' }} />
              <em>Streaming analysis...</em>
            </div>
          )}

          {/* Fallback Empty state if no content, not streaming, and not explicitly completed empty */}
          {!analysisContent && !isStreaming && (!isComplete || streamError) && (
              <Empty 
                description={
                  <>
                    No analysis available. 
                    {displayTitle && <>Click the <ExperimentOutlined style={{ color: 'var(--accent-color)'}}/> icon in the header to generate one.</>}
                  </>
                }
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
          )}
      </div>
    </div>
  );
};

export default AnalysisWindowContent;