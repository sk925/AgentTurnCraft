import { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Popconfirm, Card, Tag, Select, message } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { agentsApi, skillsApi } from '../api';
import type { Agent, Skill } from '../api';

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [form] = Form.useForm();

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const data = await agentsApi.getAll();
      setAgents(data);
    } catch (error) {
      message.error('获取智能体列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchSkills = async () => {
    try {
      const data = await skillsApi.getAll();
      setSkills(data);
    } catch (error) {
      console.error('获取技能列表失败', error);
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchSkills();
  }, []);

  const handleSubmit = async (values: any) => {
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
      fetchAgents();
    } catch (error) {
      message.error(editingAgent ? '编辑失败' : '添加失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await agentsApi.delete(id);
      message.success('删除成功');
      fetchAgents();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleAddSkill = async (agentId: number, skillId: number) => {
    try {
      await agentsApi.addSkill(agentId, skillId);
      message.success('关联成功');
      fetchAgents();
    } catch (error) {
      message.error('关联失败');
    }
  };

  const handleRemoveSkill = async (agentId: number, skillId: number) => {
    try {
      await agentsApi.removeSkill(agentId, skillId);
      message.success('解除关联成功');
      fetchAgents();
    } catch (error) {
      message.error('解除关联失败');
    }
  };

  const openCreateModal = () => {
    setEditingAgent(null);
    form.resetFields();
    setModalVisible(true);
  };

  const openEditModal = (agent: Agent) => {
    setEditingAgent(agent);
    form.setFieldsValue({
      name: agent.name,
      description: agent.description ?? undefined,
      prompt: agent.prompt ?? undefined,
    });
    setModalVisible(true);
  };

  const skillOptions = skills.map((s) => ({ label: s.name, value: s.id }));

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '提示词',
      dataIndex: 'prompt',
      key: 'prompt',
      ellipsis: true,
    },
    {
      title: '关联技能',
      dataIndex: 'skills',
      key: 'skills',
      render: (agentSkills: Skill[] = [], record: Agent) => (
        <>
          {agentSkills.map((skill) => (
            <Tag
              key={skill.id}
              closable
              onClose={() => handleRemoveSkill(record.id, skill.id)}
              color="blue"
            >
              {skill.name}
            </Tag>
          ))}
          <Select
            style={{ width: 120 }}
            placeholder="添加技能"
            value={undefined}
            onChange={(skillId) => {
              if (typeof skillId === 'number') {
                handleAddSkill(record.id, skillId);
              }
            }}
            options={skillOptions}
          />
        </>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'create_time',
      key: 'create_time',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Agent) => (
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<EditOutlined />} onClick={() => openEditModal(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除该智能体吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  return (
    <Card
      title="智能体管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          添加智能体
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={agents}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={editingAgent ? '编辑智能体' : '添加智能体'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingAgent(null);
          form.resetFields();
        }}
        onOk={form.submit}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入智能体名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="prompt" label="提示词">
            <Input.TextArea rows={5} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
