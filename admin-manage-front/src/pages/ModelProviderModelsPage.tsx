import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Flex,
  Form,
  Input,
  Modal,
  Select,
  Table,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import {
  createChatModel,
  deleteChatModel,
  fetchChatModels,
  fetchModelProvider,
  updateChatModel,
} from '../api/client';
import type { ChatModelDto, ModelProviderDto } from '../types';
import { CHAT_MODEL_TYPE_OPTIONS } from '../constants/modelManage';
import { PageHeader } from '../components/PageHeader';

const typeLabel = (v: string) => CHAT_MODEL_TYPE_OPTIONS.find((o) => o.value === v)?.label ?? v;

export default function ModelProviderModelsPage() {
  const { providerId } = useParams<{ providerId: string }>();
  const navigate = useNavigate();
  const decodedId = useMemo(() => (providerId ? decodeURIComponent(providerId) : ''), [providerId]);

  const [provider, setProvider] = useState<ModelProviderDto | null>(null);
  const [models, setModels] = useState<ChatModelDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ChatModelDto | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = async () => {
    if (!decodedId) return;
    setLoading(true);
    try {
      const [p, m] = await Promise.all([fetchModelProvider(decodedId), fetchChatModels(decodedId)]);
      setProvider(p);
      setModels(m);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载失败');
      setProvider(null);
      setModels([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!decodedId) {
      void navigate('/model-manage', { replace: true });
      return;
    }
    void reload();
  }, [decodedId, navigate]);

  const openCreate = () => {
    createForm.setFieldsValue({
      name: '',
      model_type: 'text_generation',
      description: '',
    });
    setCreateOpen(true);
  };

  const openEdit = (row: ChatModelDto) => {
    setEditing(row);
    editForm.setFieldsValue({
      name: row.name,
      model_type: row.model_type,
      description: row.description ?? '',
    });
    setEditOpen(true);
  };

  const submitCreate = async () => {
    if (!decodedId) return;
    try {
      const v = await createForm.validateFields();
      await createChatModel({
        name: v.name,
        provider_id: decodedId,
        model_type: v.model_type,
        description: v.description?.trim() ? v.description : null,
      });
      message.success('已添加模型');
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
      await updateChatModel({
        id: editing.id,
        name: v.name,
        model_type: v.model_type,
        description: v.description?.trim() ? v.description : null,
      });
      message.success('已保存');
      setEditOpen(false);
      setEditing(null);
      void reload();
    } catch (e) {
      if (e instanceof Error && e.message) message.error(e.message);
    }
  };

  const confirmDelete = (row: ChatModelDto) => {
    Modal.confirm({
      title: `删除模型「${row.name}」`,
      okText: '删除',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          await deleteChatModel(row.id);
          message.success('已删除');
          void reload();
        } catch (e) {
          message.error(e instanceof Error ? e.message : '删除失败');
        }
      },
    });
  };

  const columns: ColumnsType<ChatModelDto> = [
    { title: '名称', dataIndex: 'name', width: 180, ellipsis: true },
    {
      title: '类型',
      dataIndex: 'model_type',
      width: 140,
      render: (v: string) => typeLabel(v),
    },
    {
      title: '说明',
      dataIndex: 'description',
      ellipsis: true,
      render: (v: string | null | undefined) => v ?? '—',
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_, row) => (
        <Flex gap={4}>
          <Button type="link" size="small" style={{ paddingInline: 4 }} onClick={() => openEdit(row)}>
            编辑
          </Button>
          <Button type="link" size="small" danger style={{ paddingInline: 4 }} onClick={() => confirmDelete(row)}>
            删除
          </Button>
        </Flex>
      ),
    },
  ];

  return (
    <div className="svc-page">
      <Flex align="center" gap={12} style={{ marginBottom: 12 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => void navigate('/model-manage')}>
          返回提供者列表
        </Button>
      </Flex>

      <PageHeader
        title={provider ? `${provider.name} · 模型` : '模型列表'}
        description={provider?.base_url ?? '加载中…'}
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} disabled={!provider}>
            添加模型
          </Button>
        }
      />

      <Table<ChatModelDto>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={models}
        pagination={false}
        scroll={{ x: 720 }}
        style={{ marginTop: 8 }}
      />

      <Modal title="添加模型" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => void submitCreate()} okText="添加" destroyOnClose>
        <Form form={createForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="name" label="模型名称 / 调用名" rules={[{ required: true, message: '请填写名称' }]}>
            <Input placeholder="例如 gpt-4o-mini" />
          </Form.Item>
          <Form.Item name="model_type" label="类型" rules={[{ required: true }]}>
            <Select
              options={CHAT_MODEL_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="编辑模型" open={editOpen} onCancel={() => { setEditOpen(false); setEditing(null); }} onOk={() => void submitEdit()} okText="保存" destroyOnClose>
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="name" label="模型名称" rules={[{ required: true, message: '请填写名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="model_type" label="类型" rules={[{ required: true }]}>
            <Select
              options={CHAT_MODEL_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
