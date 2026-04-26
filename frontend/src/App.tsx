import { useEffect, useState } from 'react';
import { Divider, Layout, Menu, Typography } from 'antd';
import { CommentOutlined, RobotOutlined, ToolOutlined } from '@ant-design/icons';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import SkillsPage from './pages/Skills';
import AgentsPage from './pages/Agents';
import ChatWindowPage from './pages/ChatWindow';
import { sessionsApi } from './api';
import type { ChatSession } from './api';
import './App.css';

const { Sider, Content } = Layout;

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [memberId] = useState(1);
  const [sessions, setSessions] = useState<ChatSession[]>([]);

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
      icon: <CommentOutlined />,
      label: '对话',
    },
  ];

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const data = await sessionsApi.list(memberId);
        setSessions(data);
      } catch (error) {
        console.error('获取会话列表失败', error);
      }
    };
    void loadSessions();
  }, [memberId, location.pathname]);

  return (
    <Layout className="layout" style={{ minHeight: '100vh' }}>
      <Sider width={220} theme="dark">
        <div style={{ color: 'white', fontSize: '20px', fontWeight: 700, padding: '20px 16px 12px 16px' }}>
          Free Chat
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname.startsWith('/chat') ? '/chat' : location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
        <Divider style={{ margin: '8px 0', borderColor: 'rgba(255,255,255,0.18)' }} />
        <div style={{ padding: '0 12px 12px 12px' }}>
          <Typography.Text style={{ color: 'rgba(255,255,255,0.75)', fontSize: 12 }}>
            历史对话
          </Typography.Text>
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
                  onClick={() => navigate(`/chat?session_id=${session.id}`)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'transparent',
                    color: '#fff',
                    border: '1px solid rgba(255,255,255,0.15)',
                    borderRadius: 6,
                    padding: '6px 8px',
                    cursor: 'pointer',
                    opacity: 0.88,
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
            <Route path="/chat" element={<ChatWindowPage />} />
            <Route path="/" element={<ChatWindowPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
