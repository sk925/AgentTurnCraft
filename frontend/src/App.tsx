import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Button, Divider, Layout, Menu, Typography } from 'antd';
import { LogoutOutlined, MessageOutlined, PlusOutlined, RobotOutlined, TeamOutlined, ToolOutlined } from '@ant-design/icons';
import { BrowserRouter, Navigate, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import SkillsPage from './pages/Skills';
import AgentsPage from './pages/Agents';
import ChatWindowPage from './pages/ChatWindow';
import LoginPage from './pages/Login';
import { clearUserServiceToken, getUserServiceToken, sessionsApi } from './api';
import type { ChatSession, SessionType } from './api';
import './App.css';

const { Sider, Content } = Layout;

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  if (!getUserServiceToken()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [memberId] = useState(1);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const selectedSessionId = new URLSearchParams(location.search).get('session_id');

  const currentSessionType: SessionType = location.pathname.startsWith('/group-chat') ? 'group' : 'chat';

  const menuItems = [
    {
      key: '/skills',
      icon: <ToolOutlined />,
      label: '技能管理',
    },
    {
      key: '/agents',
      icon: <RobotOutlined />,
      label: '智能体管理',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: '对话',
    },
    {
      key: '/group-chat',
      icon: <TeamOutlined />,
      label: '群聊',
    },
  ];

  const handleMenuClick = async (key: string) => {
    if (key !== '/chat' && key !== '/group-chat') {
      navigate(key);
      return;
    }

    const targetSessionType: SessionType = key === '/group-chat' ? 'group' : 'chat';
    try {
      const targetSessions =
        targetSessionType === currentSessionType ? sessions : await sessionsApi.list(memberId, targetSessionType);
      if (targetSessions.length > 0) {
        navigate(`${key}?session_id=${targetSessions[0].id}`);
        return;
      }
    } catch (error) {
      console.error('切换菜单时加载会话失败', error);
    }

    // 无历史会话时进入空白新建页
    navigate(key);
  };

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const data = await sessionsApi.list(memberId, currentSessionType);
        setSessions(data);
      } catch (error) {
        console.error('获取会话列表失败', error);
      }
    };
    void loadSessions();
  }, [memberId, currentSessionType]);

  return (
    <Layout className="layout" style={{ minHeight: '100vh' }}>
      <Sider width={220} theme="dark">
        <div
          style={{
            color: 'white',
            fontSize: '20px',
            fontWeight: 700,
            padding: '20px 16px 12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>Free Chat</span>
          <Button
            type="text"
            size="small"
            icon={<LogoutOutlined />}
            style={{ color: 'rgba(255,255,255,0.85)' }}
            onClick={() => {
              clearUserServiceToken();
              navigate('/login', { replace: true });
            }}
          />
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname.startsWith('/chat') ? '/chat' : location.pathname]}
          items={menuItems}
          onClick={({ key }) => void handleMenuClick(String(key))}
          style={{ borderRight: 0 }}
        />
        <Divider style={{ margin: '8px 0', borderColor: 'rgba(255,255,255,0.18)' }} />
        <div style={{ padding: '0 12px 12px 12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography.Text style={{ color: 'rgba(255,255,255,0.75)', fontSize: 12 }}>
              历史对话
            </Typography.Text>
            <button
              type="button"
              onClick={() => navigate(currentSessionType === 'group' ? '/group-chat' : '/chat')}
              style={{
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                background: 'transparent',
                color: 'rgba(255,255,255,0.88)',
                fontSize: 12,
                lineHeight: '18px',
                padding: '2px 8px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <PlusOutlined />
              {currentSessionType === 'group' ? '新建群聊' : '新建对话'}
            </button>
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sessions.length === 0 ? (
              <Typography.Text style={{ color: 'rgba(255,255,255,0.45)', fontSize: 12 }}>
                暂无会话
              </Typography.Text>
            ) : (
              sessions.map((session) => (
                <button
                  type="button"
                  key={session.id}
                  onClick={() =>
                    navigate(
                      `${currentSessionType === 'group' ? '/group-chat' : '/chat'}?session_id=${session.id}`,
                    )
                  }
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    color: '#fff',
                    border: '1px solid rgba(255,255,255,0.15)',
                    borderRadius: 6,
                    padding: '6px 8px',
                    cursor: 'pointer',
                    opacity: 0.88,
                    borderColor: selectedSessionId === session.id ? 'rgba(0, 209, 255, 1)' : 'rgba(255,255,255,0.15)',
                    background: selectedSessionId === session.id ? 'rgba(0, 209, 255, 0.10)' : 'transparent',
                    boxShadow: selectedSessionId === session.id ? '0 0 0 1px rgba(0, 209, 255, 0.35)' : 'none',
                  }}
                >
                  <div style={{ fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {session.title}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </Sider>
      <Layout>
        <Content style={{ padding: '24px' }}>
          <Routes>
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/chat" element={<ChatWindowPage sessionType="chat" />} />
            <Route path="/group-chat" element={<ChatWindowPage sessionType="group" />} />
            <Route path="/" element={<ChatWindowPage sessionType="chat" />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={(
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          )}
        />
      </Routes>
    </BrowserRouter>
  );
}
