import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/context/AuthContext';
import { Spin } from 'antd';

interface WithAuthProps {}

const withAuth = <P extends object>(WrappedComponent: React.ComponentType<P>) => {
    const ComponentWithAuth: React.FC<P & WithAuthProps> = (props) => {
        const { isAuthenticated, loading } = useAuth();
        const router = useRouter();

        useEffect(() => {
            if (!loading && !isAuthenticated) {
                router.replace('/login');
            } else if (!loading && isAuthenticated) {
                // Intentionally empty, or add a comment if specific logic was meant here
            }
        }, [isAuthenticated, loading, router]);

        if (loading) {
            return (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                    <Spin size="large" tip="Loading..." />
                </div>
            );
        }

        return isAuthenticated ? <WrappedComponent {...props} /> : null;
    };

    ComponentWithAuth.displayName = `WithAuth(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`;

    return ComponentWithAuth;
};

export default withAuth;
