/**
 * @file register.tsx
 * @description Defines the registration page for new users of the SmartInfo application.
 * It allows users to create a new account by providing a username and password.
 *
 * @file_purpose To provide the user interface and logic for new user registration.
 */
import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Spin } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useRouter } from 'next/router';
import { useAuth } from '../context/AuthContext'; // Authentication context for signup
import styles from '../styles/LoginPage.module.css'; // Uses similar styles to the login page

const { Title } = Typography;

/**
 * @interface RegisterFormData
 * @description Defines the structure for the registration form data.
 */
interface RegisterFormData {
    username: string;        // The desired username for the new account.
    password: string;        // The chosen password for the new account.
    // confirmPassword is handled by form validation but not part of direct submission data to backend.
}

/**
 * @page RegisterPage
 * @description A page component that provides a form for new users to register.
 * It uses the `AuthContext` to handle the signup process. Displays loading states,
 * success messages, or error messages based on the registration attempt.
 *
 * @returns {JSX.Element} The rendered registration page.
 *
 * @example
 * // This component is rendered by Next.js routing when navigating to '/register'.
 * // No direct instantiation example needed.
 */
const RegisterPage: React.FC = () => {
    const router = useRouter();
    const { signup, loading: authLoading } = useAuth(); // `authLoading` from context
    const [error, setError] = useState<string | null>(null); // Local error state for registration
    const [success, setSuccess] = useState<string | null>(null); // Local success state (though signup usually navigates)
    const [localLoading, setLocalLoading] = useState(false); // Additional local loading if needed
    const [form] = Form.useForm(); // Ant Design form instance

    // Combined loading state
    const loading = localLoading || authLoading;

    // Handles form submission for registration.
    const onFinish = async (values: RegisterFormData) => {
        setError(null);
        setSuccess(null);
        setLocalLoading(true);

        try {
            await signup(values.username, values.password);
            // On successful signup, AuthContext handles navigation.
            // A success message here might be brief as navigation occurs.
            setSuccess('Registration successful! Redirecting...');
            form.resetFields();
            // No explicit router.push here, as AuthContext's signup should handle it.
        } catch (err: any) {
            console.error('Registration error:', err);
            setError(err.message || 'Registration failed. Please try again.');
            // Do not reset username on error, but clear password fields for security.
            form.resetFields(['password', 'confirmPassword']);
        } finally {
            setLocalLoading(false);
        }
    };

    // Handles form submission failure (e.g., validation errors).
    const onFinishFailed = (errorInfo: any) => {
        setError('Please fill all required fields correctly.');
        console.log('Failed:', errorInfo);
    };

    return (
        <div className={styles.loginContainer}> {/* Reusing login page container style */}
            <Spin spinning={loading} tip="Processing...">
                <Card className={styles.loginCard}> {/* Reusing login card style */}
                    <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
                        Create Account
                    </Title>
                    
                    {error && ( // Display error alert
                        <Alert
                            message="Registration Error"
                            description={error}
                            type="error"
                            showIcon
                            closable
                            onClose={() => setError(null)}
                            style={{ marginBottom: '24px' }}
                        />
                    )}
                    
                    {success && ( // Display success alert (briefly, before navigation)
                        <Alert
                            message="Registration Successful"
                            description={success}
                            type="success"
                            showIcon
                            style={{ marginBottom: '24px' }}
                        />
                    )}
                    
                    <Form
                        form={form}
                        name="register_form"
                        onFinish={onFinish}
                        onFinishFailed={onFinishFailed}
                        autoComplete="off"
                        layout="vertical"
                        disabled={loading || !!success} // Disable form if loading or success (awaiting redirect)
                    >
                        <Form.Item
                            label="Username"
                            name="username"
                            rules={[
                                { required: true, message: 'Please input your desired username!' },
                                { min: 3, message: 'Username must be at least 3 characters.' }
                            ]}
                        >
                            <Input 
                                prefix={<UserOutlined />} 
                                placeholder="Choose a username" 
                                autoComplete="username" // Standard autocomplete hint
                            />
                        </Form.Item>

                        <Form.Item
                            label="Password"
                            name="password"
                            rules={[
                                { required: true, message: 'Please input your password!' },
                                { min: 6, message: 'Password must be at least 6 characters.' }
                            ]}
                            hasFeedback // Shows validation status icon
                        >
                            <Input.Password 
                                prefix={<LockOutlined />} 
                                placeholder="Create a password"
                                autoComplete="new-password" // Hint for password managers
                            />
                        </Form.Item>

                        <Form.Item
                            label="Confirm Password"
                            name="confirmPassword"
                            dependencies={['password']} // Depends on the 'password' field
                            hasFeedback
                            rules={[
                                { required: true, message: 'Please confirm your password!' },
                                ({ getFieldValue }) => ({ // Custom validator to match passwords
                                    validator(_, value) {
                                        if (!value || getFieldValue('password') === value) {
                                            return Promise.resolve();
                                        }
                                        return Promise.reject(new Error('The two passwords that you entered do not match!'));
                                    },
                                }),
                            ]}
                        >
                            <Input.Password 
                                prefix={<LockOutlined />} 
                                placeholder="Confirm your password"
                                autoComplete="new-password"
                            />
                        </Form.Item>

                        <Form.Item>
                            <Button 
                                type="primary" 
                                htmlType="submit" 
                                block 
                                loading={loading}
                            >
                                Register
                            </Button>
                        </Form.Item>
                        
                        <div style={{ textAlign: 'center', marginTop: '12px' }}>
                            Already have an account? <a href="/login">Log in</a>
                        </div>
                    </Form>
                </Card>
            </Spin>
        </div>
    );
};

export default RegisterPage;