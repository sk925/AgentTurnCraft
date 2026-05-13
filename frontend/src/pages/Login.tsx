import { useState } from 'react';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi, setUserServiceToken } from '../api';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const fromLoc = (location.state as { from?: { pathname?: string; search?: string; hash?: string } } | undefined)
    ?.from;
  const returnTo =
    fromLoc?.pathname != null && fromLoc.pathname !== ''
      ? `${fromLoc.pathname}${fromLoc.search ?? ''}${fromLoc.hash ?? ''}`
      : '/chat';

  const handleFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const data = await authApi.login(values);
      setUserServiceToken(data.access_token);
      message.success('登录成功');
      void navigate(returnTo, { replace: true });
    } catch (error) {
      console.error('登录失败', error);
      message.error('登录失败，请检查用户名或密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(145deg, #0f172a 0%, #1f2937 60%, #0b5b7a 100%)',
      }}
    >
      <Card style={{ width: 420, borderRadius: 10 }}>
        <Typography.Title level={3} style={{ marginTop: 0, textAlign: 'center' }}>
          Free Chat 登录
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>
          认证接口：`POST /api/auth/login`（本服务 backend）
        </Typography.Paragraph>
        <Form layout="vertical" onFinish={(v) => void handleFinish(v)}>
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
      </Card>
    </div>
  );
}
