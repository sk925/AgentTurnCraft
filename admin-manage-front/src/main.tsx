import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import { antdTheme } from './theme';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ConfigProvider locale={zhCN} theme={antdTheme}>
        <AntApp message={{ duration: 2.8, top: 72 }}>
          <App />
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  </StrictMode>,
);
