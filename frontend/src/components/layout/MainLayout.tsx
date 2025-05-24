/**
 * @file MainLayout.tsx
 * @description Provides the primary authenticated application layout, including sidebar,
 * content area, global UI elements like FABs, Fetch News Modal, and Task Progress Drawer.
 * It manages navigation, chat list display, and provides PageActionContext for global actions.
 *
 * @file_purpose Central layout component for authenticated users, managing global UI states
 *               and interactions.
 */
import React, { useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { Layout, Menu, Button, Input, Space, Typography, Divider, Spin, Avatar, Tooltip, Dropdown, Modal, Form as AntForm, message, FloatButton, Checkbox, Select, Drawer, Progress, Empty, Alert, Badge, DatePicker, List } from 'antd';
import type { CheckboxChangeEvent } from 'antd/es/checkbox';
import type { MenuProps } from 'antd';
import {
  ReadOutlined,
  MessageOutlined,
  SettingOutlined,
  PlusOutlined,
  SearchOutlined,
  LogoutOutlined,
  AppstoreOutlined,
  EllipsisOutlined,
  DownloadOutlined,
  BarsOutlined,
  HistoryOutlined,
  DeleteOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  SyncOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { Chat, NewsCategory, NewsSource, FetchTaskItem, FetchHistoryItem } from '@/utils/types';
import * as chatService from '@/services/chatService';
import * as newsService from '@/services/newsService';
import { extractErrorMessage, handleApiError as globalHandleApiError } from '@/utils/apiErrorHandler';
import axios from 'axios';
import styles from './MainLayout.module.css';
import SettingsContent from '@/components/settings/SettingsContent';
import PageActionContext, { PageActionContextType } from '@/context/PageActionContext';
import dayjs from 'dayjs';

const { Sider, Content } = Layout;
const { Text, Title } = Typography;
const { Option } = Select;

/**
 * @function formatChatDate
 * @description Formats a chat timestamp into a human-readable date group string
 * (e.g., "Today", "Yesterday", "Others").
 *
 * @param {number | string | undefined | null} timestampInput - The chat timestamp.
 *        Can be a Unix timestamp (number, in seconds), an ISO date string, or null/undefined.
 * @returns {string} The formatted date group string.
 */
const formatChatDate = (timestampInput: number | string | undefined | null): string => {
  if (!timestampInput) return 'Others';
  let chatTimestamp: number;
  if (typeof timestampInput === 'string') {
    const parsedDate = new Date(timestampInput);
    // Assuming numeric strings might be Unix timestamps in seconds.
    chatTimestamp = isNaN(parsedDate.getTime()) ? (parseInt(timestampInput, 10) * 1000) : parsedDate.getTime();
  } else if (typeof timestampInput === 'number') {
    chatTimestamp = timestampInput * 1000; // Assuming number is Unix timestamp in seconds.
  } else return 'Others';
  if (isNaN(chatTimestamp)) return 'Others';

  const now = new Date();
  const chatDate = new Date(chatTimestamp);
  if (now.toDateString() === chatDate.toDateString()) return 'Today';
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (yesterday.toDateString() === chatDate.toDateString()) return 'Yesterday';
  return 'Others';
};

/**
 * @function groupChatsByDate
 * @description Groups an array of chat objects by their creation date into
 * predefined categories ("Today", "Yesterday", "Others").
 *
 * @param {Chat[]} chats - An array of Chat objects.
 * @returns {Record<string, Chat[]>} An object where keys are date group strings
 *          and values are arrays of chats belonging to that group.
 */
const groupChatsByDate = (chats: Chat[]) => {
  const groups: Record<string, Chat[]> = { 'Today': [], 'Yesterday': [], 'Others': [] };
  chats.forEach(chat => groups[formatChatDate(chat.created_at)].push(chat));
  return groups;
};

/**
 * @typedef {enum} TaskStep
 * @description Represents the different steps or states of a news fetching task.
 */
enum TaskStep {
  Preparing = 1,        // Task is being prepared.
  Crawling = 2,         // Actively crawling the source.
  ExtractingLinks = 3,  // Extracting article links from crawled content.
  Analyzing = 4,        // Analyzing content (if applicable).
  Saving = 5,           // Saving extracted data to the database.
  Complete = 6,         // Task finished successfully.
  Error = 7,            // An error occurred during the task.
  Skipped = 8,          // Task was skipped (e.g., due to recent fetch).
}

/**
 * @function getStepDisplayString
 * @description Converts a TaskStep enum value or its numeric code into a
 * human-readable string.
 *
 * @param {TaskStep | number} stepCode - The task step code.
 * @returns {string} The display string for the task step.
 */
const getStepDisplayString = (stepCode: TaskStep | number): string => {
  switch (stepCode) {
    case TaskStep.Preparing: return 'Preparing';
    case TaskStep.Crawling: return 'Crawling';
    case TaskStep.ExtractingLinks: return 'Extracting Links';
    case TaskStep.Analyzing: return 'Analyzing';
    case TaskStep.Saving: return 'Saving';
    case TaskStep.Complete: return 'Complete';
    case TaskStep.Error: return 'Error';
    case TaskStep.Skipped: return 'Skipped';
    default: return 'Unknown';
  }
};

/**
 * @interface MainLayoutProps
 * @description Defines the props for the MainLayout component.
 */
interface MainLayoutProps {
  children: ReactNode; // The content to be rendered within the main layout area.
}

/**
 * @component MainLayout
 * @description The main application layout for authenticated users. It includes a
 * collapsible sidebar for navigation and chat history, a central content area,
 * and global UI elements such as a Floating Action Button group for quick actions
 * (fetching news, viewing task progress, accessing settings), and modals/drawers
 * for these actions. It provides `PageActionContext` to its children, allowing
 * them to trigger these global UI elements.
 *
 * @param {ReactNode} children - The child components to be rendered within the main content area.
 *
 * @returns {JSX.Element} The rendered main application layout.
 *
 * @example
 * // In _app.tsx or a similar top-level component:
 * <MainLayout>
 *   <CurrentPageContent />
 * </MainLayout>
 */
const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const router = useRouter();
  const { isAuthenticated, user, logout, loading: authLoading, setRefreshChatListCallback, token } = useAuth();

  const [collapsed, setCollapsed] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [chats, setChats] = useState<Chat[]>([]);
  const [filteredChats, setFilteredChats] = useState<Chat[]>([]);
  const [selectedKey, setSelectedKey] = useState('news'); // Tracks the currently selected menu item.
  const [hoveredChatId, setHoveredChatId] = useState<number | null>(null); // For showing chat actions on hover.

  // State for rename chat modal
  const [isRenameModalVisible, setIsRenameModalVisible] = useState(false);
  const [renamingChatDetails, setRenamingChatDetails] = useState<{ id: number; currentTitle: string } | null>(null);
  const [renameForm] = AntForm.useForm();

  // State for settings modal
  const [isSettingsModalVisible, setIsSettingsModalVisible] = useState(false);

  // State for Fetch News Modal
  const [isFetchModalVisible, setIsFetchModalVisible] = useState<boolean>(false);
  const [fetchModalCategories, setFetchModalCategories] = useState<NewsCategory[]>([]);
  const [fetchModalSources, setFetchModalSources] = useState<NewsSource[]>([]);
  const [selectedFetchCategory, setSelectedFetchCategory] = useState<number | undefined>(undefined);
  const [filteredFetchSources, setFilteredFetchSources] = useState<NewsSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [selectAllSources, setSelectAllSources] = useState<boolean>(false);
  const [isIndeterminate, setIsIndeterminate] = useState<boolean>(false); // For "Select All" checkbox state.
  const [fetchModalLoading, setFetchModalLoading] = useState(false);

  // State for Task Progress Drawer
  const [isTaskDrawerVisible, setIsTaskDrawerVisible] = useState<boolean>(false);
  const [tasksToMonitor, setTasksToMonitor] = useState<FetchTaskItem[]>([]); // Live tasks from current session.
  const [taskGroupId, setTaskGroupId] = useState<string | null>(null); // ID for WebSocket connection.
  const wsRef = useRef<WebSocket | null>(null); // WebSocket connection reference.
  const [todaysHistory, setTodaysHistory] = useState<FetchHistoryItem[]>([]); // Fetched history for today.
  const [isHistoryLoading, setIsHistoryLoading] = useState<boolean>(false);
  const [historicalData, setHistoricalData] = useState<FetchHistoryItem[] | null>(null); // For specific past dates.
  const [viewingDate, setViewingDate] = useState<'today' | 'history'>('today'); // Toggle for drawer view.
  const [selectedHistoryDate, setSelectedHistoryDate] = useState<dayjs.Dayjs | null>(null);

  // Callbacks for PageActionContext
  const requestOpenFetchModal = useCallback(() => setIsFetchModalVisible(true), [setIsFetchModalVisible]);
  const requestOpenTaskDrawer = useCallback(() => setIsTaskDrawerVisible(true), [setIsTaskDrawerVisible]);

  // Context value provided to children for triggering global actions.
  const pageActions: PageActionContextType = {
    requestOpenFetchModal,
    requestOpenTaskDrawer,
  };

  // Effect to synchronize sidebar menu selection with the current route.
  useEffect(() => {
    const path = router.pathname;
    if (path === '/' || path.startsWith('/news') || path.startsWith('/analyze')) setSelectedKey('news');
    else if (path.startsWith('/chat/')) setSelectedKey(router.query.id ? `chat-${router.query.id}` : 'chat-list');
    else if (path === '/chat') setSelectedKey('chat-list'); // Default for /chat page itself
  }, [router.pathname, router.query.id]);

  // Callback to load chat list, used by AuthContext for refresh.
  const loadChats = useCallback(async () => {
    if (isAuthenticated) {
      try {
        const result = await chatService.getChats();
        setChats(result);
        setFilteredChats(result); // Initialize filtered list
      } catch (error) { console.error('Failed to load chats:', error); setChats([]); setFilteredChats([]); }
    } else { setChats([]); setFilteredChats([]); }
  }, [isAuthenticated]);

  // Effect to load chats on auth status change and set up refresh callback.
  useEffect(() => {
    if (!authLoading) loadChats();
    if (setRefreshChatListCallback) setRefreshChatListCallback(loadChats);
    return () => { if (setRefreshChatListCallback) setRefreshChatListCallback(null); }; // Cleanup callback
  }, [authLoading, loadChats, setRefreshChatListCallback]);

  // Effect to filter chat list based on search text.
  useEffect(() => {
    setFilteredChats(searchText.trim() ? chats.filter(chat => chat.title.toLowerCase().includes(searchText.toLowerCase())) : chats);
  }, [searchText, chats]);

  const handleNewChat = () => router.pathname !== '/chat' && router.push('/chat');
  const groupedChats = groupChatsByDate(filteredChats);

  const mainMenuItems: MenuProps['items'] = [{ key: 'news', icon: <ReadOutlined />, label: <Link href="/">News Feed</Link> }];
  const bottomMenuItems: MenuProps['items'] = []; // Placeholder for potential bottom menu items.

  // Handler to show the rename chat modal.
  const showRenameModal = (chatId: number, currentTitle: string) => {
    setRenamingChatDetails({ id: chatId, currentTitle });
    renameForm.setFieldsValue({ newTitle: currentTitle });
    setIsRenameModalVisible(true);
  };

  // Handler to delete a chat session.
  const handleDeleteChat = (chatId: number) => {
    Modal.confirm({
      title: 'Delete Chat',
      content: 'Are you sure you want to delete this chat session and all its messages?',
      okText: 'Delete', okType: 'danger', cancelText: 'Cancel',
      onOk: async () => {
        try {
          await chatService.deleteChat(chatId);
          message.success('Chat deleted successfully');
          loadChats(); // Refresh chat list
          // If current chat was deleted, navigate away or to another chat.
          if (router.query.id && parseInt(router.query.id as string) === chatId) router.push('/chat');
          else if (selectedKey === `chat-${chatId}`) { // If deleted chat was selected in menu
            const newChats = chats.filter(c => c.id !== chatId);
            if (newChats.length > 0) { /* Potentially navigate to first chat: router.push(`/chat/${newChats[0].id}`); */ }
            else router.push('/chat'); // Or back to default chat page
          }
        } catch (error) { message.error(extractErrorMessage(error).message || 'Failed to delete chat'); }
      },
    });
  };

  // Handler for confirming chat rename.
  const handleRenameOk = async () => {
    if (!renamingChatDetails) return;
    try {
      const values = await renameForm.validateFields();
      await chatService.updateChat(renamingChatDetails.id, { title: values.newTitle });
      message.success('Chat renamed successfully');
      loadChats(); // Refresh chat list
      setIsRenameModalVisible(false);
      renameForm.resetFields();
    } catch (errorInfo) {
      if (axios.isAxiosError(errorInfo)) message.error(extractErrorMessage(errorInfo).message || 'Failed to rename chat.');
      else console.log('Rename form validation failed:', errorInfo);
    }
  };
  const handleRenameCancel = () => { setIsRenameModalVisible(false); renameForm.resetFields(); };

  const handleShowSettingsModal = () => setIsSettingsModalVisible(true);
  const handleCloseSettingsModal = () => setIsSettingsModalVisible(false);

  // Effect to load data for the Fetch News Modal when it becomes visible.
  useEffect(() => {
    const loadModalData = async () => {
      if (isFetchModalVisible) {
        setFetchModalLoading(true);
        try {
          const [categoriesData, sourcesData] = await Promise.all([ newsService.getCategories(), newsService.getSources() ]);
          setFetchModalCategories(categoriesData); setFetchModalSources(sourcesData); setFilteredFetchSources(sourcesData);
        } catch (err) { globalHandleApiError(err, 'Failed to load data for fetch modal'); }
        finally { setFetchModalLoading(false); }
      }
    };
    loadModalData();
  }, [isFetchModalVisible]);

  // Handlers for Fetch News Modal interactions.
  const handleFetchCategoryChange = (value: number | undefined) => {
    setSelectedFetchCategory(value);
    const newFilteredSources = value === undefined ? fetchModalSources : fetchModalSources.filter(s => s.category_id === value);
    setFilteredFetchSources(newFilteredSources);
    // Reset source selection when category changes.
    setSelectedSourceIds([]); setSelectAllSources(false); setIsIndeterminate(false);
  };
  const handleSourceSelectionChange = (checkedValues: any[]) => {
    const numberValues = checkedValues as number[]; // Ensure values are numbers.
    setSelectedSourceIds(numberValues);
    const allVisibleSourceIds = filteredFetchSources.map(s => s.id);
    setSelectAllSources(allVisibleSourceIds.length > 0 && numberValues.length === allVisibleSourceIds.length);
    setIsIndeterminate(numberValues.length > 0 && numberValues.length < allVisibleSourceIds.length);
  };
  const handleSelectAllChange = (e: CheckboxChangeEvent) => {
    const isChecked = e.target.checked;
    setSelectedSourceIds(isChecked ? filteredFetchSources.map(s => s.id) : []);
    setSelectAllSources(isChecked); setIsIndeterminate(false);
  };
  // Confirms fetch operation, adds tasks to monitor, and opens task drawer.
  const handleFetchConfirmInMainLayout = async () => {
    if (selectedSourceIds.length === 0) { message.warning('Please select at least one news source.'); return; }
    const selectedSourcesDetails = fetchModalSources.filter(s => selectedSourceIds.includes(s.id));
    // Prepare tasks for UI display.
    const newTasks: FetchTaskItem[] = selectedSourcesDetails.map(source => ({ sourceId: source.id, sourceName: source.name, status: 'Pending', progress: 0 }));
    setTasksToMonitor(prevTasks => [ ...prevTasks.filter(t => t.status !== 'Complete' && t.status !== 'Error' && t.status !== 'Skipped'), ...newTasks ]);
    setViewingDate('today'); setHistoricalData(null); fetchTodaysHistory(); // Switch to today's view in drawer.
    setIsFetchModalVisible(false); setIsTaskDrawerVisible(true); // Show progress.
    try {
      const response = await newsService.fetchNewsFromSourcesBatchGroup(selectedSourceIds);
      setTaskGroupId(response.task_group_id); // For WebSocket connection.
    } catch (error) {
      globalHandleApiError(error, 'Failed to start news fetch tasks');
      // Remove tasks that failed to initiate.
      setTasksToMonitor(prevTasks => prevTasks.filter(task => !selectedSourceIds.includes(task.sourceId)));
    } finally {
      // Reset modal state.
      setSelectedSourceIds([]); setSelectedFetchCategory(undefined); setFilteredFetchSources(fetchModalSources);
      setSelectAllSources(false); setIsIndeterminate(false);
    }
  };

  // Fetches today's news fetch history for the Task Progress Drawer.
  const fetchTodaysHistory = useCallback(async () => {
    setIsHistoryLoading(true);
    try {
      const todayStr = dayjs().format('YYYY-MM-DD');
      const history = await newsService.getFetchHistory({ date: todayStr });
      setTodaysHistory(history);
    } catch (error) { globalHandleApiError(error, "Failed to load today's fetch history"); setTodaysHistory([]); }
    finally { setIsHistoryLoading(false); }
  }, []);

  // Fetches historical news fetch data for a specific date.
  const fetchHistoricalData = useCallback(async (date: string | null) => {
    if (!date) { setHistoricalData(null); return; }
    setIsHistoryLoading(true); setHistoricalData(null); // Clear previous historical data.
    try {
      const history = await newsService.getFetchHistory({ date });
      setHistoricalData(history);
    } catch (error) { globalHandleApiError(error, `Failed to load fetch history for ${date}`); }
    finally { setIsHistoryLoading(false); }
  }, []);

  // Manages WebSocket connection for real-time task updates.
  const connectWebSocket = useCallback((currentTaskGroupId: string) => {
    if (wsRef.current) wsRef.current.close(); // Close existing connection if any.
    if (!token) { message.error('Authentication token not found for WebSocket.'); return; }
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Ensure API URL is correctly transformed for WebSocket.
    const apiUrlBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/^http/, 'ws').replace(/\/$/, '');
    const wsUrl = `${apiUrlBase}/api/tasks/ws/tasks/group/${currentTaskGroupId}?token=${encodeURIComponent(token)}`;
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => console.log(`WebSocket connected for task group ${currentTaskGroupId}`);
      ws.onmessage = (event) => {
        try {
          const taskUpdate = JSON.parse(event.data as string);
          // Handle batch failure event.
          if (taskUpdate.event === "batch_task_failed") {
            if (taskUpdate.affected_source_ids && Array.isArray(taskUpdate.affected_source_ids)) {
              setTasksToMonitor(prevTasks => prevTasks.map(task => 
                (taskUpdate.affected_source_ids as number[]).includes(task.sourceId) && (task.progress ?? 0) < 100 ? 
                { ...task, status: 'Error', progress: 100, message: 'Batch failed' } : task
              ));
            } return;
          }
          // Handle overall batch completion event.
          if (taskUpdate.event === "overall_batch_completed") {
            console.log(`Overall batch group ${currentTaskGroupId} finished: ${taskUpdate.status}`);
            if (router.pathname === '/') router.replace(router.asPath); // Refresh news page if current.
            fetchTodaysHistory(); // Update history.
            // Close WebSocket after a short delay.
            setTimeout(() => { if (wsRef.current) wsRef.current.close(); wsRef.current = null; setTaskGroupId(null); }, 1000);
            return;
          }
          // Handle individual source progress update.
          if (taskUpdate.event === "source_progress" && taskUpdate.source_id !== undefined) {
            setTasksToMonitor(prevTasks => {
              const taskIndex = prevTasks.findIndex(t => t.sourceId === taskUpdate.source_id);
              if (taskIndex === -1) return prevTasks; // Should not happen if task was added.
              const updatedTasks = [...prevTasks];
              const taskToUpdate = { ...updatedTasks[taskIndex] };
              taskToUpdate.status = getStepDisplayString(taskUpdate.step as TaskStep);
              taskToUpdate.progress = taskUpdate.progress ?? taskToUpdate.progress;
              if (taskUpdate.step === TaskStep.Error) taskToUpdate.error = true;
              if (taskUpdate.items_saved !== undefined) taskToUpdate.items_saved_this_run = taskUpdate.items_saved as number;
              // Mark as 100% progress if terminal state.
              if (taskUpdate.step === TaskStep.Error || taskUpdate.step === TaskStep.Skipped || taskUpdate.step === TaskStep.Complete) taskToUpdate.progress = 100;
              updatedTasks[taskIndex] = taskToUpdate;
              return updatedTasks;
            }); return;
          }
        } catch (e) { console.error('Failed to parse WebSocket message:', e); }
      };
      ws.onerror = (error) => { console.error('WebSocket error:', error); message.error('WebSocket connection error.'); wsRef.current = null; setTaskGroupId(null); };
      ws.onclose = (event) => {
        console.log(`WebSocket closed for task group ${currentTaskGroupId}. Code: ${event.code}`);
        if (wsRef.current === ws) wsRef.current = null; // Clear ref only if it's the same instance.
      };
    } catch (err) { console.error("Failed to create WebSocket:", err); message.error("Failed to initialize WebSocket."); }
  }, [token, fetchTodaysHistory, router]); // Dependencies for WebSocket connection logic.

  // Effect to establish/close WebSocket connection when taskGroupId changes.
  useEffect(() => {
    if (taskGroupId) connectWebSocket(taskGroupId);
    return () => { if (wsRef.current) { wsRef.current.close(); wsRef.current = null; } }; // Cleanup on unmount.
  }, [taskGroupId, connectWebSocket]);

  // Effect to fetch today's history on initial mount.
  useEffect(() => { fetchTodaysHistory(); }, [fetchTodaysHistory]);

  // Logic to determine tasks displayed in the Task Progress Drawer.
  const getDisplayedTasks = () => {
    let displayed: (FetchTaskItem | FetchHistoryItem)[] = [];
    const processedSourceIds = new Set<number>(); // To avoid duplicates if a task is live and also in history.
    // Add live tasks first.
    tasksToMonitor.forEach(task => { displayed.push(task); processedSourceIds.add(task.sourceId); });
    // Add historical tasks based on selected view.
    if (viewingDate === 'today') todaysHistory.forEach(hist => !processedSourceIds.has(hist.source_id) && displayed.push(hist));
    else if (historicalData) displayed = [...historicalData]; // For specific past date.
    // Sort tasks: live tasks first, then by time.
    displayed.sort((a, b) => {
      const isALive = 'progress' in a && a.status !== 'Complete' && a.status !== 'Error' && a.status !== 'Skipped';
      const isBLive = 'progress' in b && b.status !== 'Complete' && b.status !== 'Error' && b.status !== 'Skipped';
      if (isALive && !isBLive) return -1; if (!isALive && isBLive) return 1;
      // For sorting, use last_updated_at if available, otherwise use current time for live tasks.
      const timeA = 'last_updated_at' in a && a.last_updated_at ? new Date(a.last_updated_at).getTime() : ('sourceId' in a ? Date.now() : 0);
      const timeB = 'last_updated_at' in b && b.last_updated_at ? new Date(b.last_updated_at).getTime() : ('sourceId' in b ? Date.now() : 0);
      return timeB - timeA; // Sort descending by time (most recent first).
    });
    return displayed;
  };
  const displayedTasks = getDisplayedTasks();
  // Helper functions to access properties from union type in Task Drawer list.
  const getSourceId = (item: FetchTaskItem | FetchHistoryItem): number => 'sourceId' in item ? item.sourceId : item.source_id;
  const getSourceName = (item: FetchTaskItem | FetchHistoryItem): string => 'sourceName' in item ? item.sourceName : item.source_name;
  const getStatus = (item: FetchTaskItem | FetchHistoryItem): string => 'status' in item ? item.status : 'Complete'; // Default to 'Complete' for history items.
  const getProgress = (item: FetchTaskItem | FetchHistoryItem): number => 'progress' in item ? item.progress || 0 : 100; // Default to 100% for history items.
  const getItemsSavedThisRun = (item: FetchTaskItem | FetchHistoryItem): number | undefined => 'items_saved_this_run' in item ? item.items_saved_this_run : ('items_saved_today' in item ? item.items_saved_today : undefined);
  
  const handleHistoryDateChange = (date: dayjs.Dayjs | null, dateString: string | string[]) => {
    setSelectedHistoryDate(date);
    if (dateString && typeof dateString === 'string') fetchHistoricalData(dateString);
    else if (Array.isArray(dateString) && dateString.length > 0) fetchHistoricalData(dateString[0]);
    else setHistoricalData(null); // Clear if date is cleared.
  };
  // Navigates to news feed filtered by source and date when a task badge is clicked.
  const handleTaskBadgeClickInMainLayout = (sourceId: number, fetchDate: string) => {
    router.push(`/?source_id=${sourceId}&fetch_date=${fetchDate}&sort_by=created_at_desc`);
    setIsTaskDrawerVisible(false); // Close drawer on navigation.
  };

  // Footer content for the Task Progress Drawer.
  const drawerFooterContent = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <Tooltip title="Clear Completed & Errored Tasks">
        <Button 
          onClick={() => {
            setTasksToMonitor(prev => prev.filter(t => 
              t.status !== 'Complete' && t.status !== 'Error' && t.status !== 'Skipped'
            ));
          }} 
          disabled={!tasksToMonitor.some(t => 
            t.status === 'Complete' || t.status === 'Error' || t.status === 'Skipped'
          )} 
          type="text" 
          icon={<DeleteOutlined />} 
        />
      </Tooltip>
      {viewingDate === 'today' ? (
        <Tooltip title="View History">
          <Button 
            type="text" 
            icon={<HistoryOutlined />} 
            onClick={() => { 
              setViewingDate('history'); 
              setSelectedHistoryDate(null); 
              setHistoricalData(null); 
            }} 
          />
        </Tooltip>
      ) : (
        <Tooltip title="View Today's Progress">
          <Button 
            type="text" 
            icon={<ClockCircleOutlined />} 
            onClick={() => { 
              setViewingDate('today'); 
              fetchTodaysHistory(); 
              setHistoricalData(null); 
              setSelectedHistoryDate(null); 
            }} 
          />
        </Tooltip>
      )}
    </div>
  );

  return (
    <PageActionContext.Provider value={pageActions}>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          width={260} collapsible collapsed={collapsed} onCollapse={setCollapsed}
          className={styles.appSider}
          style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0, bottom: 0, borderRight: `1px solid var(--border-color)`, paddingTop: '16px' }}
        >
          {/* Logo / App Name */}
          <div style={{ padding: `0 ${collapsed ? '0' : '24px'} 16px ${collapsed ? '0' : '24px'}`, textAlign: collapsed ? 'center' : 'left', height: '32px', marginBottom: '8px' }}>
            {collapsed ? <Avatar className={styles.siderLogoAvatar}>S</Avatar> : <Title level={4} className={styles.gradientLogoText} style={{ margin: 0 }}>SmartInfo</Title>}
          </div>
          {/* Main Navigation Menu */}
          <Menu mode="inline" selectedKeys={[selectedKey]} items={mainMenuItems} className={styles.siderMainMenu} />
          {/* Chat Search and New Chat Button */}
          <div style={{ padding: `0 ${collapsed ? '8px' : '16px'}`, marginBottom: '16px' }}>
            {!collapsed ? (
              <Space.Compact style={{ width: '100%' }}>
                <Input prefix={<SearchOutlined style={{ color: 'var(--text-secondary)'}} />} placeholder="Search chats" value={searchText} onChange={e => setSearchText(e.target.value)} allowClear />
                <Tooltip title="New Chat"><Button icon={<PlusOutlined />} onClick={handleNewChat} aria-label="New Chat" className={styles.newChatButton} /></Tooltip>
              </Space.Compact>
            ) : (
              <div style={{ textAlign: 'center' }}><Tooltip title="New Chat"><Button icon={<PlusOutlined />} onClick={handleNewChat} aria-label="New Chat" className={styles.newChatButton} /></Tooltip></div>
            )}
          </div>
          {/* Chat List (grouped by date) */}
          {!collapsed && (authLoading ? <div style={{padding: '20px', textAlign: 'center'}}><Spin size="small" /></div> : (
            Object.entries(groupedChats).map(([groupName, groupChatsList]) =>
              groupChatsList.length > 0 && (
                <div key={groupName} style={{ marginBottom: '12px' }}>
                  <Text className={styles.chatGroupTitle}>{groupName}</Text>
                  <Menu mode="inline" selectedKeys={[selectedKey]} items={groupChatsList.map(chat => ({
                    key: `chat-${chat.id}`,
                    label: (
                      <div onMouseEnter={() => setHoveredChatId(chat.id)} onMouseLeave={() => setHoveredChatId(null)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <Link href={`/chat/${chat.id}`} passHref legacyBehavior>
                          <a style={{ flexGrow: 1, overflow: 'hidden', textDecoration: 'none', color: 'inherit' }} onClick={(e) => { if ((e.target as HTMLElement).closest('.chat-item-actions-trigger')) e.preventDefault(); }}>
                            <Text ellipsis={{ tooltip: chat.title }} style={{ display: 'block', lineHeight: '22px' }}>{chat.title}</Text>
                          </a>
                        </Link>
                        {/* Chat item actions (rename, delete) shown on hover */}
                        {hoveredChatId === chat.id && !collapsed && (
                          <Dropdown menu={{ items: [ { key: 'rename', label: 'Rename', onClick: (info) => { info.domEvent.stopPropagation(); info.domEvent.preventDefault(); showRenameModal(chat.id, chat.title); } }, { key: 'delete', label: 'Delete', danger: true, onClick: (info) => { info.domEvent.stopPropagation(); info.domEvent.preventDefault(); handleDeleteChat(chat.id); } } ] }} trigger={['click']} placement="bottomRight">
                            <Button className="chat-item-actions-trigger" type="text" icon={<EllipsisOutlined />} size="small" style={{ flexShrink: 0, marginLeft: '8px' }} onClick={(e) => { e.stopPropagation(); e.preventDefault(); }} />
                          </Dropdown>
                        )}
                      </div>
                    ),
                  }))} className={styles.siderChatMenu} />
                </div>
              )
            )
          ))}
          {/* Sider Bottom Section (e.g., for version number) */}
          <div className={styles.siderBottomSection}>
            <Menu mode="inline" selectedKeys={[selectedKey]} items={bottomMenuItems} className={styles.siderBottomMenu} />
            {!collapsed && <div style={{ textAlign: 'center', marginTop: '8px', paddingBottom: '8px' }}><Text type="secondary" style={{ fontSize: '11px' }}>v1.0.0</Text></div>}
          </div>
        </Sider>

        {/* Main Content Area */}
        <Layout style={{ marginLeft: collapsed ? 80 : 260, transition: 'margin-left 0.2s', minHeight: '100vh' }}>
          <Content style={{ padding: 24, margin: '0 auto', width: '100%', display: 'flex', flexDirection: 'column' }}>
            {children}
          </Content>
        </Layout>

        {/* Floating Action Button Group */}
        <FloatButton.Group trigger="hover" style={{ right: 24, bottom: 24 }} icon={<AppstoreOutlined />}>
          <FloatButton icon={<DownloadOutlined />} tooltip="Get News" onClick={requestOpenFetchModal} type="primary" />
          <FloatButton icon={<BarsOutlined />} tooltip="View Progress" onClick={requestOpenTaskDrawer} />
          <FloatButton icon={<SettingOutlined />} tooltip="Settings" onClick={handleShowSettingsModal} />
        </FloatButton.Group>

        {/* Modals and Drawers */}
        <Modal title="Rename Chat" open={isRenameModalVisible} onOk={handleRenameOk} onCancel={handleRenameCancel}>
          <AntForm form={renameForm} layout="vertical" name="rename_chat_form"><AntForm.Item name="newTitle" label="New Chat Title" rules={[{ required: true, message: 'Please enter the new title.' }]}><Input /></AntForm.Item></AntForm>
        </Modal>
        <Modal title="Settings" open={isSettingsModalVisible} onCancel={handleCloseSettingsModal} footer={null} width={1000} destroyOnClose={true} styles={{ body: { paddingTop: '12px', paddingBottom: '12px' } }}><SettingsContent /></Modal>

        <Modal
          title="News Fetch Settings" open={isFetchModalVisible} onOk={handleFetchConfirmInMainLayout}
          onCancel={() => setIsFetchModalVisible(false)} okText="Add to Task List" cancelText="Cancel"
          width={600} confirmLoading={fetchModalLoading}
        >
          <Spin spinning={fetchModalLoading}>
            <AntForm layout="vertical">
              <AntForm.Item label="Step 1: Filter News Categories (Optional)">
                <Select placeholder="Select category to filter sources below" allowClear value={selectedFetchCategory} onChange={handleFetchCategoryChange} style={{ width: '100%' }}>
                  <Option value={undefined}>-- All Categories --</Option>
                  {fetchModalCategories.map(cat => <Option key={cat.id} value={cat.id}>{cat.name}</Option>)}
                </Select>
              </AntForm.Item>
              <AntForm.Item label="Step 2: Select News Sources to Fetch">
                <Checkbox indeterminate={isIndeterminate} onChange={handleSelectAllChange} checked={selectAllSources} disabled={filteredFetchSources.length === 0} style={{ marginBottom: 8, display: 'block', borderBottom: '1px solid #f0f0f0', paddingBottom: '8px' }}>
                  Select All/Deselect All ({filteredFetchSources.length} sources in current list)
                </Checkbox>
                <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid #f0f0f0', padding: '8px' }}>
                  {filteredFetchSources.length > 0 ? (
                    <Checkbox.Group style={{ width: '100%' }} options={filteredFetchSources.map(s => ({ label: s.name, value: s.id }))} value={selectedSourceIds} onChange={handleSourceSelectionChange} />
                  ) : <Text type="secondary">No sources found for this filter or sources are not yet loaded.</Text>}
                </div>
              </AntForm.Item>
            </AntForm>
          </Spin>
        </Modal>

        <Drawer
          title="Task Progress" placement="right" width={350}
          onClose={() => setIsTaskDrawerVisible(false)} open={isTaskDrawerVisible}
          mask={false} closable={true}
          footer={drawerFooterContent}
        >
          {/* Date picker for historical view */}
          {viewingDate === 'history' && <div style={{ marginBottom: 16 }}><DatePicker value={selectedHistoryDate} onChange={handleHistoryDateChange} style={{ width: '100%' }} disabledDate={(current) => current && current > dayjs().endOf('day')} /></div>}
          {/* Loading spinner or task list */}
          {(isHistoryLoading && (viewingDate === 'history' || (viewingDate === 'today' && todaysHistory.length === 0 && tasksToMonitor.length === 0))) ? <div style={{ textAlign: 'center', padding: '20px 0' }}><Spin tip="Loading history..." /></div>
            : displayedTasks.length === 0 ? <Empty description={viewingDate === 'history' && !selectedHistoryDate ? "Select a date to view history." : "No tasks or history to display."} />
            : <List itemLayout="horizontal" dataSource={displayedTasks} renderItem={(item: FetchTaskItem | FetchHistoryItem, index: number) => {
                const itemStatus = getStatus(item); const itemsSaved = getItemsSavedThisRun(item); const itemProgress = getProgress(item);
                const isRunningOrPending = itemStatus !== 'Complete' && itemStatus !== 'Error' && itemStatus !== 'Skipped';
                // Determine if this is the last running task to add a divider.
                const isLastRunningTask = isRunningOrPending && (index === displayedTasks.length - 1 || !('progress' in displayedTasks[index+1] && getStatus(displayedTasks[index+1]) !== 'Complete' && getStatus(displayedTasks[index+1]) !== 'Error' && getStatus(displayedTasks[index+1]) !== 'Skipped'));
                let extraContent = null; const iconStyle = { fontSize: '16px', verticalAlign: 'middle' }; const badgeAreaStyle = { minWidth: '45px', display: 'inline-block', textAlign: 'left' as 'left', verticalAlign: 'middle', marginLeft: '8px' };
                const sourceId = getSourceId(item);
                // Determine fetch date for linking to filtered news.
                let determinedFetchDate: string = ('progress' in item && item.status !== 'Complete' && item.status !== 'Error' && item.status !== 'Skipped') ? dayjs().format('YYYY-MM-DD') : ('record_date' in item && item.record_date ? dayjs(item.record_date).format('YYYY-MM-DD') : dayjs().format('YYYY-MM-DD'));
                
                // Determine icon and progress display based on task status.
                if (isRunningOrPending) {
                    extraContent = <Space align="center"><Tooltip title={itemStatus}>{itemStatus === 'Preparing' || itemStatus === 'Pending' ? <SyncOutlined spin style={{ ...iconStyle, color: '#1890ff' }} /> : <LoadingOutlined style={{ ...iconStyle, color: '#1890ff' }} />}</Tooltip><Progress percent={itemProgress} status="active" size="small" showInfo={false} style={{ width: 60 }} /></Space>;
                } else if (itemStatus === 'Complete') {
                    extraContent = <Space align="center" size={0}><Tooltip title="Complete"><CheckCircleOutlined style={{ ...iconStyle, color: '#52c41a' }} /></Tooltip><div style={{...badgeAreaStyle, cursor: 'pointer'}} onClick={() => handleTaskBadgeClickInMainLayout(sourceId, determinedFetchDate)}>{itemsSaved !== undefined && itemsSaved > 0 && <Badge count={`+${itemsSaved}`} style={{ backgroundColor: '#52c41a' }} size="small" />}</div></Space>;
                } else if (itemStatus === 'Error') {
                    extraContent = <Space align="center" size={0}><Tooltip title="Error"><CloseCircleOutlined style={{ ...iconStyle, color: '#f5222d' }} /></Tooltip><div style={badgeAreaStyle} /></Space>;
                } else if (itemStatus === 'Skipped') {
                    extraContent = <Space align="center" size={0}><Tooltip title="Skipped"><StopOutlined style={{ ...iconStyle, color: '#faad14' }} /></Tooltip><div style={badgeAreaStyle} /></Space>;
                }

                return (<><List.Item key={`${getSourceId(item)}-${'sourceId' in item ? 'live' : 'hist'}-${index}`} extra={extraContent}><List.Item.Meta title={<Text ellipsis={{tooltip: getSourceName(item)}}>{getSourceName(item)}</Text>} description={ viewingDate === 'history' && 'last_updated_at' in item && item.last_updated_at ? <Text type="secondary" style={{fontSize: '12px'}}>{dayjs(item.last_updated_at).format('HH:mm:ss')}</Text> : null } /></List.Item>{isLastRunningTask && viewingDate === 'today' && <Divider style={{ margin: '8px 0' }} />}</>);
              }} />}
        </Drawer>
      </Layout>
    </PageActionContext.Provider>
  );
};

export default MainLayout;