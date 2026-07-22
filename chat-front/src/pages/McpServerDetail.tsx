import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Empty,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ApiOutlined,
  ArrowLeftOutlined,
  ClockCircleOutlined,
  DownOutlined,
  ReloadOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { getBackendErrorMessage, mcpServersApi } from '../api';
import type { McpServer, McpToolInfo, McpToolParameter } from '../api';
import './McpServerDetail.css';

const { Title, Paragraph, Text } = Typography;
const BUILTIN_TYPE = 1;

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDefault(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return '-';
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function ToolParamsTable({ parameters }: { parameters: McpToolParameter[] }) {
  const columns: ColumnsType<McpToolParameter> = [
    {
      title: '参数',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (name: string, row) => (
        <span>
          <Text code>{name}</Text>
          {row.required ? (
            <Tag color="red" style={{ marginLeft: 6 }}>
              必填
            </Tag>
          ) : (
            <Tag style={{ marginLeft: 6 }}>可选</Tag>
          )}
        </span>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => <Text type="secondary">{type || 'any'}</Text>,
    },
    {
      title: '默认值',
      key: 'default',
      width: 140,
      render: (_, row) =>
        row.has_default ? (
          <Text code>{formatDefault(row.default)}</Text>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string | null | undefined, row) => {
        const text = desc?.trim() || row.title?.trim() || '';
        return text ? text : <Text type="secondary">暂无说明</Text>;
      },
    },
  ];

  if (parameters.length === 0) {
    return <Text type="secondary">无入参</Text>;
  }

  return (
    <Table
      size="small"
      rowKey={(row) => row.name}
      columns={columns}
      dataSource={parameters}
      pagination={false}
      className="mcp-tool-params-table"
    />
  );
}

function ToolCard({ tool }: { tool: McpToolInfo }) {
  const params = tool.parameters ?? [];
  const [paramsOpen, setParamsOpen] = useState(false);

  return (
    <article className="mcp-tool-card">
      <header className="mcp-tool-card__head">
        <div className="mcp-tool-card__title-row">
          <Text code className="mcp-tool-card__name">
            {tool.name}
          </Text>
          <Tag>{params.length} 个参数</Tag>
        </div>
        <Paragraph className="mcp-tool-card__desc" type="secondary">
          {tool.description?.trim() || '暂无描述'}
        </Paragraph>
      </header>
      <div className="mcp-tool-card__body">
        <button
          type="button"
          className="mcp-tool-card__fold-btn"
          onClick={() => setParamsOpen((v) => !v)}
          aria-expanded={paramsOpen}
        >
          {paramsOpen ? <DownOutlined /> : <RightOutlined />}
          <span>参数</span>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {paramsOpen ? '收起' : `展开（${params.length}）`}
          </Text>
        </button>
        {paramsOpen ? (
          <div className="mcp-tool-card__params">
            <ToolParamsTable parameters={params} />
          </div>
        ) : null}
      </div>
    </article>
  );
}

export default function McpServerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const mcpServerId = Number(id);
  const navigate = useNavigate();

  const [server, setServer] = useState<McpServer | null>(null);
  const [tools, setTools] = useState<McpToolInfo[]>([]);
  const [toolsDisabled, setToolsDisabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [toolsError, setToolsError] = useState<string | null>(null);

  const fetchServer = useCallback(async () => {
    if (!Number.isFinite(mcpServerId)) {
      setServer(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await mcpServersApi.get(mcpServerId);
      setServer(data ?? null);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取 MCP 详情失败'));
      setServer(null);
    } finally {
      setLoading(false);
    }
  }, [mcpServerId]);

  const fetchTools = useCallback(async () => {
    if (!Number.isFinite(mcpServerId)) {
      return;
    }
    setToolsLoading(true);
    setToolsError(null);
    try {
      const data = await mcpServersApi.listTools(mcpServerId);
      setTools(data.tools);
      setToolsDisabled(Boolean(data.disabled));
    } catch (error) {
      setTools([]);
      setToolsError(getBackendErrorMessage(error, '拉取工具列表失败'));
    } finally {
      setToolsLoading(false);
    }
  }, [mcpServerId]);

  useEffect(() => {
    void fetchServer();
  }, [fetchServer]);

  useEffect(() => {
    if (server) {
      void fetchTools();
    }
  }, [server?.id, fetchTools]);

  const endpoint = useMemo(() => {
    if (!server) return '';
    if (server.transport === 'stdio') {
      return `${server.command || ''} ${(server.args || []).join(' ')}`.trim();
    }
    return server.url || '';
  }, [server]);

  if (!Number.isFinite(mcpServerId)) {
    return (
      <div className="portal-page">
        <Empty description="无效的 MCP ID" />
      </div>
    );
  }

  return (
    <div className="portal-page">
      <div className="mcp-detail-page-header">
        <button
          type="button"
          className="portal-agent-detail__back"
          onClick={() => navigate('/mcp-servers')}
        >
          <ArrowLeftOutlined /> 返回 MCP 列表
        </button>
        <div className="mcp-detail-page-header__title-row">
          <div className="mcp-detail-page-header__titles">
            <Title level={3} className="mcp-detail-page-header__name">
              {server?.name || 'MCP 详情'}
            </Title>
            <Paragraph type="secondary" className="mcp-detail-page-header__desc">
              {server?.description?.trim() || '查看该 MCP 服务暴露的工具与参数'}
            </Paragraph>
          </div>
          <Button
            className="mcp-detail-page-header__refresh"
            icon={<ReloadOutlined />}
            loading={toolsLoading}
            onClick={() => void fetchTools()}
            disabled={!server}
          >
            刷新工具
          </Button>
        </div>
      </div>

      <Spin spinning={loading}>
        {!server ? (
          <Empty description="MCP 服务不存在或无权访问" />
        ) : (
          <>
            <div className="mcp-detail-meta">
              <div className="mcp-detail-meta__row">
                <ApiOutlined style={{ fontSize: 22, color: '#1677ff' }} />
                <div>
                  <div style={{ fontWeight: 600 }}>{server.name}</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    ID {server.id}
                  </Text>
                </div>
                <div className="mcp-detail-meta__tags">
                  <Tag color={server.type === BUILTIN_TYPE ? 'blue' : 'default'}>
                    {server.type === BUILTIN_TYPE ? '内置' : '自定义'}
                  </Tag>
                  <Tag color={server.enabled ? 'success' : 'default'}>
                    {server.enabled ? '已启用' : '已禁用'}
                  </Tag>
                  <Tag>{server.transport}</Tag>
                </div>
              </div>
              <div className="mcp-detail-meta__grid">
                <div>
                  <Text type="secondary">连接：</Text>
                  <Text code style={{ wordBreak: 'break-all' }}>
                    {endpoint || '未配置'}
                  </Text>
                </div>
                <div>
                  <ClockCircleOutlined style={{ marginRight: 6, color: '#94a3b8' }} />
                  <Text type="secondary">创建于 {formatDate(server.create_time)}</Text>
                </div>
              </div>
            </div>

            <div className="mcp-detail-tools">
              <div className="mcp-detail-tools__head">
                <Title level={5} style={{ margin: 0 }}>
                  工具列表
                  {!toolsLoading && !toolsError ? (
                    <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8 }}>
                      {tools.length} 个
                    </Text>
                  ) : null}
                </Title>
              </div>

              <Spin spinning={toolsLoading}>
                {toolsDisabled ? (
                  <Empty description="服务已禁用，无法拉取工具。请先启用后再刷新。" />
                ) : toolsError ? (
                  <Empty description={toolsError}>
                    <Button type="primary" onClick={() => void fetchTools()}>
                      重试
                    </Button>
                  </Empty>
                ) : tools.length === 0 ? (
                  <Empty description={toolsLoading ? '加载中…' : '暂无工具'} />
                ) : (
                  <div className="mcp-tool-list">
                    {tools.map((tool) => (
                      <ToolCard key={tool.name} tool={tool} />
                    ))}
                  </div>
                )}
              </Spin>
            </div>
          </>
        )}
      </Spin>
    </div>
  );
}
