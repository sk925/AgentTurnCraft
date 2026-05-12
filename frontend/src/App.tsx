import { useEffect, useState } from 'react';
import { Button, Layout, Menu, message } from 'antd';
import {
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  TeamOutlined,
  ToolOutlined,
  UsergroupAddOutlined,
} from '@ant-design/icons';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import SkillsPage from './pages/Skills';
import AgentsPage from './pages/Agents';
import GroupsPage from './pages/Groups';
import ChatWindowPage from './pages/ChatWindow';
import LoginPage from './pages/Login';
import {
  clearUserServiceToken,
  getBackendErrorMessage,
  goLoginPage,
  isUserLoggedIn,
  sessionsApi,
} from './api';
import type { ChatSession, SessionType } from './api';
import './App.css';

const { Sider, Content } = Layout;

function navSelectedKey(pathname: string): string {
  if (pathname.startsWith('/group-chat')) {
    return '/group-chat';
  }
  if (pathname === '/' || pathname.startsWith('/chat')) {
    return '/chat';
  }
  return pathname;
}

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const currentSessionType: SessionType = location.pathname.startsWith('/group-chat') ? 'group' : 'chat';
  const isChatRoute =
    location.pathname.startsWith('/chat') || location.pathname.startsWith('/group-chat');

  const menuItems = [
    { key: '/skills', icon: <ToolOutlined />, label: '技能' },
    { key: '/agents', icon: <RobotOutlined />, label: '智能体' },
    { key: '/groups', icon: <UsergroupAddOutlined />, label: '群组' },
    { key: '/chat', icon: <MessageOutlined />, label: '对话' },
    { key: '/group-chat', icon: <TeamOutlined />, label: '群聊' },
  ];

  const handleMenuClick = async (key: string) => {
    if (key !== '/chat' && key !== '/group-chat') {
      navigate(key);
      return;
    }

    const targetSessionType: SessionType = key === '/group-chat' ? 'group' : 'chat';
    if (!isUserLoggedIn()) {
      navigate(key);
      return;
    }
    try {
      const targetSessions =
        targetSessionType === currentSessionType ? sessions : await sessionsApi.list(targetSessionType);
      if (targetSessions.length > 0) {
        navigate(`${key}?session_id=${targetSessions[0].id}`);
        return;
      }
    } catch (error) {
      message.error(getBackendErrorMessage(error, '加载会话列表失败'));
    }

    navigate(key);
  };

  useEffect(() => {
    const loadSessions = async () => {
      if (!isUserLoggedIn()) {
        setSessions([]);
        return;
      }
      try {
        const data = await sessionsApi.list(currentSessionType);
        setSessions(data);
      } catch (error) {
        message.error(getBackendErrorMessage(error, '获取会话列表失败'));
      }
    };
    void loadSessions();
  }, [currentSessionType]);

  return (
    <Layout className="portal-shell" hasSider>
      <Sider width={236} breakpoint="lg" collapsedWidth={0} className="portal-sider" theme="light">
        <div className="portal-sider-brand" onClick={() => navigate('/chat')} role="presentation">
          <span className="portal-sider-brand__name">Free Chat</span>
          <span className="portal-sider-brand__sub">与 AI 轻松对话</span>
        </div>
        <div className="portal-sider-nav">
          <Menu
            mode="inline"
            theme="light"
            className="portal-sider-menu"
            selectedKeys={[navSelectedKey(location.pathname)]}
            items={menuItems}
            onClick={({ key }) => void handleMenuClick(String(key))}
          />
        </div>

        {/* 会话记录列表：对话/群聊页面时显示在菜单下方 */}
        {isChatRoute && (
          <div className="portal-sider-sessions">
            <div className="portal-sider-sessions__head">
              <span className="portal-sider-sessions__label">
                {currentSessionType === 'group' ? '群聊记录' : '对话记录'}
              </span>
              <button
                type="button"
                className="portal-sider-sessions__new"
                onClick={() => navigate(currentSessionType === 'group' ? '/group-chat' : '/chat')}
              >
                <PlusOutlined />
              </button>
            </div>
            <div className="portal-sider-sessions__list">
              {sessions.length === 0 ? (
                <span className="portal-sider-sessions__empty">
                  {isUserLoggedIn() ? '暂无记录' : '登录后查看'}
                </span>
              ) : (
                sessions.map((s) => {
                  const active = new URLSearchParams(location.search).get('session_id') === s.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      className={`portal-sider-sessions__item${active ? ' portal-sider-sessions__item--active' : ''}`}
                      title={s.title}
                      onClick={() =>
                        navigate(
                          `${currentSessionType === 'group' ? '/group-chat' : '/chat'}?session_id=${s.id}`,
                        )
                      }
                    >
                      {s.title}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        )}

        <div className="portal-sider-footer">
          {isUserLoggedIn() ? (
            <Button
              block
              icon={<LogoutOutlined />}
              onClick={() => {
                clearUserServiceToken();
                setSessions([]);
                navigate('/login', { replace: true });
              }}
            >
              退出登录
            </Button>
          ) : (
            <Button
              block
              type="primary"
              onClick={() =>
                goLoginPage(navigate, {
                  pathname: location.pathname,
                  search: location.search,
                })
              }
            >
              登录
            </Button>
          )}
        </div>
      </Sider>

      <Layout className="portal-main">
        <Content
          className={`portal-content${isChatRoute ? ' portal-content--chat' : ' portal-content--catalog'}`}
        >
          <Routes>
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/groups" element={<GroupsPage />} />
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
        <Route path="/*" element={<AppLayout />} />
      </Routes>
    </BrowserRouter>
  );
}
