/**
 * @file [id].tsx
 * @description Dynamically routed page for displaying the analysis of a specific news item.
 * It extracts the news item ID from the URL and passes it to the AnalysisWindowContent component.
 *
 * @file_purpose To serve as the entry point for viewing detailed analysis of individual news items.
 */
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import AnalysisWindowContent from '@/components/analysis/AnalysisWindowContent';
import { Typography, Alert } from 'antd';
import withAuth from '@/components/auth/withAuth';

const { Title } = Typography;

/**
 * @page AnalyzePage
 * @description This page displays the analysis for a news item identified by an ID in the URL.
 * It uses the `AnalysisWindowContent` component to show the details and analysis.
 * The page can also be instructed to start analysis immediately via a query parameter.
 * This page is protected and requires authentication.
 *
 * @returns {JSX.Element} The rendered analysis page for a specific news item.
 *
 * @example
 * // Navigation to this page:
 * // router.push('/analyze/123'); // Displays analysis for news item with ID 123
 * // router.push('/analyze/123?initiate=true'); // Also starts analysis immediately
 */
const AnalyzePage: React.FC = () => {
  const router = useRouter();
  const { id, initiate } = router.query; // `id` is the news item ID, `initiate` controls auto-start

  const newsItemId = typeof id === 'string' ? parseInt(id, 10) : undefined;
  const [shouldStartAnalysis, setShouldStartAnalysis] = useState(false);

  useEffect(() => {
    // Ensure query parameters are available before attempting to use them.
    if (router.isReady) {
      setShouldStartAnalysis(initiate === 'true');
    }
  }, [router.isReady, initiate]);

  // Handle cases where the newsItemId is not valid or not yet available.
  if (router.isReady && newsItemId === undefined) {
    return (
      <div style={{ padding: '20px' }}>
        <Alert
          message="Error"
          description="Invalid news item ID provided in the URL."
          type="error"
          showIcon
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      {newsItemId !== undefined ? (
        <AnalysisWindowContent
                  newsItemId={newsItemId}
                  startAnalysisImmediately={shouldStartAnalysis}
                />
      ) : (
        // Show a loading state while router is not ready or ID is being parsed.
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
           <Title level={4}>Loading news analysis...</Title>
        </div>
      )}
    </div>
  );
};

export default withAuth(AnalyzePage); // Protect this page with authentication