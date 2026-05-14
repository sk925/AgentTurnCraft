import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  Modal,
  Row,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  CloudOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import {
  createModelProvider,
  deleteModelProvider,
  fetchModelProviders,
  updateModelProvider,
} from '../api/client';
import type { ModelProviderDto } from '../types';
import { PageHeader } from '../components/PageHeader';

export default function ModelManageProvidersPage() {
  const navigate = useNavigate();
  const [providers, setProviders] = useState<ModelProviderDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ModelProviderDto | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = async () => {
    setLoading(true);
    try {
      const list = await fetchModelProviders();
      setProviders(list);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const openCreate = () => {
    createForm.resetFields();
    setCreateOpen(true);
  };

  const openEdit = (p: ModelProviderDto) => {
    setEditing(p);
    editForm.setFieldsValue({
      name: p.name,
      base_url: p.base_url,
      api_key: '',
    });
    setEditOpen(true);
  };

  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      await createModelProvider({
        name: v.name,
        base_url: v.base_url,
        api_key: v.api_key,
      });
      message.success('已创建');
      setCreateOpen(false);
      void reload();
    } catch (e) {
      if (e instanceof Error && e.message) message.error(e.message);
    }
  };

  const submitEdit = async () => {
    if (!editing) return;
    try {
      const v = await editForm.validateFields();
      await updateModelProvider({
        id: editing.id,
        name: v.name,
        base_url: v.base_url,
        api_key: v.api_key?.trim() ? v.api_key : undefined,
      });
      message.success('已保存');
      setEditOpen(false);
      setEditing(null);
      void reload();
    } catch (e) {
      if (e instanceof Error && e.message) message.error(e.message);
    }
  };

  const confirmDelete = (p: ModelProviderDto) => {
    Modal.confirm({
      title: `删除提供者「${p.name}」`,
      content: '将级联删除其下所有已配置的聊天模型，且不可恢复。',
      okText: '删除',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          await deleteModelProvider(p.id);
          message.success('已删除');
          void reload();
        } catch (e) {
          message.error(e instanceof Error ? e.message : '删除失败');
        }
      },
    });
  };

  return (
    <div className="svc-page">
      <PageHeader
        title="模型管理"
        description="外层卡片为模型提供者；点进卡片可维护其下的聊天模型。"
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建提供者
          </Button>
        }
      />

      <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
        {providers.map((p) => (
          <Col xs={24} sm={12} lg={8} xl={6} key={p.id}>
            <Card
              loading={loading}
              hoverable
              className="model-provider-card"
              onClick={() => void navigate(`/model-manage/providers/${encodeURIComponent(p.id)}`)}
              styles={{
                body: { minHeight: 132 },
              }}
            >
              <Flex vertical gap={10} style={{ height: '100%' }}>
                <Flex align="center" gap={10}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 12,
                      background: 'linear-gradient(135deg, rgba(24,144,255,0.18), rgba(114,46,209,0.2))',
                      display: 'grid',
                      placeItems: 'center',
                      color: '#1677ff',
                    }}
                  >
                    <CloudOutlined style={{ fontSize: 20 }} />
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <Typography.Title level={5} style={{ margin: 0 }} ellipsis>
                      {p.name}
                    </Typography.Title>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                      {p.base_url}
                    </Typography.Text>
                  </div>
                </Flex>
                <Typography.Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }}>
                  点击进入该提供者的模型列表。
                </Typography.Paragraph>
                <Flex gap={6} justify="flex-end" onClick={(ev) => ev.stopPropagation()}>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(p)}>
                    编辑
                  </Button>
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => confirmDelete(p)}>
                    删除
                  </Button>
                </Flex>
              </Flex>
            </Card>
          </Col>
        ))}
      </Row>

      {!loading && providers.length === 0 ? (
        <Card style={{ marginTop: 16 }} variant="borderless">
          <Flex vertical align="center" gap={12} style={{ padding: '24px 0' }}>
            <ApiOutlined style={{ fontSize: 40, color: 'rgba(0,0,0,0.25)' }} />
            <Typography.Text type="secondary">暂无模型提供者，请先新建。</Typography.Text>
          </Flex>
        </Card>
      ) : null}

      <Modal
        title="新建模型提供者"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void submitCreate()}
        okText="创建"
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写名称' }]}>
            <Input placeholder="例如 OpenAI 兼容网关" />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: '请填写 Base URL' }]}>
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: true, message: '请填写 API Key' }]}>
            <Input.Password placeholder="密钥仅保存在服务端" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑模型提供者"
        open={editOpen}
        onCancel={() => {
          setEditOpen(false);
          setEditing(null);
        }}
        onOk={() => void submitEdit()}
        okText="保存"
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请填写名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: '请填写 Base URL' }]}>
            <Input />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            extra="留空表示不修改已保存的密钥。"
          >
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
