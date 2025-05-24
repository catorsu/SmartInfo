/**
 * @file index.tsx (NewsPage)
 * @description Displays the main news feed page. Allows users to browse, filter,
 * and search for news items. It interacts with MainLayout via PageActionContext
 * to request global modals/drawers (e.g., for fetching news).
 * This is the default page shown after login, typically at the root path '/'.
 *
 * @file_purpose Entry point for the primary news aggregation and viewing interface.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import {
  Typography, Select, Input, Spin, Empty, List, Card, Row, Col, Pagination, Space, Button, Alert, Tooltip, FloatButton, message
} from 'antd';
import {
  SearchOutlined, CalendarOutlined, TagOutlined, GlobalOutlined, ExperimentOutlined, LinkOutlined, FilterOutlined
} from '@ant-design/icons';
import { NewsItem, NewsCategory, NewsSource, NewsFilterParams, PaginatedNewsResponse } from '@/utils/types';
import * as newsService from '@/services/newsService';
import { extractErrorMessage } from '@/utils/apiErrorHandler';
import Link from 'next/link'; // Used for navigation, not direct linking here.
import debounce from 'lodash/debounce';
import withAuth from '@/components/auth/withAuth'; // Protected route
import dayjs from 'dayjs'; // For date formatting

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

/**
 * @page NewsPage
 * @description Displays the main news feed, allowing users to browse, filter, and
 * search news items. It fetches news items, categories, and sources for filtering.
 * Users can paginate through news, view summaries, and navigate to detailed analysis.
 * A floating action button allows toggling of filter visibility.
 * This page is protected and requires authentication.
 *
 * @returns {JSX.Element} The rendered news page.
 *
 * @sideeffect Fetches news items, categories, and sources from the backend.
 *             Updates URL query parameters based on filter changes (implicitly via router).
 *
 * @example
 * // This component is typically rendered by Next.js routing.
 * // No direct instantiation example needed.
 * // It's accessed via the root path '/' after login.
 */
const NewsPage: React.FC = () => {
  const router = useRouter();

  // State for news data and UI control
  const [news, setNews] = useState<NewsItem[]>([]);
  const [categories, setCategories] = useState<NewsCategory[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [loading, setLoading] = useState(false); // General loading for news items
  const [error, setError] = useState<{ type: string, message: string, status?: number } | null>(null);
  const [filters, setFilters] = useState<NewsFilterParams>({
    page: 1,
    page_size: 10,
    category_id: undefined,
    source_id: undefined,
    search_term: '',
    fetch_date: undefined,
    sort_by: undefined, // e.g., 'created_at_desc'
  });
  const [total, setTotal] = useState(0); // Total number of news items for pagination
  const [isFilterRowVisible, setIsFilterRowVisible] = useState<boolean>(false); // Toggle for filter bar

  // Callback to load news items based on current filters.
  const loadNews = useCallback(async (currentFilters: NewsFilterParams) => {
    setLoading(true);
    setError(null);
    try {
      const paginatedResponse: PaginatedNewsResponse = await newsService.getNewsItems(currentFilters);
      setNews(paginatedResponse.items);
      setTotal(paginatedResponse.total);
    } catch (err: any) {
      console.error('Failed to load news:', err);
      const errorDetails = extractErrorMessage(err);
      setError(errorDetails);
      setNews([]); // Clear news on error
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array as it uses `currentFilters` argument.

  // Effect to load initial filter data (categories, sources) on mount.
  useEffect(() => {
    const loadFilterData = async () => {
      // setLoading(true); // Consider separate loading state for filter data if needed
      try {
        const [categoriesData, sourcesData] = await Promise.all([
          newsService.getCategories(),
          newsService.getSources()
        ]);
        setCategories(categoriesData);
        setSources(sourcesData);
      } catch (err: any) {
        console.error('Failed to load filter data:', err);
        const errorDetails = extractErrorMessage(err);
        setError(errorDetails); // Show error if filter data fails to load
      } finally {
        // setLoading(false);
      }
    };
    loadFilterData();
  }, []); // Runs once on component mount.

  // Effect to reload news items whenever filters change.
  useEffect(() => {
    loadNews(filters);
  }, [filters, loadNews]); // `loadNews` is memoized by useCallback.
  
  // Debounced search handler to avoid excessive API calls on input change.
  const debouncedSearch = useCallback(
    debounce((value: string) => {
      setFilters(prev => ({ ...prev, search_term: value, page: 1 })); // Reset to page 1 on new search
    }, 500), // 500ms delay
    [] // Empty dependency array for debounce
  );

  // Generic handler for filter changes.
  const handleFilterChange = (key: keyof NewsFilterParams, value: any) => {
    setFilters(prev => {
      const updated = { ...prev, [key]: value };
      if (key !== 'page') updated.page = 1; // Reset to page 1 if filter changes (except pagination itself)
      // If a primary filter (category, source, search) changes, clear secondary sort/date filters.
      if (key === 'category_id' || key === 'source_id' || key === 'search_term') {
         updated.fetch_date = undefined;
         updated.sort_by = undefined;
      }
      return updated;
    });
  };

  // Special handler for category change to also update available sources.
  const handleCategoryChange = async (value: number | undefined) => {
    handleFilterChange('category_id', value);
    // setLoading(true); // Potentially show loading for sources
    try {
      // Fetch sources specific to the selected category, or all sources if category is cleared.
      const sourcesData = value !== undefined ? await newsService.getSourcesByCategory(value) : await newsService.getSources();
      setSources(sourcesData);
    } catch (error) {
      const errorDetails = extractErrorMessage(error);
      setError(errorDetails); // Set error if source list update fails
      message.error(errorDetails.message || 'Cannot update source list for selected category.');
    } finally {
      // setLoading(false);
    }
    handleFilterChange('source_id', undefined); // Reset source filter when category changes
  };
  
  // Formats date strings for display.
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown date';
    return dayjs(dateString).format('YYYY-MM-DD'); // Example format
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Floating Action Button to toggle filter visibility */}
      <FloatButton
        icon={<FilterOutlined />}
        tooltip="Toggle Filters"
        onClick={() => setIsFilterRowVisible(prev => !prev)}
        className="filter-toggle-fab" // For global styling if needed
        style={{ position: 'fixed', top: 24, right: 24, zIndex: 1001 }} // Position FAB
      />

      {/* Filter bar, shown/hidden by FAB */}
      {isFilterRowVisible && (
        <div style={{ position: 'sticky', top: 0, zIndex: 1000, backgroundColor: 'var(--primary-bg, #fff)', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <Row justify="center">
            <Col xs={24} sm={24} md={24} lg={23} xl={22}> {/* Responsive column for content width */}
              <Row gutter={[16, 4]} style={{ padding: '8px 0px' }} align="middle">
                <Col xs={24} sm={12} md={6} lg={6} xl={6}>
                  <Select placeholder="Select category" style={{ width: '100%' }} allowClear size="small" onChange={handleCategoryChange} loading={loading && categories.length === 0} value={filters.category_id}>
                    {categories.map(category => <Option key={category.id} value={category.id}>{category.name}</Option>)}
                  </Select>
                </Col>
                <Col xs={24} sm={12} md={6} lg={6} xl={6}>
                  <Select placeholder="Select source" style={{ width: '100%' }} allowClear size="small" onChange={(value) => handleFilterChange('source_id', value)} loading={loading && sources.length === 0 && !!filters.category_id} value={filters.source_id} disabled={!filters.category_id && sources.every(s => s.category_id !== undefined) /* Disable if no category selected and all sources are categorized */}>
                    {sources.map(source => <Option key={source.id} value={source.id}>{source.name}</Option>)}
                  </Select>
                </Col>
                <Col xs={24} sm={24} md={12} lg={12} xl={12}>
                  <Input placeholder="Search news titles & summaries" prefix={<SearchOutlined />} size="small" onChange={(e) => debouncedSearch(e.target.value)} allowClear />
                </Col>
              </Row>
            </Col>
          </Row>
        </div>
      )}

      {/* Main content area for news list */}
      <div style={{ flexGrow: 1, paddingTop: isFilterRowVisible ? '8px' : '0px' /* Adjust padding based on filter bar */ }}>
        {error && <Alert message={error.message || "An unexpected error occurred."} type="error" showIcon style={{ margin: '16px auto', maxWidth: '1200px' }} />}
        {/* Loading spinner shown when fetching initial news or when news array is empty during load */}
        {loading && news.length === 0 ? <div style={{ textAlign: 'center', padding: '50px 0' }}><Spin size="large" tip="Loading news..." /></div>
          // Error display if loading failed
          : error ? <div style={{ textAlign: 'center', padding: '50px 0' }}>{error.type === 'notFound' ? <Empty description={error.message || "Content not found."} /> : error.type === 'forbidden' ? <Alert message="Access Denied" description={error.message || "You do not have permission to view this content."} type="error" showIcon /> : <Alert message={error.message || "An unexpected error occurred."} type="error" showIcon />}</div>
          // Empty state if no news found and not loading
          : !loading && news.length === 0 ? <div style={{ textAlign: 'center', padding: '50px 0' }}><Empty description="No news found. Try adjusting filters or fetching new articles." /></div>
          // News list display
          : (
            <>
              <Row justify="center">
                <Col xs={24} sm={24} md={24} lg={23} xl={22}>
                  <List
                    dataSource={news} loading={loading && news.length > 0 /* Show item loading if already displaying some news */}
                    renderItem={(item) => (
                      <List.Item key={item.id} style={{paddingTop: 0, paddingBottom: 0, borderBottom: '1px solid var(--border-color)'}}>
                        <Card className="news-item-card-hoverable" style={{ marginBottom: '0', width: '100%', border: 'none', borderRadius: 0, cursor: 'pointer' }} bodyStyle={{ padding: '20px' }} onClick={() => router.push(`/analyze/${item.id}`)}>
                          <Row gutter={[16, 16]} align="top">
                            {/* News item image */}
                            {item.top_image && <Col xs={24} sm={8} md={7} lg={6} xl={5}><img src={item.top_image} alt={item.title} style={{ width: '100%', height: 'auto', aspectRatio: '16/10', objectFit: 'cover', borderRadius: 'var(--border-radius-base)', border: '1px solid var(--border-color-secondary)' }} onError={(e) => (e.currentTarget.style.display = 'none')} /></Col>}
                            {/* News item content */}
                            <Col xs={24} sm={item.top_image ? 16 : 24} md={item.top_image ? 17 : 24} lg={item.top_image ? 18 : 24} xl={item.top_image ? 19 : 24} style={{ display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
                              <Typography.Title level={4} style={{ marginBottom: '8px', marginTop: 0, fontSize: '18px', fontWeight: 600 }} ellipsis={{ rows: 2, expandable: false }}>{item.title}</Typography.Title>
                              <Space size="middle" wrap style={{ marginBottom: '12px', fontSize: '13px', alignItems: 'center' }}>
                                {item.source_name && <Space size={4} align="center"><GlobalOutlined style={{ color: 'var(--text-secondary)', fontSize: '14px' }} /><Text type="secondary">{item.source_name}</Text></Space>}
                                {item.category_name && <Space size={4} align="center"><TagOutlined style={{ color: 'var(--text-secondary)', fontSize: '14px' }} /><Text type="secondary">{item.category_name}</Text></Space>}
                                {item.date && <Space size={4} align="center"><CalendarOutlined style={{ color: 'var(--text-secondary)', fontSize: '14px' }} /><Text type="secondary">{formatDate(item.date)}</Text></Space>}
                                {/* Link to original article */}
                                {item.url && <Button type="text" href={item.url} target="_blank" rel="noopener noreferrer" icon={<LinkOutlined style={{ color: 'var(--accent-color)', fontSize: '15px' }} />} onClick={(e) => { e.stopPropagation(); /* Prevent card click */ }} style={{ padding: '0 4px', color: 'var(--accent-color)' }} />}
                                {/* Button to initiate analysis */}
                                <Button type="text" icon={<ExperimentOutlined style={{ color: 'var(--accent-color)', fontSize: '15px' }} />} onClick={(e) => { e.stopPropagation(); router.push(`/analyze/${item.id}?initiate=true`); }} style={{ padding: '0 4px', color: 'var(--accent-color)' }} />
                              </Space>
                              {item.summary && <Typography.Paragraph ellipsis={{ rows: 3, expandable: false }} style={{ marginBottom: '0', color: 'var(--text-primary)', lineHeight: 1.6, flexGrow: 1 }}>{item.summary}</Typography.Paragraph>}
                            </Col>
                          </Row>
                        </Card>
                      </List.Item>
                    )}
                  />
                  {/* Pagination controls */}
                  {total > (filters.page_size || 10) && ( // Show pagination only if more than one page
                    <div style={{ textAlign: 'center', marginTop: 24, display: 'flex', justifyContent: 'center' }}>
                      <Pagination current={filters.page} pageSize={filters.page_size} total={total} onChange={(page) => handleFilterChange('page', page)} showSizeChanger={false} />
                    </div>
                  )}
                </Col>
              </Row>
            </>
          )}
      </div>
    </div>
  );
};

export default withAuth(NewsPage); // Protect this page