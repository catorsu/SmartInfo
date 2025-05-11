import React, { useState, useEffect } from 'react';
import { Typography, Spin, Alert, Space, Divider, Empty, Tooltip } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import { NewsItem } from '@/utils/types';
import * as newsService from '@/services/newsService';
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';

const { Title, Text, Paragraph } = Typography;

interface AnalysisWindowContentProps {
  newsItemId: number;
}

const FIXED_CONTENT_HEIGHT = '65vh';

const AnalysisWindowContent: React.FC<AnalysisWindowContentProps> = ({ newsItemId }) => {
  const [newsItem, setNewsItem] = useState<NewsItem | null>(null);
  const [analysisContent, setAnalysisContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

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

        setNewsItem(item);

        if (item.analysis) {
          setAnalysisContent(item.analysis);
          setIsLoading(false);
          setIsStreaming(false);
        } else {
          setIsStreaming(true);
          setIsLoading(true);

          try {
            const response = await newsService.streamAnalysis(newsItemId);
            if (!response.body) throw new Error("Streaming response body is empty.");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let receivedContent = '';
            let firstChunkReceived = false;

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              if (!firstChunkReceived) {
                setIsLoading(false);
                firstChunkReceived = true;
              }

              const decodedChunk = decoder.decode(value, { stream: true });
              receivedContent += decodedChunk;
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
            console.error("Streaming analysis failed:", streamError);
            const errorDetails = extractErrorMessage(streamError);
            setError(errorDetails);
            setIsLoading(false);
          } finally {
            setIsStreaming(false);
          }
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
          <Empty description="No analysis available or generated." image={Empty.PRESENTED_IMAGE_SIMPLE}/>
        )}
      </div>
    </div>
  );
};

export default AnalysisWindowContent;
