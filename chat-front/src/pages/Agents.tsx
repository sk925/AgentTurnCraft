import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  message,
  Popconfirm,
  Row,
  Col,
  Typography,
  Empty,
  Spin,
  Select,
  Tooltip,
} from 'antd';
import { PlusOutlined, DeleteOutlined, RobotOutlined, ClockCircleOutlined, ApiOutlined } from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { agentsApi, getBackendErrorMessage, goLoginPage, groupsApi, isUserLoggedIn, modelManageApi } from '../api';
import type { Agent, ChatModelOption, Group } from '../api';

const { Title, Paragraph, Text } = Typography;

const BUILTIN_TYPE = 1;
const DESC_EXCERPT_MAX = 48;
const HOVER_DELAY_SEC = 0.5;

function formatAgentDate(iso: string) {
  const d = new Date(iso);
  const date = d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' });
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  return `${date} ${time}`;
}

function excerpt(text: string | null | undefined, max: number) {
  if (!text) {
    return '暂无描述';
  }
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

function AgentCardDesc({ description }: { description: string | null | undefined }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [overflow, setOverflow] = useState(false);
  const isEmpty = !description?.trim();
  const fullText = isEmpty ? '暂无描述' : description!.trim();
  const display = excerpt(description, DESC_EXCERPT_MAX);
  const truncatedByLength = !isEmpty && fullText.replace(/\s+/g, ' ').trim().length > DESC_EXCERPT_MAX;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    setOverflow(el.scrollHeight > el.clientHeight + 1);
  }, [display]);

  const showTooltip = !isEmpty && (truncatedByLength || overflow);

  const body = (
    <p
      ref={ref}
      className={`portal-agent-card__desc${showTooltip ? ' is-help' : ''}`}
    >
      {display}
    </p>
  );

  if (!showTooltip) {
    return body;
  }

  return (
    <Tooltip
      title={<span className="portal-agent-card__desc-tooltip">{fullText}</span>}
      mouseEnterDelay={HOVER_DELAY_SEC}
      styles={{ root: { maxWidth: 360 } }}
    >
      {body}
    </Tooltip>
  );
}

function AgentCard({
  agent,
  modelLabel,
  onOpen,
  onDelete,
  showDelete,
}: {
  agent: Agent;
  modelLabel: string;
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
  showDelete: boolean;
}) {
  const isBuiltin = agent.type === BUILTIN_TYPE;
  const canDelete = showDelete && !isBuiltin;

  return (
    <div className="portal-agent-card-wrap">
      <div className="portal-agent-card__main" onClick={() => onOpen(agent.id)} role="button" tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onOpen(agent.id);
          }
        }}
      >
        <div className="portal-agent-card__head">
          <div className="portal-agent-card__avatar" aria-hidden>
            <RobotOutlined />
          </div>
          <div className="portal-agent-card__head-main">
            <div className="portal-agent-card__title-row">
              <h3 className="portal-agent-card__title">{agent.name}</h3>
              <span
                className={`portal-agent-card__badge ${
                  isBuiltin ? 'portal-agent-card__badge--builtin' : 'portal-agent-card__badge--custom'
                }`}
              >
                {isBuiltin ? '内置' : '自定义'}
              </span>
            </div>
            <div className="portal-agent-card__meta">
              <ClockCircleOutlined />
              <span>{formatAgentDate(agent.create_time)}</span>
            </div>
          </div>
        </div>

        <div className="portal-agent-card__body">
          <div className="portal-agent-card__row">
            <span className="portal-agent-card__label">描述</span>
            <AgentCardDesc description={agent.description} />
          </div>
          <div className="portal-agent-card__row portal-agent-card__row--model">
            <span className="portal-agent-card__label">
              <ApiOutlined />
              模型
            </span>
            <span className="portal-agent-card__model">{modelLabel}</span>
          </div>
        </div>
      </div>

      {showDelete && (
        <div
          className="portal-agent-card__footer"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <Popconfirm
            title="确定删除该智能体吗？"
            onConfirm={() => void onDelete(agent.id)}
            okText="确定"
            cancelText="取消"
            disabled={!canDelete}
          >
            <Button
              className="portal-agent-card__delete"
              danger
              size="small"
              icon={<DeleteOutlined />}
              disabled={!canDelete}
            >
              删除
            </Button>
          </Popconfirm>
        </div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [chatModels, setChatModels] = useState<ChatModelOption[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterGroupId, setFilterGroupId] = useState<number | undefined>(undefined);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const data = await agentsApi.getAll();
      setAgents(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取智能体列表失败'));
    } finally {
      setLoading(false);
    }
  };

  const fetchGroups = async () => {
    try {
      const data = await groupsApi.getAll();
      setGroups(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取群组失败'));
    }
  };

  const fetchChatModels = async () => {
    try {
      const data = await modelManageApi.listChatModels();
      setChatModels(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取聊天模型列表失败'));
    }
  };

  useEffect(() => {
    void fetchAgents();
    void fetchGroups();
    void fetchChatModels();
  }, []);

  const agentIdsInFilterGroup = useMemo(() => {
    if (filterGroupId == null) {
      return null;
    }
    const g = groups.find((x) => x.id === filterGroupId);
    if (!g?.agents?.length) {
      return new Set<number>();
    }
    return new Set(g.agents.map((a) => a.id));
  }, [filterGroupId, groups]);

  const displayAgents = useMemo(() => {
    if (agentIdsInFilterGroup === null) {
      return agents;
    }
    return agents.filter((a) => agentIdsInFilterGroup.has(a.id));
  }, [agents, agentIdsInFilterGroup]);

  const requireLogin = () => {
    if (isUserLoggedIn()) {
      return true;
    }
    message.warning('请先登录');
    goLoginPage(navigate, { pathname: location.pathname, search: location.search });
    return false;
  };

  const openCreatePage = () => {
    if (!requireLogin()) {
      return;
    }
    navigate('/agents/new');
  };

  const groupFilterOptions = useMemo(
    () => groups.map((g) => ({ label: g.name, value: g.id })),
    [groups],
  );

  const chatModelLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of chatModels) {
      map.set(m.id, m.provider_name ? `${m.name}（${m.provider_name}）` : m.name);
    }
    return map;
  }, [chatModels]);

  const openAgentDetail = (id: number) => {
    navigate(`/agents/${id}`);
  };

  const handleDelete = async (id: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await agentsApi.delete(id);
      message.success('删除成功');
      void fetchAgents();
    } catch (error: unknown) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>智能体</Title>
        <Paragraph type="secondary" style={{ maxWidth: 720, marginBottom: 0 }}>
          创建不同人设与能力的对话角色，并为其关联技能。点击卡片进入详情页配置。
        </Paragraph>
        <div className="portal-toolbar">
          <div className="portal-toolbar-left">
            <Text type="secondary" style={{ flexShrink: 0 }}>
              群组
            </Text>
            <Select
              allowClear
              placeholder="全部智能体"
              style={{ minWidth: 200, maxWidth: 280 }}
              value={filterGroupId}
              onChange={(v) => setFilterGroupId(v ?? undefined)}
              options={groupFilterOptions}
            />
          </div>
          <div className="portal-toolbar-actions">
            {isUserLoggedIn() && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreatePage}>
                添加智能体
              </Button>
            )}
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        {displayAgents.length === 0 ? (
          <Empty
            description={
              filterGroupId != null ? '该群组下暂无智能体，或尚未加入成员' : '还没有智能体，点击上方「添加智能体」'
            }
          />
        ) : (
          <Row gutter={[16, 16]} className="portal-agents-grid">
            {displayAgents.map((agent) => (
              <Col xs={12} sm={12} md={8} lg={6} xl={4} key={agent.id}>
                <AgentCard
                  agent={agent}
                  modelLabel={
                    agent.chat_model_id
                      ? chatModelLabelById.get(agent.chat_model_id) ?? `ID ${agent.chat_model_id}`
                      : '未配置'
                  }
                  onOpen={openAgentDetail}
                  onDelete={handleDelete}
                  showDelete={isUserLoggedIn()}
                />
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
