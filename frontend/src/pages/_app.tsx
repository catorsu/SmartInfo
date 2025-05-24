/**
 * @file _app.tsx
 * @description Main application component for Next.js.
 * Wraps all pages with global providers like AuthProvider and Ant Design's ConfigProvider.
 * Manages layout switching for public vs. authenticated routes and handles initial
 * authentication loading state.
 *
 * @file_purpose To set up global context providers (authentication, UI theme),
 *               and manage the overall page layout structure based on route and
 *               authentication status.
 */
import React, { useEffect } from 'react';
import type { AppProps } from 'next/app';
import { ConfigProvider, Spin } from 'antd';
import MainLayout from '@/components/layout/MainLayout'; // MainLayout will now provide PageActionContext
import { AuthProvider, useAuth } from '@/context/AuthContext';
// PageActionProvider is removed from here, MainLayout will provide it.
import { useRouter } from 'next/router';
import '@/styles/globals.css';

// Defines paths that are considered public and do not require authentication.
const publicPaths = ['/login', '/register'];

/**
 * @component AppContent
 * @description Internal component responsible for rendering the correct page layout
 * (either MainLayout for authenticated routes or direct component for public routes)
 * after the initial authentication check is complete. It also handles redirection
 * for authenticated users trying to access public pages.
 *
 * @param {AppProps & { router: ReturnType<typeof useRouter> }} props - Standard Next.js AppProps
 *        extended with the router object. Includes `Component` (the current page),
 *        `pageProps`, and `router`.
 * @returns {JSX.Element} The page component, potentially wrapped in `MainLayout`,
 *                        or a global loading spinner during auth check.
 */
function AppContent({ Component, pageProps, router }: AppProps & { router: ReturnType<typeof useRouter> }) {
    const { isAuthenticated, loading } = useAuth();

    useEffect(() => {
        // Redirect authenticated users trying to access public paths (e.g., login page)
        // back to the application's root or a dashboard.
        if (!loading && isAuthenticated && publicPaths.includes(router.pathname)) {
            router.replace('/');
        }
        // Unauthenticated users attempting to access protected pages are handled by
        // the `withAuth` HOC wrapping those specific pages.
    }, [isAuthenticated, loading, router]);

    // Display a global loading spinner while initial authentication check is in progress.
    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <Spin size="large" tip="Initializing..." />
            </div>
        );
    }

    const isPublicPath = publicPaths.includes(router.pathname);

    if (isPublicPath) {
        // Render public pages (login, register) without the MainLayout.
        return <Component {...pageProps} />;
    } else {
        // Render authenticated pages within MainLayout.
        // MainLayout internally provides PageActionContext.
        return (
            <MainLayout>
                <Component {...pageProps} />
            </MainLayout>
        );
    }
}

/**
 * @component App
 * @description The root component for the Next.js application, as defined by `pages/_app.tsx`.
 * It sets up global providers, including Ant Design's `ConfigProvider` for UI theming
 * and the `AuthProvider` for managing authentication state across the application.
 * It then delegates rendering to `AppContent`.
 *
 * @param {AppProps & { router: ReturnType<typeof useRouter> }} props - Standard Next.js AppProps
 *        passed from Next.js, including the page `Component`, `pageProps`, and `router`.
 * @returns {JSX.Element} The configured application structure with global providers.
 *
 * @example
 * // This component is automatically used by Next.js. No direct usage example needed.
 */
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
                    },
                    Card: {
                        actionsBg: '#FDFDFD',
                        paddingLG: 20,
                        extraColor: 'var(--text-secondary)',
                    },
                    Button: {
                        defaultBg: 'var(--primary-bg)',
                        defaultColor: 'var(--text-secondary)',
                        defaultBorderColor: 'var(--border-color)',
                        defaultGhostColor: 'var(--text-primary)',
                        defaultGhostBorderColor: 'var(--border-color)',
                        controlItemBgActive: 'var(--secondary-bg)',
                        colorPrimaryActive: 'var(--secondary-bg)',
                        colorPrimary: 'var(--secondary-bg)',
                        colorPrimaryHover: 'var(--tertiary-bg)',
                    },
                    Table: {
                        headerBg: 'var(--secondary-bg)',
                        headerColor: 'var(--text-primary)',
                    },
                    Input: {
                        colorBgContainer: 'var(--input-bg)',
                        colorBorder: 'var(--input-border-color)',
                        colorTextPlaceholder: 'var(--input-placeholder-color)',
                    },
                    Select: {}, // Placeholder for Select specific overrides if needed
                    Tooltip: {
                        colorBgSpotlight: '#2D3748', // Darker background for tooltips
                        colorTextLightSolid: '#FFFFFF', // White text for tooltips
                    }
                }
            }}
        >
            <AuthProvider>
                {/* PageActionProvider is now provided by MainLayout, which is conditionally rendered by AppContent */}
                <AppContent Component={Component} pageProps={pageProps} router={router} />
            </AuthProvider>
        </ConfigProvider>
    );
}