import React, { useState, useEffect } from 'react';
import { Typography, Spin, Alert, Space, Divider, Empty, Tooltip, Button } from 'antd';
import { LinkOutlined, ExperimentOutlined } from '@ant-design/icons';
import { NewsItem } from '@/utils/types';
import * as newsService from '@/services/newsService';
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';

const { Title, Text, Paragraph } = Typography;

interface AnalysisWindowContentProps {
  newsItemId: number;
}

const FIXED_CONTENT_HEIGHT = '65vh';

const AnalysisWindowContent: React.FC<AnalysisWindowContentProps> = ({ newsItemId }) => {
  // Added handleForceAnalysis function for the new button
  const [newsItem, setNewsItem] = useState<NewsItem | null>(null);
  const [analysisContent, setAnalysisContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  const handleForceAnalysis = async () => {
    if (!newsItemId) return;

    setError(null);
    setAnalysisContent(''); 
    setIsStreaming(true);
    setIsLoading(true); 

    try {
      const response = await newsService.streamAnalysis(newsItemId, true); 
      if (!response.body) throw new Error("Streaming response body is empty.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let firstChunkReceived = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        if (!firstChunkReceived) {
          setIsLoading(false); 
          firstChunkReceived = true;
        }

        const decodedChunk = decoder.decode(value, { stream: true });
        setAnalysisContent(prev => prev + decodedChunk);
      }

      const finalChunk = decoder.decode(); 
      if (finalChunk) {
        setAnalysisContent(prev => prev + finalChunk);
      }
      
      if (!firstChunkReceived) { 
          setIsLoading(false);
          setAnalysisContent('No analysis generated or content available.'); 
      }

    } catch (streamError: any) {
      console.error("Forced analysis streaming failed:", streamError);
      const errorDetails = extractErrorMessage(streamError);
      setError(errorDetails);
      setIsLoading(false); 
    } finally {
      setIsStreaming(false); 
    }
  };

  useEffect(() => {
    const fetchNewsAndAnalyze = async () => {
      setIsLoading(true);
      setError(null);
      setAnalysisContent('');

      try {
        const item = await newsService.getNewsById(newsItemId);

        if (item === null) { 
        setNewsItem(null); 
          setError({ type: 'notFound', message: `News item with ID ${newsItemId} not found or not owned by user.`, status: 404 });
          setIsLoading(false);
          setIsStreaming(false);
          return;
        }

        setNewsItem(item); // Set newsItem regardless of analysis presence first

        if (item.analysis) {
          setAnalysisContent(item.analysis);
          setIsLoading(false);
          setIsStreaming(false); // Ensure streaming is false
        } else {
          // If no analysis, just set loading and streaming to false.
          // DO NOT automatically start streaming here.
          setAnalysisContent(''); // Ensure analysisContent is empty
          setIsLoading(false);
          setIsStreaming(false);
          // The automatic streaming block that was here is removed.
        }
      } catch (fetchError: any) {
        console.error("Failed to fetch news item:", fetchError);
        const errorDetails = extractErrorMessage(fetchError);
        setError(errorDetails);
        setIsLoading(false);
        setIsStreaming(false);
        setNewsItem(null);
      }
    };

    if (newsItemId) {
      fetchNewsAndAnalyze();
    }
  }, [newsItemId]);



  // Loading State (Initial fetch before content/analysis is known)
  // Check if loading AND no newsItem AND no error
  if (isLoading && !newsItem && !error) {
    return (
      <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        <Spin size="large" tip="Loading news item..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
        {error.type === 'notFound' ? ( 
        <Empty description={error.message || "News item not found."} />
        ) : error.type === 'forbidden' ? (
          <Alert
            message="Access Denied"
            description={error.message || "You do not have permission to view this news item."}
            type="error"
            showIcon
          />
        ) : (
          <Alert
            message="Error"
            description={error.message || "An unexpected error occurred."}
            type="error"
            showIcon
          />
        )}
      </div>
    );
  }

  if (!newsItem) {
     return (
        <div style={{ height: FIXED_CONTENT_HEIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <Empty description="News item not found." />
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

      <div style={{ flexShrink: 0 }}>
        <Title level={4} style={{ marginBottom: '8px', marginTop: 0 }}>{newsItem.title}</Title>
        <Space size={16} wrap style={{ marginBottom: '12px', fontSize: '12px' }}>
          {newsItem.date && <Text type="secondary">{new Date(newsItem.date).toLocaleDateString()}</Text>}
          {newsItem.source_name && (
            <Text type="secondary">{newsItem.source_name}</Text>
          )}
          {newsItem.url && (
            <Tooltip title="查看原文">
              <a href={newsItem.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', display: 'inline-flex', alignItems: 'center' }}>
           <LinkOutlined />
              </a>
            </Tooltip>
           )}
          {newsItem && !newsItem.analysis && (!analysisContent || analysisContent === 'No analysis generated or content available.') && !isStreaming && !isLoading && (
            <Tooltip title="Analyze News">
              <Button
                type="text"
                icon={<ExperimentOutlined style={{ color: 'var(--accent-color)', fontSize: '15px' }} />}
                onClick={handleForceAnalysis}
                loading={isStreaming}
                style={{ padding: '0 4px', color: 'var(--accent-color)', marginLeft: '8px' }}
                size="small"
              />
            </Tooltip>
          )}
        </Space>
        {newsItem.summary && <Paragraph type="secondary" style={{ marginBottom: '12px' }}>{newsItem.summary}</Paragraph>}
        <Divider style={{ marginTop: '0px', marginBottom: '12px' }} />
      </div>

      <div style={{
        flexGrow: 1,        
        overflowY: 'auto',   
        minHeight: 0,       
        paddingRight: '8px',
      }}>
        {isStreaming ? (
           <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Spin size="small" /> Streaming analysis...
           </div>
        ) : analysisContent && analysisContent !== 'No analysis generated or content available.' ? ( 
          <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {analysisContent}
          </Paragraph>
        ) : (
          // No valid content, not streaming
          newsItem && newsItem.analysis ? ( // Original analysis existed, but current analysisContent is empty/failed
            <div style={{ textAlign: 'center', marginTop: '20px' }}>
              <Paragraph type="secondary" style={{marginBottom: '12px'}}>
                The previous attempt to re-analyze yielded no content, or the original analysis could not be displayed.
              </Paragraph>
              <Button type="primary" onClick={handleForceAnalysis} loading={isStreaming}>
                Re-analyze News
              </Button>
            </div>
          ) : ( // No original analysis, and current analysisContent is empty/failed
            <Empty 
              description={
                <>
                  No analysis available for this item. 
                  Click the <ExperimentOutlined style={{ color: 'var(--accent-color)'}} /> icon in the header to generate one.
                  {analysisContent === 'No analysis generated or content available.' && 
                   ' The previous attempt yielded no content.'}
                </>
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )
        )}
      </div>
    </div>
  );
};

export default AnalysisWindowContent;
