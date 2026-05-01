import { useEffect, useMemo, useState } from 'react';
import { Button, Flex, Form, Input, Modal, Select, Switch, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  createUser,
  deleteUser,
  fetchMe,
  fetchRoles,
  fetchUsers,
  updateUser,
} from '../api/client';
import type { RoleDto, UserDto } from '../types';
import { PageHeader } from '../components/PageHeader';

export default function UsersPage() {
  const [users, setUsers] = useState<UserDto[]>([]);
  const [roles, setRoles] = useState<RoleDto[]>([]);
  const [me, setMe] = useState<UserDto | null>(null);
  const [loading, setLoading] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editUser, setEditUser] = useState<UserDto | null>(null);

  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const reload = async () => {
    setLoading(true);
    try {
      const [u, r, self] = await Promise.all([fetchUsers(), fetchRoles(), fetchMe()]);
      setUsers(u);
      setRoles(r);
      setMe(self);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const roleNameById = useMemo(() => {
    const m = new Map<number, string>();
    roles.forEach((r) => m.set(r.id, r.name));
    return m;
  }, [roles]);

  const columns: ColumnsType<UserDto> = [
    { title: 'ID', dataIndex: 'id', width: 72 },
    {
      title: '用户名',
      dataIndex: 'username',
      width: 148,
      render: (text: string) => <span style={{ fontWeight: 650 }}>{text}</span>,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      render: (v) =>
        v ? <span className="svc-tag-mono">{v}</span> : <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: '角色',
      dataIndex: 'role_ids',
      render: (ids: number[]) =>
        ids.length === 0 ? (
          <Typography.Text type="secondary">未分配</Typography.Text>
        ) : (
          <Flex wrap="wrap" gap={6}>
            {ids.map((id) => (
              <Tag key={id} bordered={false} color="gold" className="svc-tag-mono">
                {roleNameById.get(id) ?? id}
              </Tag>
            ))}
          </Flex>
        ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 108,
      render: (v: boolean) =>
        v ? (
          <Tag bordered={false} color="success">
            启用
          </Tag>
        ) : (
          <Tag bordered={false}>禁用</Tag>
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
            disabled={row.id === me?.id}
            onClick={() => confirmDelete(row)}
          >
            删除
          </Button>
        </Flex>
      ),
    },
  ];

  const openEdit = (u: UserDto) => {
    setEditUser(u);
    editForm.setFieldsValue({
      email: u.email ?? '',
      is_active: u.is_active,
      role_ids: u.role_ids,
      password: '',
    });
    setEditOpen(true);
  };

  const confirmDelete = (u: UserDto) => {
    Modal.confirm({
      title: `删除用户「${u.username}」`,
      content: '此操作不可撤销。若该用户有关联会话，请先确认业务侧已同步。',
      okText: '删除',
      okButtonProps: { danger: true },
      centered: true,
      onOk: async () => {
        try {
          await deleteUser(u.id);
          message.success('已删除');
          await reload();
        } catch {
          message.error('删除失败（权限不足或受保护账号）');
        }
      },
    });
  };

  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      await createUser({
        username: v.username,
        password: v.password,
        email: v.email || null,
        is_active: !!v.is_active,
        role_ids: v.role_ids ?? [],
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
    if (!editUser) return;
    try {
      const v = await editForm.validateFields();
      const payload: Parameters<typeof updateUser>[1] = {
        email: v.email || null,
        is_active: !!v.is_active,
        role_ids: v.role_ids,
      };
      if (v.password) {
        payload.password = v.password;
      }
      await updateUser(editUser.id, payload);
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
        title="用户"
        description="创建账户并绑定角色。删除他人需具备 user:delete；不可在列表中移除当前会话自身。"
        actions={
          <Flex wrap="wrap" gap={10}>
            <Button className="toolbar-ghost" onClick={() => void reload()} loading={loading}>
              刷新
            </Button>
            <Button type="primary" className="toolbar-primary" onClick={() => setCreateOpen(true)}>
              新建用户
            </Button>
          </Flex>
        }
      />
      <Table
        rowKey="id"
        size="middle"
        sticky
        scroll={{ x: 960 }}
        loading={loading}
        columns={columns}
        dataSource={users}
        pagination={false}
      />

      <Modal
        title="新建用户"
        open={createOpen}
        centered
        onCancel={() => setCreateOpen(false)}
        onOk={() => void submitCreate()}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical" initialValues={{ is_active: true, role_ids: [] }}>
          <Form.Item label="用户名" name="username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, min: 6 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item label="邮箱" name="email">
            <Input type="email" />
          </Form.Item>
          <Form.Item label="启用" name="is_active" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="角色" name="role_ids">
            <Select mode="multiple" placeholder="可选" options={roles.map((r) => ({ label: r.name, value: r.id }))} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editUser ? `编辑「${editUser.username}」` : '编辑用户'}
        open={editOpen}
        centered
        onCancel={() => setEditOpen(false)}
        onOk={() => void submitEdit()}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="邮箱" name="email">
            <Input type="email" />
          </Form.Item>
          <Form.Item label="新口令（留空不改）" name="password">
            <Input.Password />
          </Form.Item>
          <Form.Item label="启用" name="is_active" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="角色" name="role_ids">
            <Select mode="multiple" options={roles.map((r) => ({ label: r.name, value: r.id }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
