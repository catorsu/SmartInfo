import React, { useState, useEffect } from 'react';
import { Row, Col } from 'antd';
import {
  Typography,
  Tabs,
  Form,
  Input,
  Button,
  Table,
  Space,
  Popconfirm,
  Modal,
  message,
  Card,
  Divider,
  Switch,
  Select,
  Spin,
  Alert,
  InputNumber,
  Tag,
  Tooltip,
} from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  KeyOutlined,
  ApiOutlined,
  SettingOutlined,
  SaveOutlined,
  UserOutlined,
  LockOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import type { TableProps } from 'antd/lib/table';
import { ApiKey, NewsCategory, NewsSource } from '@/utils/types';
import * as settingsService from '@/services/settingsService';
import * as newsService from '@/services/newsService';
import * as authService from '@/services/authService';
// Removed MainLayout import
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';
// Removed withAuth import
import { useAuth } from '@/context/AuthContext';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

interface ApiKeyFormValues {
  model: string;
  base_url: string;
  api_key: string;
  context: number;
  max_output_tokens: number;
  description?: string;
}

// Renamed component
const SettingsContent: React.FC = () => {
  const { user, logout, loading: authLoading, updateUserProfile } = useAuth();
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [categories, setCategories] = useState<NewsCategory[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  const [isApiKeyModalVisible, setIsApiKeyModalVisible] = useState(false);
  const [apiKeyForm] = Form.useForm<ApiKeyFormValues>();
  const [editingApiKeyId, setEditingApiKeyId] = useState<number | null>(null);
  const [editingApiKey, setEditingApiKey] = useState<ApiKey | null>(null);

  const [isSourceModalVisible, setIsSourceModalVisible] = useState(false);
  const [sourceForm] = Form.useForm<{ name: string; url: string; category_id: number }>();
  const [editingSourceId, setEditingSourceId] = useState<number | null>(null);
  const [newCategoryName, setNewCategoryName] = useState<string>('');
  const [isAddCategoryModalVisible, setIsAddCategoryModalVisible] = useState(false);

  const [settingsForm] = Form.useForm();

  const [isPasswordModalVisible, setIsPasswordModalVisible] = useState(false);
  const [passwordChangeLoading, setPasswordChangeLoading] = useState(false);
  const [passwordForm] = Form.useForm();

  const [isUsernameModalVisible, setIsUsernameModalVisible] = useState(false);
  const [usernameChangeLoading, setUsernameChangeLoading] = useState(false);
  const [usernameForm] = Form.useForm();

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    try {
      setLoading(true);
      setError(null);
      await Promise.all([
        loadSettings(),
        loadApiKeys(),
        loadCategories(),
        loadSources()
      ]);
    } catch (err: any) {
      console.error('Failed to load settings data:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setLoading(false);
    }
  };

  const loadSettings = async () => {
    try {
      setSettingsLoading(true);
      const settingsData = await settingsService.getSettings();
      setSettings(settingsData);
      settingsForm.setFieldsValue(settingsData);
    } catch (err: any) {
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setSettingsLoading(false);
    }
  };

  const loadApiKeys = async () => {
    try {
      setApiKeysLoading(true);
      const apiKeysData = await settingsService.getApiKeys();
      setApiKeys(apiKeysData);
    } catch (err: any) {
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setApiKeysLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const categoriesData = await newsService.getCategories();
      setCategories(categoriesData);
    } catch (err: any) {
      console.error('Failed to load categories:', err);
    }
  };

  const loadSources = async () => {
    try {
      const sourcesData = await newsService.getSources();
      setSources(sourcesData);
    } catch (err: any) {
      console.error('Failed to load sources:', err);
    }
  };
  const handleSettingChange = (key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const saveSettings = async (values: Record<string, any>) => {
    try {
      setSavingSettings(true);
      const result = await settingsService.updateSettings(values);
      setSettings(result.settings);
      message.success('Settings saved successfully');
    } catch (error) {
      handleApiError(error, 'Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  const resetSettings = async () => {
    try {
      setLoading(true);
      const result = await settingsService.resetSettings();
      setSettings(result.settings);
      settingsForm.setFieldsValue(result.settings);
      message.success('Settings have been reset to default');
    } catch (error) {
      handleApiError(error, 'Failed to reset settings');
    } finally {
      setLoading(false);
    }
  };
  const showAddApiKeyModal = () => {
    apiKeyForm.resetFields();
    setEditingApiKey(null);
    setEditingApiKeyId(null);
    setIsApiKeyModalVisible(true);
  };

  const showEditApiKeyModal = (record: ApiKey) => {
    setEditingApiKey(record);
    setEditingApiKeyId(record.id);
    settingsService.getApiKey(record.id)
      .then(apiKeyData => {
        if (apiKeyData === null) {
          message.error('API key not found or has been deleted');
          setIsApiKeyModalVisible(false);
          setEditingApiKey(null);
          setEditingApiKeyId(null);
          return;
        }
        apiKeyForm.setFieldsValue({
          model: apiKeyData.model,
          base_url: apiKeyData.base_url,
          api_key: apiKeyData.api_key,
          context: apiKeyData.context,
          max_output_tokens: apiKeyData.max_output_tokens,
          description: apiKeyData.description
        });
        setIsApiKeyModalVisible(true);
      })
      .catch(error => { // This catch will now only handle non-404 errors
        handleApiError(error, 'Failed to load API key details');
        setIsApiKeyModalVisible(false);
        setEditingApiKey(null);
        setEditingApiKeyId(null);
      });
  };

  const handleApiKeySave = async () => {
    try {
      const values = await apiKeyForm.validateFields();

      if (editingApiKey) {
        await settingsService.updateApiKey(editingApiKeyId!, values);
        message.success('API key updated successfully');
      } else {
        await settingsService.createApiKey(values);
        message.success('API key created successfully');
      }

      setIsApiKeyModalVisible(false);
      loadApiKeys();
    } catch (error) {
      handleApiError(error, 'Failed to save API key');
    }
  };

  const handleDeleteApiKey = async (apiKeyId: number) => {
    try {
      await settingsService.deleteApiKey(apiKeyId);
      message.success('API key deleted successfully');
      loadApiKeys();
    } catch (error) {
      handleApiError(error, 'Failed to delete API key');
    }
  };
  const handleTestApiKey = async (apiKeyId: number) => {
    const testMessage = message.loading('Testing API key connection...', 0);

    try {
      const result = await settingsService.testApiKey(apiKeyId);
      testMessage();

      if (result.status === 'success') {
        message.success('Connection test successful!');
      } else {
        message.error(`Test failed: ${result.message}`);
      }
    } catch (error) {
      testMessage();
      handleApiError(error, 'Failed to test API key');
    }
  };
  const showAddSourceModal = () => {
    sourceForm.resetFields();
    setEditingSourceId(null);
    setIsSourceModalVisible(true);
  };

  const showEditSourceModal = (record: NewsSource) => {
    sourceForm.setFieldsValue({
      name: record.name,
      url: record.url,
      category_id: record.category_id
    });
    setEditingSourceId(record.id);
    setIsSourceModalVisible(true);
  };

  const handleSourceSave = async () => {
    try {
      const values = await sourceForm.validateFields();

      if (editingSourceId) {
        await newsService.updateSource(editingSourceId, values);
        message.success('Source updated successfully');
      } else {
        await newsService.createSource(values);
        message.success('Source created successfully');
      }

      setIsSourceModalVisible(false);
      loadSources();
    } catch (error) {
      console.error('Failed to save source:', error);
      message.error('Failed to save source');
    }
  };

  const handleDeleteSource = async (id: number) => {
    try {
      await newsService.deleteSource(id);
      message.success('Source deleted successfully');
      loadSources();
    } catch (error) {
      console.error('Failed to delete source:', error);
      message.error('Failed to delete source');
    }
  };
  const handleAddCategoryClick = () => {
    setNewCategoryName('');
    setIsAddCategoryModalVisible(true);
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) {
      message.error('Category name cannot be empty');
      return;
    }

    try {
      const newCategory = await newsService.createCategory({ name: newCategoryName });
      message.success('Category created successfully');
      await loadCategories();
      setIsAddCategoryModalVisible(false);
      sourceForm.setFieldsValue({ category_id: newCategory.id });
    } catch (error) {
      handleApiError(error, 'Failed to create category');
    }
  };

  const handleDeleteCategoryTag = (categoryId: number) => {
    Modal.confirm({
      title: 'Confirm Deletion',
      content: 'Are you sure you want to delete this category? This action cannot be undone.',
      okText: 'Delete',
      cancelText: 'Cancel',
      okType: 'danger',
      onOk: async () => {
        try {
          await newsService.deleteCategory(categoryId);
          message.success('Category deleted successfully');
          await loadCategories();
        } catch (error) {
          handleApiError(error, 'Failed to delete category');
        }
      }
    });
  };
  const apiKeyColumns: TableProps<ApiKey>['columns'] = [
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
    },
    {
      title: 'API Key',
      key: 'api_key',
      render: () => '••••••••',
    },
    {
      title: 'Context',
      dataIndex: 'context',
      key: 'context',
    },
    {
      title: 'Max Output Tokens',
      dataIndex: 'max_output_tokens',
      key: 'max_output_tokens',
    },


    {
      title: () => (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Action</span>
          <Tooltip title="Add API Key">
            <Button
              type="primary"
              ghost
              shape="circle"
              icon={<PlusOutlined />}
              size="small"
              onClick={(e) => { e.stopPropagation(); showAddApiKeyModal(); }}
            />
          </Tooltip>
        </div>
      ),
      key: 'action',
      render: (_: any, record: ApiKey) => (
        <Space>
          <Tooltip title="Edit API Key"><Button
            icon={<EditOutlined />}
            onClick={() => showEditApiKeyModal(record)}
            size="small"
          /></Tooltip>
          <Tooltip title="Test API Key"><Button
            icon={<ApiOutlined />}
            onClick={() => handleTestApiKey(record.id)}
            size="small"
          /></Tooltip>
          <Popconfirm
            title="Are you sure you want to delete this API key?"
            onConfirm={() => handleDeleteApiKey(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Tooltip title="Delete API Key"><Button
              danger
              icon={<DeleteOutlined />}
              size="small"
            /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const sourceColumns: TableProps<NewsSource>['columns'] = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      render: (text) => <a href={text} target="_blank" rel="noopener noreferrer">{text}</a>,
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      render: (_, record) => {
        const category = categories.find(c => c.id === record.category_id);
        return category ? category.name : '-';
      },
    },
    {
      title: () => (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <span>Action</span>
          <Tooltip title="Add Source">
            <Button
              type="primary"
              ghost
              shape="circle"
              icon={<PlusOutlined />}
              size="small"
              style={{ marginLeft: 8 }}
              onClick={(e) => { e.stopPropagation(); showAddSourceModal(); }}
            />
          </Tooltip>
        </div>
      ),
      key: 'actions',
      render: (_: any, record: NewsSource) => (
        <Space>
          <Tooltip title="Edit Source"><Button
            icon={<EditOutlined />}
            onClick={() => showEditSourceModal(record)}
            size="small"
          /></Tooltip>
          <Popconfirm
            title="Are you sure you want to delete this source?"
            onConfirm={() => handleDeleteSource(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Tooltip title="Delete Source"><Button
              danger
              icon={<DeleteOutlined />}
              size="small"
            /></Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const handlePasswordModalOk = async () => {
    try {
      const values = await passwordForm.validateFields();
      await handleChangePassword(values);
    } catch (formError) {
      console.log('Password form validation failed:', formError);
    }
  };

  const handlePasswordModalCancel = () => {
    setIsPasswordModalVisible(false);
    passwordForm.resetFields();
  };

  const handleUsernameModalOk = async () => {
    try {
      const values = await usernameForm.validateFields();
      await handleChangeUsername(values);
    } catch (formError) {
      console.log('Username form validation failed:', formError);
    }
  };

  const handleUsernameModalCancel = () => {
    setIsUsernameModalVisible(false);
    usernameForm.resetFields();
  };

  const handleChangeUsername = async (values: any) => {
    setUsernameChangeLoading(true);
    try {
      const updatedUser = await authService.changeUsername({
        new_username: values.newUsername,
        current_password: values.currentPassword,
      });
      message.success('Username successfully changed!');
      // Use updateUserProfile from context
      if (typeof updateUserProfile === 'function') {
          updateUserProfile(updatedUser);
      }
      setIsUsernameModalVisible(false);
      usernameForm.resetFields();
    } catch (apiError: any) {
      message.error(extractErrorMessage(apiError).message || 'Failed to change username.');
    } finally {
      setUsernameChangeLoading(false);
    }
  };
  const handleChangePassword = async (values: any) => {
    setPasswordChangeLoading(true);
    try {
      await authService.changePassword({
        current_password: values.currentPassword,
        new_password: values.newPassword,
      });
      message.success('Password successfully changed!');
      setIsPasswordModalVisible(false);
      passwordForm.resetFields();
    } catch (apiError: any) {
      message.error(extractErrorMessage(apiError).message || 'Failed to change password.');
    } finally {
      setPasswordChangeLoading(false);
    }
  };

  // Removed MainLayout wrapper
  return (
    <div> {/* Changed from MainLayout to a simple div or fragment */}
      <Row justify="center" style={{ width: '100%' }}>
        <Col xs={24} sm={24} md={24} lg={23} xl={22}>
          <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>System Settings</Title>

          {error && (
            <Alert
              message="Error Loading Settings"
              description={error.message || "An unexpected error occurred while loading settings data."}
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Tabs defaultActiveKey="general" centered>
            <TabPane
              tab={<><SettingOutlined /> General Settings</>}
              key="general"
            >
              <Card title="Application Settings" extra={
                <Space>
                  <Tooltip title="Reset to Default Settings">
                    <Button
                    icon={<ReloadOutlined />}
                    onClick={resetSettings}
                    >
                    </Button>
                  </Tooltip>
                </Space>
              }>
                <Spin spinning={settingsLoading}>
                  <Form
                    form={settingsForm}
                    layout="vertical"
                    onFinish={saveSettings}
                  >
                    {Object.entries(settings).map(([key, value]) => (
                      <Form.Item
                        key={key}
                        name={key}
                        label={key.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase())}
                      >
                        <Input />
                      </Form.Item>
                    ))}

                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={savingSettings} icon={<SaveOutlined />}>
                        Save Settings
                      </Button>
                    </Form.Item>
                  </Form>
                </Spin>
              </Card>
            </TabPane>

            <TabPane
              tab={<><KeyOutlined /> API Keys</>}
              key="api-keys"
            >
              <Spin spinning={apiKeysLoading}>
                <Table
                  dataSource={apiKeys}
                    columns={apiKeyColumns}
                    rowKey="id"
                    pagination={false}
                  />
                </Spin>
            </TabPane>

            <TabPane
              tab={<><ApiOutlined /> News Sources</>}
              key="sources"
              >
              <Table
              dataSource={sources}
                columns={[
                  {
                    title: 'Name',
                    dataIndex: 'name',
                    key: 'name',
                  },
                  {
                    title: 'URL',
                    dataIndex: 'url',
                    key: 'url',
                    render: (text) => <a href={text} target="_blank" rel="noopener noreferrer">{text}</a>,
                  },
                  {
                    title: 'Category',
                    dataIndex: 'category',
                    key: 'category',
                    render: (_, record) => {
                      const category = categories.find(c => c.id === record.category_id);
                      return category ? category.name : '-';
                    },
                  },
                  {
                    title: () => (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>Action</span>
                        <Tooltip title="Add Source">
                          <Button
                            type="primary"
                            shape="circle"
                            icon={<PlusOutlined />}
                            size="small"
                            onClick={(e) => { e.stopPropagation(); showAddSourceModal(); }}
                          />
                        </Tooltip>
                      </div>
                    ),
                    key: 'actions',
                    render: (_: any, record: NewsSource) => (
                      <Space>
                        <Tooltip title="Edit Source"><Button
                          icon={<EditOutlined />}
                          onClick={() => showEditSourceModal(record)}
                          size="small"
                        /></Tooltip>
                        <Popconfirm
                          title="Are you sure you want to delete this source?"
                          onConfirm={() => handleDeleteSource(record.id)}
                          okText="Yes"
                          cancelText="No"
                        >
                          <Tooltip title="Delete Source"><Button
                            danger
                            icon={<DeleteOutlined />}
                            size="small"
                          /></Tooltip>
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
                rowKey="id"
                loading={loading}
              />
            </TabPane>

            <TabPane
              tab={<><UserOutlined /> Account</>}
              key="account"
            >
              <Card title="Account Information" style={{ marginBottom: 24 }}>
                <Spin spinning={authLoading}>
                  <Form layout="vertical">
                    <Form.Item label="Username">
                      <Space>
                        <Input value={user?.username || 'Loading...'} readOnly prefix={<UserOutlined />} style={{ flexGrow: 1 }} />
                        <Button onClick={() => setIsUsernameModalVisible(true)} icon={<EditOutlined />}>
                          Change
                        </Button>
                      </Space>
                    </Form.Item>
                  </Form>
                </Spin>
              </Card>

              <Card title="Security" style={{ marginBottom: 24 }}>
                <Button
                  onClick={() => setIsPasswordModalVisible(true)}
                  icon={<LockOutlined />}
                >
                  Change Password
                </Button>
                <Paragraph type="secondary" style={{ marginTop: '12px' }}>
                  It's a good idea to use a strong password that you're not using elsewhere.
                </Paragraph>
              </Card>

              <Card title="Session Management">
                <Button
                  type="primary"
                  danger
                  icon={<LogoutOutlined />}
                  onClick={async () => {
                    message.loading('Logging out...', 0.5);
                    await logout();
                    // Redirection is handled by AuthContext
                  }}
                  loading={authLoading}
                >
                  Logout
                </Button>
                <Paragraph type="secondary" style={{ marginTop: '12px' }}>
                  This will end your current session on this device.
                </Paragraph>
              </Card>
            </TabPane>
          </Tabs>

          <Modal
            title="Change Username"
            open={isUsernameModalVisible}
            onOk={handleUsernameModalOk}
            onCancel={handleUsernameModalCancel}
            confirmLoading={usernameChangeLoading}
            okText="Update Username"
            destroyOnClose
          >
            <Form form={usernameForm} layout="vertical" name="change_username_form_modal">
              <Form.Item
                name="newUsername"
                label="New Username"
                rules={[
                  { required: true, message: 'Please input your new username!' },
                  { min: 3, message: 'Username must be at least 3 characters.' },
                ]}
              >
                <Input prefix={<UserOutlined />} placeholder="New Username" />
              </Form.Item>
              <Form.Item
                name="currentPassword"
                label="Current Password (for verification)"
                rules={[{ required: true, message: 'Please input your current password!' }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Current Password" />
              </Form.Item>
            </Form>
          </Modal>

          <Modal
            title={editingApiKey ? 'Edit API Key' : 'Add API Key'}
            open={isApiKeyModalVisible}
            onOk={handleApiKeySave}
            onCancel={() => setIsApiKeyModalVisible(false)}
            okText={editingApiKey ? 'Update' : 'Create'}
            cancelText="Cancel"
          >
            <Form
              form={apiKeyForm}
              layout="vertical"
              initialValues={{ context: 16000, max_output_tokens: 4000 }}
            >
              <Form.Item
                name="model"
                label="Model Name"
                rules={[{ required: true, message: 'Please enter the model name' }]}
              >
                <Input placeholder="e.g.: deepseek-chat" />
              </Form.Item>

              <Form.Item
                name="base_url"
                label="API Base URL"
                rules={[{ required: true, message: 'Please enter the API base URL' }]}
              >
                <Input placeholder="e.g.: https://api.deepseek.com" />
              </Form.Item>

              <Form.Item
                name="api_key"
                label="API Key"
                rules={[{ required: true, message: 'Please enter the API key' }]}
              >
                <Input.Password placeholder="Enter API Key" />
              </Form.Item>

              <Form.Item
                name="context"
                label="Context Length"
                rules={[
                  { required: true, message: 'Please enter the context length' },
                  { type: 'number', min: 1, message: 'Context length must be a positive integer' }
                ]}
              >
                <InputNumber style={{ width: '100%' }} placeholder="e.g.: 16000" />
              </Form.Item>

              <Form.Item
                name="max_output_tokens"
                label="Max Output Tokens"
                rules={[
                  { required: true, message: 'Please enter the max output tokens' },
                  { type: 'number', min: 1, message: 'Max output tokens must be a positive integer' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('context') > value) {
                      return Promise.resolve();
                      }
                      return Promise.reject(new Error('Context length must be greater than or equal to max output tokens'));
                    },
                  }),
                ]}
              >
                <InputNumber style={{ width: '100%' }} placeholder="e.g.: 4000" />
              </Form.Item>

              <Form.Item
                name="description"
                label="Description"
              >
                <Input.TextArea placeholder="Optional description" />
              </Form.Item>
            </Form>
          </Modal>

          <Modal
            title="Change Password"
            open={isPasswordModalVisible}
            onOk={handlePasswordModalOk}
            onCancel={handlePasswordModalCancel}
            confirmLoading={passwordChangeLoading}
            okText="Update Password"
            destroyOnClose
          >
            <Form
              form={passwordForm}
              layout="vertical"
              name="change_password_form_in_modal"
            >
              <Form.Item
                name="currentPassword"
                label="Current Password"
                rules={[{ required: true, message: 'Please input your current password!' }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Current Password" />
              </Form.Item>
              <Form.Item
                name="newPassword"
                label="New Password"
                rules={[
                  { required: true, message: 'Please input your new password!' },
                  { min: 6, message: 'Password must be at least 6 characters.' },
                ]}
                hasFeedback
              >
                <Input.Password prefix={<LockOutlined />} placeholder="New Password" />
              </Form.Item>
              <Form.Item
                name="confirmNewPassword"
                label="Confirm New Password"
                dependencies={['newPassword']}
                hasFeedback
                rules={[
                  { required: true, message: 'Please confirm your new password!' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('newPassword') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('The new passwords do not match!'));
                    },
                  }),
                ]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Confirm New Password" />
              </Form.Item>
            </Form>
          </Modal>

          <Modal
            title={editingSourceId ? 'Edit Source' : 'Add Source'}
            open={isSourceModalVisible}
            onOk={handleSourceSave}
            onCancel={() => setIsSourceModalVisible(false)}
            okText={editingSourceId ? 'Update' : 'Create'}
            cancelText="Cancel"
            width={600}
          >
            <Form form={sourceForm} layout="vertical">
              <Form.Item
                name="name"
                label="Source Name"
                rules={[{ required: true, message: 'Please enter the source name' }]}
              >
                <Input />
              </Form.Item>

              <Form.Item
                name="url"
                label="URL"
                rules={[
                  { required: true, message: 'Please enter the URL' },
                  { type: 'url', message: 'Please enter a valid URL' }
                ]}
              >
                <Input />
              </Form.Item>

              <Form.Item
                name="category_id"
                label={
                  <Space>
                    <span>Category</span>
                    <Button
                      type="link"
                      icon={<PlusOutlined />}
                      onClick={handleAddCategoryClick}
                      size="small"
                    >
                      Add Category
                    </Button>
                  </Space>
                }
                rules={[{ required: true, message: 'Please select a category' }]}
              >
                <Select>
                  {categories.map(category => (
                    <Option key={category.id} value={category.id}>{category.name}</Option>
                  ))}
                </Select>
              </Form.Item>

              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>Existing Categories:</div>
                <div>
                  {categories.map(category => (
                    <Tag
                      key={category.id}
                      closable
                      onClose={(e) => {
                        e.preventDefault();
                        handleDeleteCategoryTag(category.id);
                      }}
                      style={{ marginBottom: 8 }}
                    >
                      {category.name}
                    </Tag>
                  ))}
                </div>
              </div>
            </Form>
          </Modal>

          <Modal
            title="Add New Category"
            open={isAddCategoryModalVisible}
            onOk={handleCreateCategory}
            onCancel={() => setIsAddCategoryModalVisible(false)}
            okText="Create"
            cancelText="Cancel"
          >
            <Form layout="vertical">
              <Form.Item
                label="Category Name"
                rules={[{ required: true, message: 'Please enter the category name' }]}
              >
                <Input
                  value={newCategoryName}
                  onChange={(e) => setNewCategoryName(e.target.value)}
                  placeholder="Enter new category name"
                />
              </Form.Item>
            </Form>
          </Modal>
        </Col>
      </Row>
    </div> // Changed from MainLayout to a simple div or fragment
  );
};

// Removed withAuth export
export default SettingsContent; // Export the new component