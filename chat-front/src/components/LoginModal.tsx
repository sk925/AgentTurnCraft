import { useState } from 'react';
import { Button, Form, Input, Modal, Typography, message } from 'antd';
import { authApi, setUserServiceToken } from '../api';

type LoginModalProps = {
  open: boolean;
  onCancel: () => void;
  /** 登录成功并已写入 token 后调用 */
  onSuccess: () => void;
};

export default function LoginModal({ open, onCancel, onSuccess }: LoginModalProps) {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<{ username: string; password: string }>();

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const data = await authApi.login(values);
      setUserServiceToken(data.access_token);
      message.success('登录成功');
      form.resetFields();
      onSuccess();
    } catch (error) {
      console.error('登录失败', error);
      message.error('登录失败，请检查用户名或密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={
        <Typography.Title level={4} style={{ margin: 0 }}>
          Free Chat 登录
        </Typography.Title>
      }
      open={open}
      onCancel={onCancel}
      footer={null}
      destroyOnHidden
      width={420}
    >
      <Form form={form} layout="vertical" onFinish={(v) => void handleFinish(v)}>
        <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button htmlType="submit" type="primary" block loading={loading}>
          登录
        </Button>
      </Form>
    </Modal>
  );
}
