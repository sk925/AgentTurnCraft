import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Layout, Menu, Avatar, Typography, Dropdown, Flex, Tooltip } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AuditOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { fetchMe } from '../api/client';
import { useAuthToken } from '../hooks/useAuthToken';
import type { UserDto } from '../types';

const { Header, Content, Sider } = Layout;

type AdminLayoutProps = {
  children: ReactNode;
};

export function AdminLayout({ children }: AdminLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [, logout] = useAuthToken();
  const [me, setMe] = useState<UserDto | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchMe()
      .then((user) => {
        if (!cancelled) setMe(user);
      })
      .catch(() => {
        if (!cancelled) {
          logout();
          void navigate('/login', { replace: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [logout, navigate]);

  const normalizePath = location.pathname.startsWith('/') ? location.pathname.slice(1) : location.pathname;
  const selectedKeys = ['/'.concat(normalizePath || 'users')];

  return (
    <Layout className="admin-root" style={{ minHeight: '100%' }}>
      <Sider
        width={244}
        className="admin-sider"
        theme="dark"
        breakpoint="lg"
        collapsedWidth={72}
      >
        <div className="admin-sider-brand">
          <div className="admin-sider-mark" aria-hidden>
            <SafetyCertificateOutlined />
          </div>
          <div>
            <Typography.Text className="admin-sider-label">控制中心</Typography.Text>
            <div className="admin-sider-name">IAM</div>
          </div>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          className="admin-menu"
          selectedKeys={selectedKeys}
          items={[
            {
              key: '/users',
              icon: <UserOutlined />,
              label: '用户',
              onClick: () => void navigate('/users'),
            },
            {
              key: '/roles',
              icon: <TeamOutlined />,
              label: '角色',
              onClick: () => void navigate('/roles'),
            },
            {
              key: '/permissions',
              icon: <AuditOutlined />,
              label: '权限',
              onClick: () => void navigate('/permissions'),
            },
          ]}
        />

        <div className="admin-sider-footer">
          <Typography.Text type="secondary" style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
            <SettingOutlined /> 策略与委派
          </Typography.Text>
        </div>
      </Sider>

      <Layout>
        <Header className="admin-header">
          <Flex align="center" justify="flex-end" style={{ width: '100%' }}>
            <Dropdown
              menu={{
                items: [
                  {
                    key: 'out',
                    label: '退出登录',
                    icon: <LogoutOutlined />,
                    onClick: () => {
                      logout();
                      void navigate('/login', { replace: true });
                    },
                  },
                ],
              }}
              trigger={['click']}
              placement="bottomRight"
            >
              <Flex align="center" gap={10} style={{ cursor: 'pointer', userSelect: 'none' }}>
                <Tooltip title="当前登录身份">
                  <Avatar
                    style={{ background: 'linear-gradient(140deg,#c58a2d,#f0c46c)', border: '1px solid rgba(255,255,255,0.35)', color: '#1a1410', fontFamily: 'var(--svc-font-display)', fontWeight: 700 }}
                    size={40}
                  >
                    {(me?.username ?? '?').slice(0, 1).toUpperCase()}
                  </Avatar>
                </Tooltip>
                <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
                  <Typography.Text strong style={{ letterSpacing: 0.02 }}>
                    {me?.username ?? '加载中'}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {me?.is_superuser ? '超级管理员' : '操作员'}
                  </Typography.Text>
                </div>
              </Flex>
            </Dropdown>
          </Flex>
        </Header>

        <Content className="admin-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
