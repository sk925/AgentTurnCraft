import { useState, useEffect, useMemo } from 'react';
import {
  Button,
  Card,
  Modal,
  Form,
  Input,
  Popconfirm,
  Tag,
  Select,
  message,
  Row,
  Col,
  Typography,
  Empty,
  Spin,
  Space,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, RobotOutlined } from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { agentsApi, getBackendErrorMessage, goLoginPage, groupsApi, isUserLoggedIn, skillsApi } from '../api';
import type { Agent, Skill, Group } from '../api';

const { Title, Paragraph, Text } = Typography;

function excerpt(text: string | null | undefined, max: number) {
  if (!text) {
    return '—';
  }
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length <= max ? t : `${t.slice(0, max)}…`;
}

export default function AgentsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [filterGroupId, setFilterGroupId] = useState<number | undefined>(undefined);
  const [form] = Form.useForm();

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

  const fetchSkills = async () => {
    try {
      const data = await skillsApi.getAll();
      setSkills(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取技能列表失败'));
    }
  };

  useEffect(() => {
    void fetchAgents();
    void fetchGroups();
    void fetchSkills();
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

  const handleSubmit = async (values: { name: string; description?: string; prompt?: string }) => {
    if (!requireLogin()) {
      return;
    }
    try {
      if (editingAgent) {
        await agentsApi.update(editingAgent.id, values);
        message.success('编辑成功');
      } else {
        await agentsApi.create(values);
        message.success('添加成功');
      }
      setModalVisible(false);
      setEditingAgent(null);
      form.resetFields();
      void fetchAgents();
    } catch (error) {
      message.error(getBackendErrorMessage(error, editingAgent ? '编辑失败' : '添加失败'));
    }
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

  const handleAddSkill = async (agentId: number, skillId: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await agentsApi.addSkill(agentId, skillId);
      message.success('关联成功');
      void fetchAgents();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '关联失败'));
    }
  };

  const handleRemoveSkill = async (agentId: number, skillId: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await agentsApi.removeSkill(agentId, skillId);
      message.success('已解除关联');
      void fetchAgents();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '解除关联失败'));
    }
  };

  const openCreateModal = () => {
    if (!requireLogin()) {
      return;
    }
    setEditingAgent(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEditModal = (agent: Agent) => {
    if (!requireLogin()) {
      return;
    }
    setEditingAgent(agent);
    form.setFieldsValue({
      name: agent.name,
      description: agent.description ?? undefined,
      prompt: agent.prompt ?? undefined,
    });
    setModalVisible(true);
  };

  const skillOptions = useMemo(() => {
    return skills.map((s) => ({ label: s.name, value: s.id }));
  }, [skills]);

  const groupFilterOptions = useMemo(
    () => groups.map((g) => ({ label: g.name, value: g.id })),
    [groups],
  );

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>智能体</Title>
        <Paragraph type="secondary" style={{ maxWidth: 720, marginBottom: 0 }}>
          创建不同人设与能力的对话角色，并为其关联技能。面向访客时，建议用简短、好记的名称与描述。
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
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
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
          <Row gutter={[16, 16]}>
            {displayAgents.map((agent) => {
              const agentSkills = agent.skills ?? [];
              const linkedIds = new Set(agentSkills.map((s) => s.id));
              const addOptions = skillOptions.filter((o) => !linkedIds.has(o.value as number));

              return (
                <Col xs={24} sm={12} lg={8} xl={6} key={agent.id}>
                  <Card className="portal-card" hoverable variant="borderless" style={{ height: '100%' }}>
                    <div className="portal-card__head">
                      <div className="portal-card__avatar" aria-hidden>
                        <RobotOutlined />
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <h3 className="portal-card__title">{agent.name}</h3>
                        <div className="portal-card__meta">
                          创建于 {new Date(agent.create_time).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="portal-card__body">
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        {excerpt(agent.description, 120)}
                      </Text>
                      <div style={{ marginTop: 10 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          提示词摘要
                        </Text>
                        <Paragraph
                          style={{ marginBottom: 0, marginTop: 4, fontSize: 13 }}
                          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        >
                          {agent.prompt || '—'}
                        </Paragraph>
                      </div>
                      <div style={{ marginTop: 12 }} className="portal-card-tags">
                        {agentSkills.map((skill) => (
                          <Tag
                            key={skill.id}
                            closable={isUserLoggedIn()}
                            onClose={() => handleRemoveSkill(agent.id, skill.id)}
                            color="processing"
                          >
                            {skill.name}
                          </Tag>
                        ))}
                      </div>
                      {isUserLoggedIn() && addOptions.length > 0 && (
                        <Select
                          style={{ width: '100%', marginTop: 10 }}
                          placeholder="添加技能"
                          value={undefined}
                          options={addOptions}
                          onChange={(skillId) => {
                            if (typeof skillId === 'number') {
                              void handleAddSkill(agent.id, skillId);
                            }
                          }}
                        />
                      )}
                    </div>
                    {isUserLoggedIn() && (
                      <div className="portal-card__footer">
                        <Space size="small" wrap>
                          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(agent)}>
                            编辑
                          </Button>
                          <Popconfirm
                            title="确定删除该智能体吗？"
                            onConfirm={() => void handleDelete(agent.id)}
                            okText="确定"
                            cancelText="取消"
                          >
                            <Button type="link" danger icon={<DeleteOutlined />}>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      </div>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>

      <Modal
        title={editingAgent ? '编辑智能体' : '添加智能体'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingAgent(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={520}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入智能体名称' }]}>
            <Input placeholder="例如：职场顾问小王" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="一句话介绍角色定位，访客会先看到这段" />
          </Form.Item>
          <Form.Item name="prompt" label="提示词">
            <Input.TextArea rows={6} placeholder="系统提示词，定义语气、知识边界与行为" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
