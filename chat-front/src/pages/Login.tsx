import { useState, useMemo } from 'react';
import { Button, Form, Input, Typography, message } from 'antd';
import { CommentOutlined, MessageOutlined, RobotOutlined, TeamOutlined } from '@ant-design/icons';
import { useLocation, useNavigate, Navigate } from 'react-router-dom';
import { authApi, isUserLoggedIn, setUserServiceToken } from '../api';
import './LoginPage.css';
import { LoginNeuralCanvas } from './LoginNeuralCanvas';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = useMemo(() => {
    const fromLoc = (location.state as { from?: { pathname?: string; search?: string; hash?: string } } | undefined)
      ?.from;
    const raw =
      fromLoc?.pathname != null && fromLoc.pathname !== ''
        ? `${fromLoc.pathname}${fromLoc.search ?? ''}${fromLoc.hash ?? ''}`
        : '/chat';
    if (raw === '/login' || raw.startsWith('/login?')) {
      return '/chat';
    }
    return raw;
  }, [location.state, location.pathname, location.search, location.hash]);

  if (isUserLoggedIn()) {
    return <Navigate to={returnTo} replace />;
  }

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
    <div className="login-page">
      <LoginNeuralCanvas />
      <div className="login-page__vignette" aria-hidden />
      <div className="login-page__inner">
        <div className="login-page__brand">
          <div className="login-page__mark" aria-hidden>
            <MessageOutlined />
          </div>
          <Typography.Title level={1} className="login-page__title">
            Free Chat
          </Typography.Title>
          <p className="login-page__subtitle">与 AI 轻松对话：单聊、群聊、技能与智能体，一站式工作台。</p>
          <ul className="login-page__highlights">
            <li>
              <CommentOutlined aria-hidden />
              <span>自然语言对话，支持会话记录与多轮上下文。</span>
            </li>
            <li>
              <RobotOutlined aria-hidden />
              <span>智能体与技能编排，按需组合能力与角色。</span>
            </li>
            <li>
              <TeamOutlined aria-hidden />
              <span>群聊协作与工作空间，适合团队场景。</span>
            </li>
          </ul>
        </div>

        <div className="login-page__card">
          <h2 className="login-page__card-title">欢迎回来</h2>
          <p className="login-page__card-hint">使用已开通的账号登录，开始使用工作台。</p>
          <Form
            className="login-page__form"
            layout="vertical"
            size="large"
            onFinish={(v) => void handleFinish(v)}
          >
            <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input autoComplete="username" placeholder="请输入用户名" />
            </Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password autoComplete="current-password" placeholder="请输入密码" />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button htmlType="submit" type="primary" block loading={loading} className="login-page__submit">
                登录
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    </div>
  );
}
