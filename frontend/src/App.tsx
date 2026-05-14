import { useCallback, useEffect, useMemo, useState } from 'react';
import { Avatar, Button, Layout, Menu, Popconfirm, Typography, message, type MenuProps } from 'antd';
import {
  LogoutOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
  UsergroupAddOutlined,
} from '@ant-design/icons';
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import LoginModal from './components/LoginModal';
import { PortalSessionsProvider } from './PortalSessionsContext';
import SkillsPage from './pages/Skills';
import AgentsPage from './pages/Agents';
import GroupsPage from './pages/Groups';
import ChatWindowPage from './pages/ChatWindow';
import LoginPage from './pages/Login';
import {
  authApi,
  chatPathForSessionType,
  clearUserServiceToken,
  getBackendErrorMessage,
  getCurrentUserIdFromToken,
  getUserServiceToken,
  isUserLoggedIn,
  OPEN_LOGIN_MODAL_EVENT,
  permissionsApi,
  sessionsApi,
} from './api';
import type { ChatSession } from './api';
import './App.css';

const { Sider, Content } = Layout;

/** 侧栏路由 key → PermissionMenu 成员名（与后端 permission.code 一致） */
const MENU_PATH_TO_PERMISSION: Record<string, string> = {
  '/skills': 'skill_management',
  '/agents': 'agent_management',
  '/groups': 'group_management',
  '/chat': 'chat',
  '/group-chat': 'group_chat',
};

function navSelectedKey(pathname: string): string {
  if (pathname.startsWith('/group-chat')) {
    return '/group-chat';
  }
  if (pathname === '/' || pathname.startsWith('/chat')) {
    return '/chat';
  }
  return pathname;
}

function sessionsMatchingChatMenu(sessionsList: ChatSession[], menuKey: '/chat' | '/group-chat'): ChatSession[] {
  const wantGroup = menuKey === '/group-chat';
  return sessionsList.filter((s) => {
    const st = String(s.session_type ?? 'chat').toLowerCase();
    const isGroup = st === 'group' || st === 'group_chat';
    return wantGroup ? isGroup : !isGroup;
  });
}

/** 未登录不可进入门户（主页及各业务页），统一跳转登录页 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isUserLoggedIn()) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsReady, setSessionsReady] = useState(false);
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  /** 登录成功后递增，触发会话列表、权限与侧栏展示刷新 */
  const [authTick, setAuthTick] = useState(0);
  const [myPermissionCodes, setMyPermissionCodes] = useState<string[] | null>(null);
  const [permissionsReady, setPermissionsReady] = useState(true);

  const isChatRoute =
    location.pathname === '/' ||
    location.pathname.startsWith('/chat') ||
    location.pathname.startsWith('/group-chat');

  const menuItems = useMemo((): MenuProps['items'] => {
    const all: MenuProps['items'] = [
      { key: '/skills', icon: <ToolOutlined />, label: '技能' },
      { key: '/agents', icon: <RobotOutlined />, label: '智能体' },
      { key: '/groups', icon: <UsergroupAddOutlined />, label: '群组' },
      { key: '/chat', icon: <MessageOutlined />, label: '对话' },
      { key: '/group-chat', icon: <TeamOutlined />, label: '群聊' },
    ];
    if (!isUserLoggedIn()) {
      return [];
    }
    if (!permissionsReady || myPermissionCodes === null) {
      return all;
    }
    const allowed = new Set(myPermissionCodes);
    return all!.filter((item) => {
      const key = item && 'key' in item ? String(item.key) : '';
      const need = MENU_PATH_TO_PERMISSION[key];
      if (!need) {
        return true;
      }
      return allowed.has(need);
    });
  }, [myPermissionCodes, permissionsReady]);

  const handleMenuClick = async (key: string) => {
    if (key !== '/chat' && key !== '/group-chat') {
      navigate(key);
      return;
    }

    if (!isUserLoggedIn()) {
      navigate(key);
      return;
    }
    const menuKey = key === '/group-chat' ? '/group-chat' : '/chat';
    try {
      const targetSessions = sessionsMatchingChatMenu(sessions, menuKey);
      if (targetSessions.length > 0) {
        navigate(`${key}?session_id=${targetSessions[0].id}`);
        return;
      }
    } catch (error) {
      message.error(getBackendErrorMessage(error, '加载会话列表失败'));
    }

    navigate(key);
  };

  const loadSessions = useCallback(async () => {
    if (!isUserLoggedIn()) {
      setSessions([]);
      setSessionsReady(true);
      return;
    }
    setSessionsReady(false);
    try {
      const data = await sessionsApi.list();
      setSessions(data);
    } catch (error) {
      message.error(getBackendErrorMessage(error, '获取会话列表失败'));
    } finally {
      setSessionsReady(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadMyPermissions = async () => {
      if (!isUserLoggedIn()) {
        setMyPermissionCodes(null);
        setPermissionsReady(true);
        return;
      }
      setPermissionsReady(false);
      try {
        const codes = await permissionsApi.getMine();
        if (!cancelled) {
          setMyPermissionCodes(codes);
        }
      } catch (error) {
        if (!cancelled) {
          message.warning(getBackendErrorMessage(error, '获取权限失败，侧栏暂时显示全部菜单'));
          setMyPermissionCodes(null);
        }
      } finally {
        if (!cancelled) {
          setPermissionsReady(true);
        }
      }
    };
    void loadMyPermissions();
    return () => {
      cancelled = true;
    };
  }, [authTick]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions, authTick]);

  useEffect(() => {
    const openLogin = () => setLoginModalOpen(true);
    window.addEventListener(OPEN_LOGIN_MODAL_EVENT, openLogin);
    return () => window.removeEventListener(OPEN_LOGIN_MODAL_EVENT, openLogin);
  }, []);

  const handleLogout = async () => {
    const t = getUserServiceToken();
    if (t) {
      try {
        await authApi.logout();
      } catch {
        /* 仍清理本地状态 */
      }
    }
    clearUserServiceToken();
    setSessions([]);
    setSessionsReady(true);
    setAuthTick((v) => v + 1);
    navigate('/login', { replace: true });
    message.success('已退出登录');
  };

  const portalSessionsValue = useMemo(
    () => ({ sessions, ready: sessionsReady }),
    [sessions, sessionsReady],
  );

  return (
    <PortalSessionsProvider value={portalSessionsValue}>
      <Layout className="portal-shell" hasSider>
      <Sider width={236} breakpoint="lg" collapsedWidth={0} className="portal-sider" theme="light">
        <div className="portal-sider-brand" onClick={() => navigate('/chat')} role="presentation">
          <span className="portal-sider-brand__name">Free Chat</span>
          <span className="portal-sider-brand__sub">与 AI 轻松对话</span>
        </div>
        <div className="portal-sider-main">
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

          {/* 会话记录：已登录时始终展示，与当前菜单页无关；列表仅由登录态 / authTick 触发拉取 */}
          {isUserLoggedIn() && (
            <div className="portal-sider-sessions">
              <div className="portal-sider-sessions__head">
                <span className="portal-sider-sessions__label">会话记录</span>
                <button
                  type="button"
                  className="portal-sider-sessions__new"
                  onClick={() =>
                    navigate(location.pathname.startsWith('/group-chat') ? '/group-chat' : '/chat')
                  }
                >
                  <PlusOutlined />
                </button>
              </div>
              <div className="portal-sider-sessions__list">
                {sessions.length === 0 ? (
                  <span className="portal-sider-sessions__empty">
                    {sessionsReady ? '暂无记录' : '加载中…'}
                  </span>
                ) : (
                  sessions.map((s) => {
                    const sid = new URLSearchParams(location.search).get('session_id');
                    const here: '/chat' | '/group-chat' = location.pathname.startsWith('/group-chat')
                      ? '/group-chat'
                      : '/chat';
                    const active =
                      sid === s.id && chatPathForSessionType(s.session_type) === here;
                    return (
                      <button
                        key={s.id}
                        type="button"
                        className={`portal-sider-sessions__item${active ? ' portal-sider-sessions__item--active' : ''}`}
                        title={s.title}
                        onClick={() =>
                          navigate(
                            `${chatPathForSessionType(s.session_type)}?session_id=${encodeURIComponent(s.id)}`,
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
        </div>

        <div className="portal-sider-footer">
          {isUserLoggedIn() ? (
            <div className="portal-sider-footer__inner">
              <div className="portal-sider-footer__user-row">
                <Avatar
                  className="portal-sider-footer__avatar"
                  size={40}
                  icon={<UserOutlined />}
                  aria-hidden
                />
                <div className="portal-sider-footer__user-text">
                  <Typography.Text strong ellipsis className="portal-sider-footer__name">
                    用户 {getCurrentUserIdFromToken() ?? '—'}
                  </Typography.Text>
                </div>
              </div>
              <Popconfirm
                title="退出登录？"
                description="退出后将清除本机保存的登录状态。"
                okText="退出"
                cancelText="取消"
                okButtonProps={{ danger: true }}
                onConfirm={() => void handleLogout()}
              >
                <Button block icon={<LogoutOutlined />} className="portal-sider-footer__logout-btn" size="middle">
                  退出登录
                </Button>
              </Popconfirm>
            </div>
          ) : (
            <div className="portal-sider-footer__inner portal-sider-footer__inner--login">
              <Button block type="primary" size="middle" onClick={() => setLoginModalOpen(true)}>
                登录
              </Button>
            </div>
          )}
        </div>
        <LoginModal
          open={loginModalOpen}
          onCancel={() => setLoginModalOpen(false)}
          onSuccess={() => {
            setLoginModalOpen(false);
            setAuthTick((t) => t + 1);
          }}
        />
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
    </PortalSessionsProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
