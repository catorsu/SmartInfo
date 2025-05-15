import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Spin } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import styles from '../styles/LoginPage.module.css';

const { Title } = Typography;

const LoginPage: React.FC = () => {
    const { login, loading } = useAuth();
    const [error, setError] = useState<string | null>(null);
    const [form] = Form.useForm();

    const onFinish = async (values: any) => {
        setError(null);
        try {
            await login(values.username, values.password);
        } catch (err: any) {
            console.error('Login page caught error:', err);
            setError(err.message || 'Login failed. Please check your credentials.');
            form.resetFields(['password']);
        }
    };

    const onFinishFailed = (errorInfo: any) => {
        setError('Please fill in all required fields.');
    };

    return (
        <div className={styles.loginContainer}>
            <Spin spinning={loading} tip="Logging in...">
                <Card className={styles.loginCard}>
                    <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
                        Login
                    </Title>
                    {error && (
                        <Alert
                            message="Login Error"
                            description={error}
                            type="error"
                            showIcon
                            closable
                            onClose={() => setError(null)}
                            style={{ marginBottom: '24px' }}
                        />
                    )}
                    <Form
                        form={form}
                        name="login_form"
                        initialValues={{ remember: true }}
                        onFinish={onFinish}
                        onFinishFailed={onFinishFailed}
                        autoComplete="off"
                        layout="vertical" 
                        disabled={loading}
                    >
                        <Form.Item
                            label="Username"
                            name="username"
                            rules={[{ required: true, message: 'Please input your Username!' }]}
                        >
                            <Input prefix={<UserOutlined />} placeholder="Username" />
                        </Form.Item>

                        <Form.Item
                            label="Password"
                            name="password"
                            rules={[{ required: true, message: 'Please input your Password!' }]}
                        >
                            <Input.Password prefix={<LockOutlined />} placeholder="Password" />
                        </Form.Item>

                        <Form.Item>
                            <Button type="primary" htmlType="submit" block loading={loading}>
                                Log in
                            </Button>
                        </Form.Item>

                        <div style={{ textAlign: 'center', marginTop: '12px' }}>
                            没有账号？ <a href="/register">立即注册</a>
                        </div>
                    </Form>
                </Card>
            </Spin>
        </div>
    );
};

export default LoginPage;
