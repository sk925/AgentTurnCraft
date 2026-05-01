import { useEffect, useState } from 'react';
import { Button, Flex, Form, Input, Modal, Table, Typography, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { createPermission, deletePermission, fetchPermissions, updatePermission } from '../api/client';
import type { PermissionDto } from '../types';
import { PageHeader } from '../components/PageHeader';

const SEEDED_CODES = new Set([
  'user:read',
  'user:write',
  'user:delete',
  'role:read',
  'role:write',
  'permission:read',
  'permission:write',
]);

export default function PermissionsPage() {
  const [rows, setRows] = useState<PermissionDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editPerm, setEditPerm] = useState<PermissionDto | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = async () => {
    setLoading(true);
    try {
      const data = await fetchPermissions();
      setRows(data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const columns: ColumnsType<PermissionDto> = [
    { title: 'ID', dataIndex: 'id', width: 72 },
    {
      title: '编码',
      dataIndex: 'code',
      width: 200,
      render: (text: string) => (
        <Tag bordered={false} color={SEEDED_CODES.has(text) ? 'default' : 'blue'} className="svc-tag-mono">
          {text}
        </Tag>
      ),
    },
    { title: '名称', dataIndex: 'name', width: 140 },
    { title: '说明', dataIndex: 'description', render: (v) => v ?? '—' },
    {
      title: '操作',
      key: 'actions',
      width: 176,
      fixed: 'right' as const,
      render: (_, row) => (
        <Flex gap={4}>
          <Button type="link" style={{ paddingInline: 4 }} onClick={() => openEdit(row)}>
            编辑
          </Button>
          <Button
            type="link"
            danger
            style={{ paddingInline: 4 }}
            disabled={SEEDED_CODES.has(row.code)}
            onClick={() => confirmDelete(row)}
          >
            删除
          </Button>
        </Flex>
      ),
    },
  ];

  const openEdit = (p: PermissionDto) => {
    setEditPerm(p);
    editForm.setFieldsValue({
      name: p.name,
      description: p.description ?? '',
    });
    setEditOpen(true);
  };

  const confirmDelete = (p: PermissionDto) => {
    Modal.confirm({
      title: `删除权限「${p.code}」`,
      centered: true,
      okText: '删除',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deletePermission(p.id);
          message.success('已删除');
          await reload();
        } catch {
          message.error('删除失败（可能为内置权限）');
        }
      },
    });
  };

  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      await createPermission({
        code: v.code,
        name: v.name,
        description: v.description || null,
      });
      message.success('已创建');
      setCreateOpen(false);
      createForm.resetFields();
      await reload();
    } catch {
      message.error('创建失败');
    }
  };

  const submitEdit = async () => {
    if (!editPerm) return;
    try {
      const v = await editForm.validateFields();
      await updatePermission(editPerm.id, {
        name: v.name,
        description: v.description || null,
      });
      message.success('已保存');
      setEditOpen(false);
      await reload();
    } catch {
      message.error('保存失败');
    }
  };

  return (
    <div className="data-panel">
      <PageHeader
        title="权限"
        description="粒度化的能力令牌（code）；系统预置的一组不可删除，但可继续在业务侧引用。"
        actions={
          <Flex wrap="wrap" gap={10}>
            <Button className="toolbar-ghost" onClick={() => void reload()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" className="toolbar-primary" onClick={() => setCreateOpen(true)}>
              新建权限
            </Button>
          </Flex>
        }
      />

      <Table
        rowKey="id"
        size="middle"
        sticky
        scroll={{ x: 820 }}
        loading={loading}
        columns={columns}
        dataSource={rows}
        pagination={false}
      />

      <Modal
        title="新建权限"
        open={createOpen}
        centered
        onCancel={() => setCreateOpen(false)}
        onOk={() => void submitCreate()}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical">
          <Form.Item label="编码" name="code" rules={[{ required: true }]} extra="形如 resource:action，全小写与冒号">
            <Input placeholder="project:approve" />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editPerm ? `编辑「${editPerm.code}」` : '编辑权限'}
        open={editOpen}
        centered
        onCancel={() => setEditOpen(false)}
        onOk={() => void submitEdit()}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Typography.Paragraph type="secondary" style={{ marginTop: -4 }}>
            编码作为稳定主键不提供修改；仅能调整展示名称与说明。
          </Typography.Paragraph>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
