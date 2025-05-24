/**
 * @file withAuth.tsx
 * @description Defines a Higher-Order Component (HOC) for route protection.
 * It ensures that a component is only rendered if the user is authenticated.
 * If not authenticated, the user is redirected to the login page.
 *
 * @file_purpose To provide a reusable mechanism for protecting authenticated routes/pages.
 */
import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/context/AuthContext';
import { Spin } from 'antd';

/**
 * @interface WithAuthProps
 * @description Defines additional props that might be passed by or to the withAuth HOC.
 * Currently, this interface is empty but serves as a placeholder for future extensions.
 */
interface WithAuthProps {}

/**
 * @hoc withAuth
 * @description A Higher-Order Component that wraps a given React component to enforce authentication.
 * If the user is not authenticated (checked via `useAuth` context), they are redirected to '/login'.
 * While checking authentication status, a loading spinner is displayed.
 *
 * @param {React.ComponentType<P>} WrappedComponent - The component to be protected.
 *                                                   It will receive its original props `P`.
 *
 * @returns {React.FC<P & WithAuthProps>} A new component that renders the `WrappedComponent`
 *                                        only if authenticated, or a loading spinner/null otherwise.
 *
 * @example
 * // To protect a page component:
 * // import withAuth from '@/components/auth/withAuth';
 * // const ProtectedPage: React.FC = () => <div>Secret Content</div>;
 * // export default withAuth(ProtectedPage);
 */
const withAuth = <P extends object>(WrappedComponent: React.ComponentType<P>) => {
    const ComponentWithAuth: React.FC<P & WithAuthProps> = (props) => {
        const { isAuthenticated, loading } = useAuth();
        const router = useRouter();

        useEffect(() => {
            if (!loading && !isAuthenticated) {
                router.replace('/login');
            } else if (!loading && isAuthenticated) {
                // User is authenticated and loading is complete, proceed to render WrappedComponent.
                // No specific action needed here as rendering is handled below.
            }
        }, [isAuthenticated, loading, router]);

        if (loading) {
            return (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                    <Spin size="large" tip="Loading..." />
                </div>
            );
        }

        return isAuthenticated ? <WrappedComponent {...props} /> : null; // Render null while redirecting or if not authenticated
    };

    ComponentWithAuth.displayName = `WithAuth(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`;

    return ComponentWithAuth;
};

export default withAuth;