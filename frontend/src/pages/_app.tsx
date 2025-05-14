
import React, { useEffect } from 'react';
import type { AppProps } from 'next/app';
import { ConfigProvider, Spin } from 'antd';
import MainLayout from '@/components/layout/MainLayout';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { PageActionProvider } from '@/context/PageActionContext';
import { useRouter } from 'next/router';
import '@/styles/globals.css';

const publicPaths = ['/login', '/register'];


function AppContent({ Component, pageProps, router }: AppProps) {
    const { isAuthenticated, loading } = useAuth();

    useEffect(() => {
        // Redirect authenticated users trying to access public paths
        if (!loading && isAuthenticated && publicPaths.includes(router.pathname)) {
            router.replace('/');
        }
    }, [isAuthenticated, loading, router]);



    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <Spin size="large" tip="Initializing..." />
            </div>
        );
    }


    const isPublicPath = publicPaths.includes(router.pathname);

    if (isPublicPath) {


        return <Component {...pageProps} />;
    } else {



        return (
            <MainLayout>
                <Component {...pageProps} />
            </MainLayout>
        );
    }
}


export default function App({ Component, pageProps, router }: AppProps & { router: ReturnType<typeof useRouter> }) {
    return (
        <ConfigProvider
            theme={{
                token: {
                    colorPrimary: 'var(--accent-color)',
                    colorInfo: 'var(--accent-color)',
                    colorSuccess: '#10B981',
                    colorWarning: '#F59E0B',
                    colorError: '#EF4444',

                    colorText: 'var(--text-primary)',
                    colorTextSecondary: 'var(--text-secondary)',
                    colorTextTertiary: 'var(--text-tertiary)',
                    colorTextQuaternary: '#CED4DA',

                    colorBgContainer: 'var(--primary-bg)',
                    colorBgLayout: 'var(--secondary-bg)',
                    colorBgElevated: 'var(--primary-bg)',
                    colorBgSpotlight: '#4A5568',

                    colorBorder: 'var(--border-color)',
                    colorBorderSecondary: 'var(--border-color-secondary)',

                    borderRadius: 6,
                    borderRadiusLG: 8,
                    borderRadiusSM: 4,

                    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'",
                    fontSize: 14,


                    controlHeight: 36,
                    controlHeightLG: 40,
                    controlHeightSM: 30,


                    boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
                },
                components: {
                    Layout: {
                        siderBg: 'var(--secondary-bg)',
                        bodyBg: 'var(--primary-bg)',
                        headerBg: 'var(--primary-bg)',
                    },
                    Menu: {
                        itemBg: 'transparent',
                        itemHoverBg: 'var(--tertiary-bg)',
                        itemSelectedBg: 'var(--secondary-bg)',
                        itemSelectedColor: 'var(--accent-color)',
                        itemColor: 'var(--text-secondary)',
                        itemHoverColor: 'var(--text-primary)',
                        activeBarBorderWidth: 0,
                        // Add a way to style the left border for selected items if possible via tokens
                        // Otherwise, CSS override is needed.
                    },
                    Card: {
                        actionsBg: '#FDFDFD',
                        paddingLG: 20,
                        extraColor: 'var(--text-secondary)',
                    },
                    Button: {
                        defaultBg: 'var(--primary-bg)', // Explicitly set default button background to a light variable
                        defaultColor: 'var(--text-secondary)',
                        defaultBorderColor: 'var(--border-color)',
                        defaultGhostColor: 'var(--text-primary)',
                        defaultGhostBorderColor: 'var(--border-color)',
                        controlItemBgActive: 'var(--secondary-bg)',
                        colorPrimaryActive: 'var(--secondary-bg)',
                        colorPrimary: 'var(--secondary-bg)',
                        colorPrimaryHover: 'var(--tertiary-bg)', // Set primary button background on hover to a light color
                    },
                    Table: { // Add explicit Table component override
                        headerBg: 'var(--secondary-bg)', // Set table header background to a light color variable
                        headerColor: 'var(--text-primary)', // Ensure header text is readable
                    },
                    Input: {
                        colorBgContainer: 'var(--input-bg)',
                        colorBorder: 'var(--input-border-color)',
                        colorTextPlaceholder: 'var(--input-placeholder-color)',

                    },
                    Select: {
                    },
                    Tooltip: {
                        colorBgSpotlight: '#2D3748',
                        colorTextLightSolid: '#FFFFFF',
                    }
                }
            }}
        >
            <AuthProvider>
                <PageActionProvider>
                    <AppContent Component={Component} pageProps={pageProps} router={router} />
                </PageActionProvider>
            </AuthProvider>
        </ConfigProvider>
    );
}
