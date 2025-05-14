import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import AnalysisWindowContent from '@/components/analysis/AnalysisWindowContent';
import { Typography, Alert } from 'antd';
import withAuth from '@/components/auth/withAuth';

const { Title } = Typography;

const AnalyzePage: React.FC = () => {
  const router = useRouter();
  const { id, initiate } = router.query; // Destructure initiate

  const newsItemId = typeof id === 'string' ? parseInt(id, 10) : undefined;
  const [shouldStartAnalysis, setShouldStartAnalysis] = useState(false);

  useEffect(() => {
    if (router.isReady) { // Ensure query params are available
      setShouldStartAnalysis(initiate === 'true');
    }
  }, [router.isReady, initiate]); // Depend on router.isReady and initiate

  if (router.isReady && newsItemId === undefined) {
    return (
      <div style={{ padding: '20px' }}>
        <Alert
          message="Error"
          description="Invalid news item ID provided."
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
                  startAnalysisImmediately={shouldStartAnalysis} // Pass the new prop
                />
      ) : (
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
           <Title level={4}>Loading...</Title>
        </div>
      )}
    </div>
  );
};

export default withAuth(AnalyzePage);
