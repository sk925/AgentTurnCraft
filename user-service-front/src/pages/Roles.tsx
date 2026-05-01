import { useEffect, useMemo, useState } from 'react';
import { Button, Flex, Form, Input, Modal, Select, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { createRole, deleteRole, fetchPermissions, fetchRoles, updateRole } from '../api/client';
import type { PermissionDto, RoleDto } from '../types';
import { PageHeader } from '../components/PageHeader';

export default function RolesPage() {
  const [roles, setRoles] = useState<RoleDto[]>([]);
  const [perms, setPerms] = useState<PermissionDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editRole, setEditRole] = useState<RoleDto | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = async () => {
    setLoading(true);
    try {
      const [r, p] = await Promise.all([fetchRoles(), fetchPermissions()]);
      setRoles(r);
      setPerms(p);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const permLabelById = useMemo(() => {
    const m = new Map<number, string>();
    perms.forEach((p) => m.set(p.id, `${p.code} · ${p.name}`));
    return m;
  }, [perms]);

  const columns: ColumnsType<RoleDto> = [
    { title: 'ID', dataIndex: 'id', width: 72 },
    {
      title: '名称',
      dataIndex: 'name',
      width: 160,
      render: (text: string) =>
        text === 'admin' ? (
          <Tag bordered={false} color="volcano">
            {text}
          </Tag>
        ) : (
          <span style={{ fontWeight: 650 }}>{text}</span>
        ),
    },
    { title: '说明', dataIndex: 'description', render: (v) => v ?? '—' },
    {
      title: '权限',
      dataIndex: 'permission_ids',
      render: (ids: number[]) =>
        ids.length === 0 ? (
          <Typography.Text type="secondary">无</Typography.Text>
        ) : (
          <Flex wrap="wrap" gap={6}>
            {ids.slice(0, 6).map((id) => (
              <Tag key={id} bordered={false} className="svc-tag-mono" color="processing">
                {permLabelById.get(id) ?? id}
              </Tag>
            ))}
            {ids.length > 6 ? (
              <Tag bordered={false} color="default">
                +{ids.length - 6}
              </Tag>
            ) : null}
          </Flex>
        ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
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
            disabled={row.name === 'admin'}
            onClick={() => confirmDelete(row)}
          >
            删除
          </Button>
        </Flex>
      ),
    },
  ];

  const openEdit = (r: RoleDto) => {
    setEditRole(r);
    editForm.setFieldsValue({
      name: r.name,
      description: r.description ?? '',
      permission_ids: r.permission_ids,
    });
    setEditOpen(true);
  };

  const confirmDelete = (r: RoleDto) => {
    Modal.confirm({
      title: `删除角色「${r.name}」`,
      centered: true,
      okText: '删除',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deleteRole(r.id);
          message.success('已删除');
          await reload();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      await createRole({
        name: v.name,
        description: v.description || null,
        permission_ids: v.permission_ids ?? [],
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
    if (!editRole) return;
    try {
      const v = await editForm.validateFields();
      await updateRole(editRole.id, {
        name: v.name,
        description: v.description || null,
        permission_ids: v.permission_ids ?? [],
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
        title="角色"
        description="把权限打包成职务模板。内置 admin 受保护不可删除，名称亦不可改写。"
        actions={
          <Flex wrap="wrap" gap={10}>
            <Button className="toolbar-ghost" onClick={() => void reload()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" className="toolbar-primary" onClick={() => setCreateOpen(true)}>
              新建角色
            </Button>
          </Flex>
        }
      />

      <Table
        rowKey="id"
        size="middle"
        sticky
        scroll={{ x: 900 }}
        loading={loading}
        columns={columns}
        dataSource={roles}
        pagination={false}
      />

      <Modal
        title="新建角色"
        open={createOpen}
        centered
        onCancel={() => setCreateOpen(false)}
        onOk={() => void submitCreate()}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical" initialValues={{ permission_ids: [] }}>
          <Form.Item label="名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input placeholder="简述职责边界" />
          </Form.Item>
          <Form.Item label="权限" name="permission_ids">
            <Select
              mode="multiple"
              placeholder="可多选"
              optionFilterProp="label"
              options={perms.map((p) => ({ label: `${p.code} · ${p.name}`, value: p.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editRole ? `编辑「${editRole.name}」` : '编辑角色'}
        open={editOpen}
        centered
        onCancel={() => setEditOpen(false)}
        onOk={() => void submitEdit()}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true }]}
            extra={editRole?.name === 'admin' ? '内置管理员角色名称不可更改' : undefined}
          >
            <Input disabled={editRole?.name === 'admin'} />
          </Form.Item>
          <Form.Item label="说明" name="description">
            <Input />
          </Form.Item>
          <Form.Item label="权限" name="permission_ids">
            <Select
              mode="multiple"
              optionFilterProp="label"
              options={perms.map((p) => ({ label: `${p.code} · ${p.name}`, value: p.id }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
