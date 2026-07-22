import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Spin,
  Switch,
  Tooltip,
  Typography,
  message,
  Pagination,
} from 'antd';
import {
  ApiOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { getBackendErrorMessage, goLoginPage, isUserLoggedIn, mcpServersApi } from '../api';
import type { McpServer } from '../api';
import './McpServers.css';

const { Title, Paragraph } = Typography;
const BUILTIN_TYPE = 1;
const PAGE_SIZE = 12;
const SEARCH_DEBOUNCE_MS = 300;

type TypeFilter = 'all' | 'custom' | 'builtin';

const TYPE_FILTER_OPTIONS: { label: string; value: TypeFilter }[] = [
  { label: '全部', value: 'all' },
  { label: '自定义', value: 'custom' },
  { label: '系统内建', value: 'builtin' },
];

const TRANSPORT_OPTIONS = [
  { label: 'HTTP', value: 'http' },
  { label: 'Streamable HTTP', value: 'streamable_http' },
  { label: 'stdio', value: 'stdio' },
];

function formatDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

type FormValues = {
  name: string;
  description?: string;
  transport: string;
  url?: string;
  command?: string;
  args_text?: string;
  headers_text?: string;
  enabled: boolean;
};

function parseArgsText(raw?: string): string[] | undefined {
  const text = (raw || '').trim();
  if (!text) return undefined;
  try {
    const parsed = JSON.parse(text);
    if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === 'string')) {
      throw new Error('args 须为字符串数组 JSON');
    }
    return parsed;
  } catch {
    return text.split(/\s+/).filter(Boolean);
  }
}

function parseHeadersText(raw?: string): Record<string, string> | undefined {
  const text = (raw || '').trim();
  if (!text) return undefined;
  const parsed = JSON.parse(text) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('headers 须为 JSON 对象');
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    out[k] = String(v);
  }
  return out;
}

function McpCard({
  item,
  onOpen,
  onEdit,
  onDelete,
}: {
  item: McpServer;
  onOpen: (item: McpServer) => void;
  onEdit: (item: McpServer) => void;
  onDelete: (id: number) => void;
}) {
  const isBuiltin = item.type === BUILTIN_TYPE;
  const loggedIn = isUserLoggedIn();
  const canManage = loggedIn && !isBuiltin;
  const displayDesc = item.description?.trim() || '暂无描述';
  const endpoint =
    item.transport === 'stdio'
      ? `${item.command || ''} ${(item.args || []).join(' ')}`.trim()
      : item.url || '';

  return (
    <article
      className="portal-skill-card-wrap portal-mcp-card-wrap"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(item);
        }
      }}
    >
      <span
        className={`portal-skill-card__badge portal-skill-card__badge--corner ${
          isBuiltin ? 'portal-skill-card__badge--builtin' : 'portal-skill-card__badge--custom'
        }`}
      >
        {isBuiltin ? '内置' : '自定义'}
      </span>

      {loggedIn && (
        <div className="portal-skill-card__hover-actions" onClick={(e) => e.stopPropagation()}>
          <Tooltip title={isBuiltin ? '内置不可编辑' : '编辑'}>
            <button
              type="button"
              className="portal-skill-card__icon-btn"
              disabled={!canManage}
              aria-label="编辑 MCP"
              onClick={() => onEdit(item)}
            >
              <EditOutlined />
            </button>
          </Tooltip>
          <Popconfirm
            title="确定删除该 MCP 服务吗？"
            description="删除前请先解除与智能体的关联。"
            onConfirm={() => void onDelete(item.id)}
            okText="确定"
            cancelText="取消"
            disabled={!canManage}
          >
            <Tooltip title={isBuiltin ? '内置不可删除' : '删除'}>
              <button
                type="button"
                className="portal-skill-card__icon-btn portal-skill-card__icon-btn--delete"
                disabled={!canManage}
                aria-label="删除 MCP"
              >
                <DeleteOutlined />
              </button>
            </Tooltip>
          </Popconfirm>
        </div>
      )}

      <div className="portal-skill-card__badge-row" aria-hidden />

      <div className="portal-skill-card__head">
        <div className="portal-skill-card__avatar portal-mcp-card__avatar" aria-hidden>
          <ApiOutlined />
        </div>
        <div className="portal-skill-card__head-main">
          <h3 className="portal-skill-card__title">{item.name}</h3>
        </div>
      </div>

      <div className="portal-skill-card__middle">
        <p className={`portal-skill-card__desc${displayDesc === '暂无描述' ? ' is-empty' : ''}`}>
          {displayDesc}
        </p>
        <div className="portal-mcp-card__chips">
          <span className="portal-mcp-card__chip">{item.transport}</span>
          <span
            className={`portal-mcp-card__chip${
              item.enabled ? ' portal-mcp-card__chip--on' : ' portal-mcp-card__chip--off'
            }`}
          >
            {item.enabled ? '已启用' : '已禁用'}
          </span>
        </div>
        <p className="portal-mcp-card__endpoint" title={endpoint || undefined}>
          {endpoint || '未配置连接'}
        </p>
      </div>

      <div className="portal-skill-card__bottom">
        <span className="portal-skill-card__meta">
          <ClockCircleOutlined />
          {formatDate(item.create_time)}
        </span>
      </div>
    </article>
  );
}

export default function McpServersPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<McpServer[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<McpServer | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<FormValues>();
  const transport = Form.useWatch('transport', form);

  const requireLogin = () => {
    if (!isUserLoggedIn()) {
      goLoginPage(navigate, { pathname: location.pathname, search: location.search });
      return false;
    }
    return true;
  };

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedKeyword(keyword.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [keyword]);

  const fetchItems = useCallback(
    async (targetPage: number) => {
      setLoading(true);
      try {
        const data = await mcpServersApi.list({
          page: targetPage,
          page_size: PAGE_SIZE,
          q: debouncedKeyword || undefined,
          type: typeFilter === 'all' ? undefined : typeFilter === 'builtin' ? 1 : 2,
        });
        setItems(data.items);
        setTotal(data.total);
        setPage(data.page);
      } catch (error) {
        message.error(getBackendErrorMessage(error, '获取 MCP 列表失败'));
      } finally {
        setLoading(false);
      }
    },
    [debouncedKeyword, typeFilter],
  );

  useEffect(() => {
    void fetchItems(1);
  }, [fetchItems]);

  const openCreate = () => {
    if (!requireLogin()) return;
    setEditing(null);
    form.setFieldsValue({
      name: '',
      description: '',
      transport: 'http',
      url: '',
      command: '',
      args_text: '',
      headers_text: '',
      enabled: true,
    });
    setModalOpen(true);
  };

  const openEdit = (item: McpServer) => {
    if (!requireLogin()) return;
    setEditing(item);
    form.setFieldsValue({
      name: item.name,
      description: item.description || '',
      transport: item.transport,
      url: item.url || '',
      command: item.command || '',
      args_text: item.args?.length ? JSON.stringify(item.args) : '',
      headers_text: '',
      enabled: item.enabled,
    });
    setModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!requireLogin()) return;
    try {
      await mcpServersApi.delete(id);
      message.success('已删除');
      void fetchItems(page);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  const handleSubmit = async () => {
    if (!requireLogin()) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const args = parseArgsText(values.args_text);
      let headers: Record<string, string> | undefined;
      try {
        headers = parseHeadersText(values.headers_text);
      } catch (error) {
        message.error(error instanceof Error ? error.message : 'headers 格式错误');
        return;
      }
      const payload = {
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        transport: values.transport,
        url: values.transport === 'stdio' ? undefined : values.url?.trim() || undefined,
        command: values.transport === 'stdio' ? values.command?.trim() || undefined : undefined,
        args: values.transport === 'stdio' ? args : undefined,
        headers,
        enabled: values.enabled,
      };
      if (editing) {
        const updatePayload = { ...payload };
        if (!values.headers_text?.trim()) {
          delete (updatePayload as { headers?: Record<string, string> }).headers;
        }
        await mcpServersApi.update(editing.id, updatePayload);
        message.success('已更新');
      } else {
        await mcpServersApi.create(payload);
        message.success('已创建');
      }
      setModalOpen(false);
      void fetchItems(editing ? page : 1);
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) return;
      message.error(getBackendErrorMessage(error, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  const empty = useMemo(() => !loading && items.length === 0, [loading, items.length]);
  const isFiltering = debouncedKeyword.length > 0 || typeFilter !== 'all';

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>MCP 服务</Title>
        <Paragraph type="secondary" style={{ maxWidth: 560, marginBottom: 0 }}>
          管理外部 MCP 工具源，并在智能体详情中按需绑定。
        </Paragraph>
        <div className="portal-toolbar portal-skills-toolbar">
          <div className="portal-toolbar-left portal-skills-toolbar__left">
            <Input
              allowClear
              prefix={<SearchOutlined style={{ color: 'var(--portal-muted)' }} />}
              placeholder="搜索名称或描述"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="portal-skills-toolbar__search"
            />
            <Select
              value={typeFilter}
              options={TYPE_FILTER_OPTIONS}
              onChange={(value) => {
                setTypeFilter(value);
                setPage(1);
              }}
              className="portal-skills-toolbar__filter"
            />
          </div>
          <div className="portal-toolbar-actions">
            {isUserLoggedIn() && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
                新增 MCP
              </Button>
            )}
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        {empty ? (
          <Empty
            description={
              isFiltering ? '未找到匹配的 MCP 服务' : '暂无 MCP 服务，点击「新增 MCP」开始'
            }
          />
        ) : (
          <>
            <Row gutter={[14, 14]} className="portal-skills-grid">
              {items.map((item) => (
                <Col xs={24} sm={12} md={8} lg={6} xl={4} key={item.id}>
                  <McpCard
                    item={item}
                    onOpen={(mcp) => navigate(`/mcp-servers/${mcp.id}`)}
                    onEdit={openEdit}
                    onDelete={handleDelete}
                  />
                </Col>
              ))}
            </Row>
            {total > PAGE_SIZE && (
              <div className="portal-skills-pagination">
                <Pagination
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={total}
                  showSizeChanger={false}
                  onChange={(p) => void fetchItems(p)}
                />
              </div>
            )}
          </>
        )}
      </Spin>

      <Modal
        title={editing ? '编辑 MCP 服务' : '新增 MCP 服务'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => void handleSubmit()}
        confirmLoading={saving}
        destroyOnClose
        width={640}
      >
        <Form form={form} layout="vertical" initialValues={{ transport: 'http', enabled: true }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写名称' }]}>
            <Input placeholder="例如 weather" maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} maxLength={500} showCount placeholder="用途说明" />
          </Form.Item>
          <Form.Item name="transport" label="传输类型" rules={[{ required: true }]}>
            <Select options={TRANSPORT_OPTIONS} />
          </Form.Item>
          {transport === 'stdio' ? (
            <>
              <Form.Item name="command" label="Command" rules={[{ required: true, message: '请填写 command' }]}>
                <Input placeholder="例如 python" />
              </Form.Item>
              <Form.Item name="args_text" label="Args">
                <Input.TextArea rows={2} placeholder='JSON 数组，如 ["server.py"]，或空格分隔' />
              </Form.Item>
            </>
          ) : (
            <Form.Item name="url" label="URL" rules={[{ required: true, message: '请填写 URL' }]}>
              <Input placeholder="http://127.0.0.1:8100/mcp" />
            </Form.Item>
          )}
          <Form.Item
            name="headers_text"
            label="Headers（JSON）"
            extra={editing?.has_headers ? '已配置请求头；留空表示不修改，填写则覆盖' : '可选，如 {"Authorization":"Bearer xxx"}'}
          >
            <Input.TextArea rows={3} placeholder='{"Authorization":"Bearer xxx"}' />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
