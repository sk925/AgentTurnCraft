import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button, Card, Form, Input, Typography, message } from 'antd';
import { login, TOKEN_KEY } from '../api/client';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname ?? '/users';

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await login(values.username, values.password);
      localStorage.setItem(TOKEN_KEY, res.access_token);
      message.success('已通过校验，欢迎回来');
      void navigate(from, { replace: true });
    } catch {
      message.error('校验失败：用户名或口令不正确');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-scene">
      <section className="login-hero" aria-labelledby="login-hero-heading">
        <p className="login-kicker">Identity · Access · Admin</p>
        <h1 id="login-hero-heading" className="login-title">
          以策展式界面，管理好每一次访问权限。
        </h1>
        <p className="login-lede">
          IAM 工作台把用户、角色与权限编成一条清晰的治理链——少即是多，但该有的力度一分不减。
        </p>
        <div className="login-note">
          本地演示账号：<strong>admin</strong> · <strong>admin123</strong>
          <br />
          Production 请务必轮换口令与 JWT 密钥。
        </div>
      </section>

      <aside className="login-aside">
        <Card className="login-card" variant="borderless">
          <Typography.Title level={3} className="login-card-title">
            进入控制台
          </Typography.Title>
          <p className="login-card-helper">
            使用已开通的账户登录。开发环境下由 Vite 将 <code>/api</code> 转发至 free-chat backend（默认{' '}
            <code>http://localhost:8000</code>）。
          </p>
          <Form layout="vertical" onFinish={(v) => void onFinish(v)} requiredMark="optional">
            <Form.Item label="用户名" name="username" rules={[{ required: true, message: '必填' }]}>
              <Input size="large" placeholder="例如 admin" autoComplete="username" />
            </Form.Item>
            <Form.Item label="口令" name="password" rules={[{ required: true, message: '必填' }]}>
              <Input.Password size="large" placeholder="••••••••" autoComplete="current-password" />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={loading}
              className="toolbar-primary"
            >
              登录
            </Button>
          </Form>
          <p className="login-card-footer">首次部署后请先完成密钥与 DATABASE_URL 配置。</p>
        </Card>
      </aside>
    </div>
  );
}
