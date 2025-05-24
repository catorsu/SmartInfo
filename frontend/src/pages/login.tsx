/**
 * @file login.tsx
 * @description Defines the login page for the SmartInfo application.
 * Users can enter their credentials to authenticate and access protected routes.
 *
 * @file_purpose To provide the user interface and logic for user authentication (login).
 */
import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Spin } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuth } from '../context/AuthContext'; // Authentication context hook
import styles from '../styles/LoginPage.module.css'; // Specific styles for the login page

const { Title } = Typography;

/**
 * @page LoginPage
 * @description A page component that provides a form for users to log in.
 * It uses the `AuthContext` to handle the login process and displays
 * loading states or error messages accordingly.
 *
 * @returns {JSX.Element} The rendered login page.
 *
 * @example
 * // This component is rendered by Next.js routing when navigating to '/login'.
 * // No direct instantiation example needed.
 */
const LoginPage: React.FC = () => {
    const { login, loading } = useAuth(); // `loading` from context indicates auth operation in progress
    const [error, setError] = useState<string | null>(null); // Local error state for login failures
    const [form] = Form.useForm(); // Ant Design form instance

    // Handles form submission for login.
    const onFinish = async (values: any) => {
        setError(null); // Clear previous errors
        try {
            await login(values.username, values.password);
            // Navigation on successful login is handled by the AuthContext's login method.
        } catch (err: any) {
            console.error('Login page caught error:', err);
            setError(err.message || 'Login failed. Please check your credentials.');
            form.resetFields(['password']); // Clear password field on error
        }
    };

    // Handles form submission failure (e.g., validation errors).
    const onFinishFailed = (errorInfo: any) => {
        setError('Please fill in all required fields correctly.');
        console.log('Failed:', errorInfo);
    };

    return (
        <div className={styles.loginContainer}>
            <Spin spinning={loading} tip="Logging in...">
                <Card className={styles.loginCard}>
                    <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
                        Login
                    </Title>
                    {error && ( // Display error alert if login fails
                        <Alert
                            message="Login Error"
                            description={error}
                            type="error"
                            showIcon
                            closable
                            onClose={() => setError(null)} // Allow closing the alert
                            style={{ marginBottom: '24px' }}
                        />
                    )}
                    <Form
                        form={form}
                        name="login_form"
                        initialValues={{ remember: true }} // "Remember me" functionality (if implemented)
                        onFinish={onFinish}
                        onFinishFailed={onFinishFailed}
                        autoComplete="off"
                        layout="vertical" // Vertical layout for labels and inputs
                        disabled={loading} // Disable form while loading
                    >
                        <Form.Item
                            label="Username"
                            name="username"
                            rules={[{ required: true, message: 'Please input your Username!' }]}
                        >
                            <Input prefix={<UserOutlined />} placeholder="Username" autoComplete="username" />
                        </Form.Item>

                        <Form.Item
                            label="Password"
                            name="password"
                            rules={[{ required: true, message: 'Please input your Password!' }]}
                        >
                            <Input.Password prefix={<LockOutlined />} placeholder="Password" autoComplete="current-password" />
                        </Form.Item>

                        <Form.Item>
                            <Button type="primary" htmlType="submit" block loading={loading}>
                                Log in
                            </Button>
                        </Form.Item>

                        <div style={{ textAlign: 'center', marginTop: '12px' }}>
                            No account? <a href="/register">Register now</a>
                        </div>
                    </Form>
                </Card>
            </Spin>
        </div>
    );
};

export default LoginPage;