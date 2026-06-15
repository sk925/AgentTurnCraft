/// <reference types="vite/client" />

interface DesktopConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  isDesktop?: boolean;
}

interface ElectronAPI {
  openSettings: () => Promise<void>;
  getVersion: () => Promise<string>;
}

declare global {
  interface Window {
    desktopConfig?: DesktopConfig;
    electronAPI?: ElectronAPI;
  }
}

export {};
