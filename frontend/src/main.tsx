import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <ConfigProvider
    locale={zhCN}
    theme={{
      algorithm: theme.defaultAlgorithm,
      token: {
        colorPrimary: '#2563eb',
        colorInfo: '#2563eb',
        borderRadius: 8,
        fontFamily:
          "'IBM Plex Sans', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        fontSize: 14,
        colorBgLayout: '#f4f7fb',
        colorText: '#0f172a',
        colorTextSecondary: '#475569',
      },
      components: {
        Card: {
          borderRadiusLG: 12,
          paddingLG: 20,
        },
        Table: {
          borderRadius: 8,
        },
        Button: {
          controlHeight: 36,
        },
      },
    }}
  >
    <App />
  </ConfigProvider>,
)
