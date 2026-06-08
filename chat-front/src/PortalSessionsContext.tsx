import { createContext, useContext, type ReactNode } from 'react';
import type { ChatSession } from './api';

export type PortalSessionsValue = {
  sessions: ChatSession[];
  /** 已按当前登录态完成一次会话列表拉取（含未登录的空结果） */
  ready: boolean;
};

const PortalSessionsContext = createContext<PortalSessionsValue | null>(null);

export function PortalSessionsProvider({
  value,
  children,
}: {
  value: PortalSessionsValue;
  children: ReactNode;
}) {
  return <PortalSessionsContext.Provider value={value}>{children}</PortalSessionsContext.Provider>;
}

export function usePortalSessions(): PortalSessionsValue {
  const v = useContext(PortalSessionsContext);
  if (v == null) {
    throw new Error('usePortalSessions 须在 PortalSessionsProvider 内使用');
  }
  return v;
}
