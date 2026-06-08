import { useState, useEffect } from 'react';
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
import { PlusOutlined, DeleteOutlined, EditOutlined, UsergroupAddOutlined } from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import { agentsApi, getBackendErrorMessage, goLoginPage, groupsApi, isUserLoggedIn } from '../api';
import type { Group, Agent } from '../api';

const { Title, Paragraph } = Typography;

export default function GroupsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [groups, setGroups] = useState<Group[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [form] = Form.useForm();

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const data = await groupsApi.getAll();
      setGroups(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取群组列表失败'));
    } finally {
      setLoading(false);
    }
  };

  const fetchAgents = async () => {
    try {
      const data = await agentsApi.getAll();
      setAgents(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取智能体列表失败'));
    }
  };

  useEffect(() => {
    void fetchGroups();
    void fetchAgents();
  }, []);

  const requireLogin = () => {
    if (isUserLoggedIn()) {
      return true;
    }
    message.warning('请先登录');
    goLoginPage(navigate, { pathname: location.pathname, search: location.search });
    return false;
  };

  const handleSubmit = async (values: { name: string; description?: string; agent_ids?: number[] }) => {
    if (!requireLogin()) {
      return;
    }
    try {
      if (editingGroup) {
        await groupsApi.update(editingGroup.id, values);
        message.success('编辑成功');
      } else {
        await groupsApi.create(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      setEditingGroup(null);
      form.resetFields();
      void fetchGroups();
    } catch (error) {
      message.error(getBackendErrorMessage(error, editingGroup ? '编辑失败' : '创建失败'));
    }
  };

  const handleDelete = async (id: number) => {
    if (!requireLogin()) {
      return;
    }
    try {
      await groupsApi.delete(id);
      message.success('删除成功');
      void fetchGroups();
    } catch (error) {
      message.error(getBackendErrorMessage(error, '删除失败'));
    }
  };

  const openCreateModal = () => {
    if (!requireLogin()) {
      return;
    }
    setEditingGroup(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEditModal = (group: Group) => {
    if (!requireLogin()) {
      return;
    }
    setEditingGroup(group);
    form.setFieldsValue({
      name: group.name,
      description: group.description ?? undefined,
      agent_ids: group.agents?.map((a) => a.id) ?? [],
    });
    setModalVisible(true);
  };

  const agentOptions = agents.map((a) => ({ label: a.name, value: a.id }));

  return (
    <div>
      <div className="portal-page-hero">
        <Title level={2}>群组</Title>
        <Paragraph type="secondary" style={{ maxWidth: 720, marginBottom: 0 }}>
          将多个智能体编为一组，便于在群聊中按组筛选成员、限定讨论角色范围。
        </Paragraph>
        <div className="portal-toolbar">
          <div className="portal-toolbar-left">
            <span style={{ color: 'var(--portal-muted)', fontSize: 13 }}>管理协作分组</span>
          </div>
          <div className="portal-toolbar-actions">
            {isUserLoggedIn() && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                创建群组
              </Button>
            )}
          </div>
        </div>
      </div>

      <Spin spinning={loading}>
        {groups.length === 0 ? (
          <Empty description="还没有群组，创建一个开始编排成员" />
        ) : (
          <Row gutter={[16, 16]}>
            {groups.map((group) => {
              const groupAgents = group.agents ?? [];
              return (
                <Col xs={24} sm={12} lg={8} xl={6} key={group.id}>
                  <Card className="portal-card portal-group-card" hoverable variant="borderless" style={{ height: '100%' }}>
                    <div className="portal-card__head">
                      <div className="portal-card__avatar" aria-hidden>
                        <UsergroupAddOutlined />
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <h3 className="portal-card__title">{group.name}</h3>
                        <div className="portal-card__meta">
                          创建于 {new Date(group.create_time).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <div className="portal-card__body">
                      <Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 12 }} ellipsis={{ rows: 3 }}>
                        {group.description || '暂无描述'}
                      </Paragraph>
                      <div className="portal-card-tags">
                        {groupAgents.map((agent) => (
                          <Tag key={agent.id} color="blue">
                            {agent.name}
                          </Tag>
                        ))}
                      </div>
                    </div>
                    {isUserLoggedIn() && (
                      <div className="portal-card__footer">
                        <Space size="small" wrap>
                          <Button type="link" icon={<EditOutlined />} onClick={() => openEditModal(group)}>
                            编辑
                          </Button>
                          <Popconfirm
                            title="确定删除该群组吗？"
                            onConfirm={() => void handleDelete(group.id)}
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
        title={editingGroup ? '编辑群组' : '创建群组'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingGroup(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={520}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="群组名称" rules={[{ required: true, message: '请输入群组名称' }]}>
            <Input placeholder="例如：产品讨论组" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选，帮助访客理解群组用途" />
          </Form.Item>
          <Form.Item
            name="agent_ids"
            label="选择智能体"
            rules={[{ required: true, message: '请选择至少一个智能体' }]}
          >
            <Select
              mode="multiple"
              placeholder="从已有智能体中选择"
              options={agentOptions}
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
