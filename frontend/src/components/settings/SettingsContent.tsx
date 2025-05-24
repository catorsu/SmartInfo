/**
 * @file SettingsContent.tsx
 * @description Provides the main user interface for managing various application
 * settings. This includes general application preferences, API key configuration,
 * news source and category management, and user account settings.
 *
 * @file_purpose To centralize all settings-related UI and logic into a single,
 *               tabbed component for ease of use and maintenance.
 */
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
import { handleApiError, extractErrorMessage } from '@/utils/apiErrorHandler';
import { useAuth } from '@/context/AuthContext';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;

/**
 * @interface ApiKeyFormValues
 * @description Defines the structure for the form values when creating or editing an API key.
 */
interface ApiKeyFormValues {
  model: string;              // The model name associated with the API key (e.g., "deepseek-chat").
  base_url: string;           // The base URL for the API service.
  api_key: string;            // The actual API key string.
  context: number;            // The context length supported by the model.
  max_output_tokens: number;  // The maximum number of output tokens the model can generate.
  description?: string;       // [description] Optional: A user-defined description for the API key.
}

/**
 * @component SettingsContent
 * @description A comprehensive component that renders a tabbed interface for managing
 * various application and user settings. It handles:
 * - General application settings.
 * - API Key management (CRUD operations, testing).
 * - News Source and Category management (CRUD operations).
 * - User Account settings (changing username, password, logout).
 * It interacts with respective services to fetch and update data.
 *
 * @returns {JSX.Element} The rendered settings management UI.
 *
 * @example
 * // Typically used within a Modal in a layout component like MainLayout.tsx
 * // <Modal title="Settings" open={isSettingsModalVisible} onCancel={handleClose}>
 * //   <SettingsContent />
 * // </Modal>
 */
const SettingsContent: React.FC = () => {
  const { user, logout, loading: authLoading, updateUserProfile } = useAuth();
  // State for various settings sections
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [categories, setCategories] = useState<NewsCategory[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);

  // Loading and error states
  const [loading, setLoading] = useState(false); // General loading for initial data fetch
  const [savingSettings, setSavingSettings] = useState(false); // For general settings save
  const [settingsLoading, setSettingsLoading] = useState(true); // For general settings tab
  const [apiKeysLoading, setApiKeysLoading] = useState(true); // For API keys tab
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);

  // API Key Modal state
  const [isApiKeyModalVisible, setIsApiKeyModalVisible] = useState(false);
  const [apiKeyForm] = Form.useForm<ApiKeyFormValues>();
  const [editingApiKeyId, setEditingApiKeyId] = useState<number | null>(null);
  const [editingApiKey, setEditingApiKey] = useState<ApiKey | null>(null); // Stores the API key being edited

  // News Source Modal state
  const [isSourceModalVisible, setIsSourceModalVisible] = useState(false);
  const [sourceForm] = Form.useForm<{ name: string; url: string; category_id: number }>();
  const [editingSourceId, setEditingSourceId] = useState<number | null>(null);

  // News Category Modal state
  const [newCategoryName, setNewCategoryName] = useState<string>('');
  const [isAddCategoryModalVisible, setIsAddCategoryModalVisible] = useState(false);

  // General settings form
  const [settingsForm] = Form.useForm();

  // Account settings modals state
  const [isPasswordModalVisible, setIsPasswordModalVisible] = useState(false);
  const [passwordChangeLoading, setPasswordChangeLoading] = useState(false);
  const [passwordForm] = Form.useForm();

  const [isUsernameModalVisible, setIsUsernameModalVisible] = useState(false);
  const [usernameChangeLoading, setUsernameChangeLoading] = useState(false);
  const [usernameForm] = Form.useForm();

  useEffect(() => {
    loadAllData();
  }, []);

  // Fetches all necessary data for the settings page.
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

  // Fetches general application settings.
  const loadSettings = async () => {
    try {
      setSettingsLoading(true);
      const settingsData = await settingsService.getSettings();
      setSettings(settingsData);
      settingsForm.setFieldsValue(settingsData); // Populate form with fetched settings
    } catch (err: any) {
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setSettingsLoading(false);
    }
  };

  // Fetches API keys.
  const loadApiKeys = async () => {
    try {
      setApiKeysLoading(true);
      const apiKeysData = await settingsService.getApiKeys();
      setApiKeys(apiKeysData);
    } catch (err: any)
      {
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
    } finally {
      setApiKeysLoading(false);
    }
  };

  // Fetches news categories.
  const loadCategories = async () => {
    try {
      const categoriesData = await newsService.getCategories();
      setCategories(categoriesData);
    } catch (err: any) {
      // Error is logged, but not set to global error state to allow other sections to load
      console.error('Failed to load categories:', err);
    }
  };

  // Fetches news sources.
  const loadSources = async () => {
    try {
      const sourcesData = await newsService.getSources();
      setSources(sourcesData);
    } catch (err: any) {
      // Error is logged, but not set to global error state
      console.error('Failed to load sources:', err);
    }
  };
  // Handles changes to individual general settings (currently not directly used by UI, form handles it).
  const handleSettingChange = (key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Saves general application settings.
  const saveSettings = async (values: Record<string, any>) => {
    try {
      setSavingSettings(true);
      const result = await settingsService.updateSettings(values);
      setSettings(result.settings); // Assuming backend returns updated settings object
      message.success('Settings saved successfully');
    } catch (error) {
      handleApiError(error, 'Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  // Resets general application settings to their default values.
  const resetSettings = async () => {
    try {
      setLoading(true); // Use general loading for this action
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
  // Shows the modal for adding a new API key.
  const showAddApiKeyModal = () => {
    apiKeyForm.resetFields();
    setEditingApiKey(null); // Ensure not in edit mode
    setEditingApiKeyId(null);
    setIsApiKeyModalVisible(true);
  };

  // Shows the modal for editing an existing API key, pre-filling the form.
  const showEditApiKeyModal = (record: ApiKey) => {
    setEditingApiKey(record); // Store the key being edited
    setEditingApiKeyId(record.id);
    settingsService.getApiKey(record.id) // Fetch full details in case table has partial data
      .then(apiKeyData => {
        if (apiKeyData === null) { // Should not happen if record exists, but good check
          message.error('API key not found or has been deleted');
          setIsApiKeyModalVisible(false);
          setEditingApiKey(null);
          setEditingApiKeyId(null);
          return;
        }
        apiKeyForm.setFieldsValue({
          model: apiKeyData.model,
          base_url: apiKeyData.base_url,
          api_key: apiKeyData.api_key, // This will be the actual key
          context: apiKeyData.context,
          max_output_tokens: apiKeyData.max_output_tokens,
          description: apiKeyData.description
        });
        setIsApiKeyModalVisible(true);
      })
      .catch(error => {
        handleApiError(error, 'Failed to load API key details');
        setIsApiKeyModalVisible(false);
        setEditingApiKey(null);
        setEditingApiKeyId(null);
      });
  };

  // Handles saving (create or update) of an API key.
  const handleApiKeySave = async () => {
    try {
      const values = await apiKeyForm.validateFields();

      if (editingApiKeyId && editingApiKey) { // Check editingApiKeyId for clarity
        await settingsService.updateApiKey(editingApiKeyId, values);
        message.success('API key updated successfully');
      } else {
        await settingsService.createApiKey(values);
        message.success('API key created successfully');
      }

      setIsApiKeyModalVisible(false);
      loadApiKeys(); // Refresh the list
    } catch (error) {
      handleApiError(error, 'Failed to save API key');
    }
  };

  // Handles deletion of an API key.
  const handleDeleteApiKey = async (apiKeyId: number) => {
    try {
      await settingsService.deleteApiKey(apiKeyId);
      message.success('API key deleted successfully');
      loadApiKeys(); // Refresh the list
    } catch (error) {
      handleApiError(error, 'Failed to delete API key');
    }
  };
  // Tests the connection for a given API key.
  const handleTestApiKey = async (apiKeyId: number) => {
    const testMessage = message.loading('Testing API key connection...', 0); // Indefinite loading message

    try {
      const result = await settingsService.testApiKey(apiKeyId);
      testMessage(); // Close loading message

      if (result.status === 'success') {
        message.success('Connection test successful!');
      } else {
        message.error(`Test failed: ${result.message}`);
      }
    } catch (error) {
      testMessage(); // Close loading message on error
      handleApiError(error, 'Failed to test API key');
    }
  };
  // Shows the modal for adding a new news source.
  const showAddSourceModal = () => {
    sourceForm.resetFields();
    setEditingSourceId(null); // Ensure not in edit mode
    setIsSourceModalVisible(true);
  };

  // Shows the modal for editing an existing news source, pre-filling the form.
  const showEditSourceModal = (record: NewsSource) => {
    sourceForm.setFieldsValue({
      name: record.name,
      url: record.url,
      category_id: record.category_id
    });
    setEditingSourceId(record.id);
    setIsSourceModalVisible(true);
  };

  // Handles saving (create or update) of a news source.
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
      loadSources(); // Refresh the list
    } catch (error) {
      // Using console.error for detailed logging, message.error for user feedback
      console.error('Failed to save source:', error);
      message.error('Failed to save source. Check console for details.');
    }
  };

  // Handles deletion of a news source.
  const handleDeleteSource = async (id: number) => {
    try {
      await newsService.deleteSource(id);
      message.success('Source deleted successfully');
      loadSources(); // Refresh the list
    } catch (error) {
      console.error('Failed to delete source:', error);
      message.error('Failed to delete source. Check console for details.');
    }
  };
  // Shows the modal for adding a new news category.
  const handleAddCategoryClick = () => {
    setNewCategoryName(''); // Reset input field
    setIsAddCategoryModalVisible(true);
  };

  // Handles creation of a new news category.
  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) {
      message.error('Category name cannot be empty');
      return;
    }

    try {
      const newCategory = await newsService.createCategory({ name: newCategoryName });
      message.success('Category created successfully');
      await loadCategories(); // Refresh category list
      setIsAddCategoryModalVisible(false);
      // Optionally, select the new category in the source form if it's open
      sourceForm.setFieldsValue({ category_id: newCategory.id });
    } catch (error) {
      handleApiError(error, 'Failed to create category');
    }
  };

  // Handles deletion of a news category tag.
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
          await loadCategories(); // Refresh category list
        } catch (error) {
          handleApiError(error, 'Failed to delete category');
        }
      }
    });
  };
  // Column definitions for the API Keys table.
  const apiKeyColumns: TableProps<ApiKey>['columns'] = [
    {
      title: 'Model',
      dataIndex: 'model',
      key: 'model',
    },
    {
      title: 'API Key',
      key: 'api_key',
      render: () => '••••••••', // Mask the API key for security
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
      title: () => ( // Custom title with Add button
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

  // Column definitions for the News Sources table.
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
      dataIndex: 'category', // This should be category_id or category_name from backend
      key: 'category',
      render: (_, record) => {
        const category = categories.find(c => c.id === record.category_id);
        return category ? category.name : '-';
      },
    },
    {
      title: () => ( // Custom title with Add button
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

  // Handles password change modal confirmation.
  const handlePasswordModalOk = async () => {
    try {
      const values = await passwordForm.validateFields();
      await handleChangePassword(values);
    } catch (formError) {
      // Validation error, antd form handles message display
      console.log('Password form validation failed:', formError);
    }
  };

  const handlePasswordModalCancel = () => {
    setIsPasswordModalVisible(false);
    passwordForm.resetFields();
  };

  // Handles username change modal confirmation.
  const handleUsernameModalOk = async () => {
    try {
      const values = await usernameForm.validateFields();
      await handleChangeUsername(values);
    } catch (formError) {
      // Validation error
      console.log('Username form validation failed:', formError);
    }
  };

  const handleUsernameModalCancel = () => {
    setIsUsernameModalVisible(false);
    usernameForm.resetFields();
  };

  // Submits username change request to the backend.
  const handleChangeUsername = async (values: any) => {
    setUsernameChangeLoading(true);
    try {
      const updatedUser = await authService.changeUsername({
        new_username: values.newUsername,
        current_password: values.currentPassword, // Password for verification
      });
      message.success('Username successfully changed!');
      if (typeof updateUserProfile === 'function') {
          updateUserProfile(updatedUser); // Update user in AuthContext
      }
      setIsUsernameModalVisible(false);
      usernameForm.resetFields();
    } catch (apiError: any) {
      message.error(extractErrorMessage(apiError).message || 'Failed to change username.');
    } finally {
      setUsernameChangeLoading(false);
    }
  };
  // Submits password change request to the backend.
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

  return (
    <div>
      <Row justify="center" style={{ width: '100%' }}>
        <Col xs={24} sm={24} md={24} lg={23} xl={22}>
          <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>System Settings</Title>

          {error && ( // Global error display for initial load issues
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
                    loading={loading && savingSettings} // Show loading if general load or save is in progress
                    >
                      {/* Text can be added if not collapsed: Reset */}
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
                    {/* Dynamically render form items based on fetched settings */}
                    {Object.entries(settings).map(([key, value]) => (
                      <Form.Item
                        key={key}
                        name={key}
                        // Attempt to make label more readable
                        label={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      >
                        {/* Basic input, could be enhanced based on value type if known */}
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
                    pagination={false} // Consider adding pagination if list can be long
                  />
                </Spin>
            </TabPane>

            <TabPane
              tab={<><ApiOutlined /> News Sources</>}
              key="sources"
              >
              <Table // Table for News Sources
              dataSource={sources}
                columns={sourceColumns} // Uses sourceColumns defined earlier
                rowKey="id"
                loading={loading && sources.length === 0} // Show loading if general load and no sources yet
                pagination={{ pageSize: 5 }} // Example pagination
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
                    {/* Add other user info if available, e.g., email, ID */}
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
                    message.loading('Logging out...', 0.5); // Brief visual feedback
                    await logout();
                    // Redirection is handled by AuthContext after logout
                  }}
                  loading={authLoading} // Disable button while auth operations are in progress
                >
                  Logout
                </Button>
                <Paragraph type="secondary" style={{ marginTop: '12px' }}>
                  This will end your current session on this device.
                </Paragraph>
              </Card>
            </TabPane>
          </Tabs>

          {/* Modal for Changing Username */}
          <Modal
            title="Change Username"
            open={isUsernameModalVisible}
            onOk={handleUsernameModalOk}
            onCancel={handleUsernameModalCancel}
            confirmLoading={usernameChangeLoading}
            okText="Update Username"
            destroyOnClose // Reset form state when modal is closed
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

          {/* Modal for Adding/Editing API Key */}
          <Modal
            title={editingApiKeyId ? 'Edit API Key' : 'Add API Key'}
            open={isApiKeyModalVisible}
            onOk={handleApiKeySave}
            onCancel={() => setIsApiKeyModalVisible(false)}
            okText={editingApiKeyId ? 'Update' : 'Create'}
            cancelText="Cancel"
          >
            <Form
              form={apiKeyForm}
              layout="vertical"
              initialValues={{ context: 16000, max_output_tokens: 4000 }} // Default values
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
                  // Validator to ensure max_output_tokens <= context
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('context') >= value) { // Corrected logic
                      return Promise.resolve();
                      }
                      return Promise.reject(new Error('Max output tokens cannot exceed context length.'));
                    },
                  }),
                ]}
              >
                <InputNumber style={{ width: '100%' }} placeholder="e.g.: 4000" />
              </Form.Item>

              <Form.Item
                name="description"
                label="Description" // Optional field
              >
                <Input.TextArea placeholder="Optional description for this API key" />
              </Form.Item>
            </Form>
          </Modal>

          {/* Modal for Changing Password */}
          <Modal
            title="Change Password"
            open={isPasswordModalVisible}
            onOk={handlePasswordModalOk}
            onCancel={handlePasswordModalCancel}
            confirmLoading={passwordChangeLoading}
            okText="Update Password"
            destroyOnClose // Reset form state when modal is closed
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
                hasFeedback // Shows validation status icon
              >
                <Input.Password prefix={<LockOutlined />} placeholder="New Password" />
              </Form.Item>
              <Form.Item
                name="confirmNewPassword"
                label="Confirm New Password"
                dependencies={['newPassword']} // Validates against newPassword field
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

          {/* Modal for Adding/Editing News Source */}
          <Modal
            title={editingSourceId ? 'Edit Source' : 'Add Source'}
            open={isSourceModalVisible}
            onOk={handleSourceSave}
            onCancel={() => setIsSourceModalVisible(false)}
            okText={editingSourceId ? 'Update' : 'Create'}
            cancelText="Cancel"
            width={600} // Wider modal for better form layout
          >
            <Form form={sourceForm} layout="vertical">
              <Form.Item
                name="name"
                label="Source Name"
                rules={[{ required: true, message: 'Please enter the source name' }]}
              >
                <Input placeholder="e.g., BBC News" />
              </Form.Item>

              <Form.Item
                name="url"
                label="URL"
                rules={[
                  { required: true, message: 'Please enter the URL' },
                  { type: 'url', message: 'Please enter a valid URL' }
                ]}
              >
                <Input placeholder="e.g., https://www.bbc.com/news" />
              </Form.Item>

              <Form.Item
                name="category_id"
                label={ // Custom label with "Add Category" button
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
                <Select placeholder="Select a category">
                  {categories.map(category => (
                    <Option key={category.id} value={category.id}>{category.name}</Option>
                  ))}
                </Select>
              </Form.Item>

              {/* Display existing categories with delete option */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>Existing Categories:</div>
                <div>
                  {categories.map(category => (
                    <Tag
                      key={category.id}
                      closable
                      onClose={(e) => {
                        e.preventDefault(); // Prevent default tag close behavior if any
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

          {/* Modal for Adding New Category */}
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
                // Validation can be added here if using Form instance for this modal
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
    </div>
  );
};

export default SettingsContent;