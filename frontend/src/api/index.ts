import axios, { type AxiosError } from 'axios';
import type { NavigateFunction } from 'react-router-dom';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
});

const USER_SERVICE_BASE_URL = 'http://localhost:8001/api';
const USER_SERVICE_TOKEN_KEY = 'user_service_access_token';

/** 解析后端 JSON：成功体为 { code, message, data }；错误体同样字段，优先读 message，兼容旧版 detail */
export function extractBackendMessage(data: unknown): string | undefined {
  if (data == null || typeof data !== 'object') {
    return undefined;
  }
  const d = data as { message?: string; detail?: unknown };
  if (typeof d.message === 'string' && d.message.length > 0) {
    return d.message;
  }
  if (typeof d.detail === 'string' && d.detail.length > 0) {
    return d.detail;
  }
  return undefined;
}

export function getBackendErrorMessage(error: unknown, fallback: string): string {
  const e = error as AxiosError & { backendMessage?: string };
  if (e.backendMessage) {
    return e.backendMessage;
  }
  return extractBackendMessage(e.response?.data) ?? fallback;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(USER_SERVICE_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    const msg = extractBackendMessage(error.response?.data);
    if (msg) {
      (error as AxiosError & { backendMessage?: string }).backendMessage = msg;
    }
    return Promise.reject(error);
  },
);

/** 从 access_token 解析 `sub`（用户 ID），与后端 JWT 一致；仅用于前端展示/传参，权限以后端校验为准。 */
export function getCurrentUserIdFromToken(): number | null {
  const token = localStorage.getItem(USER_SERVICE_TOKEN_KEY);
  if (!token) {
    return null;
  }
  try {
    const part = token.split('.')[1];
    if (!part) {
      return null;
    }
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const json = JSON.parse(atob(padded)) as { sub?: string };
    const sub = json?.sub;
    if (sub == null || sub === '') {
      return null;
    }
    const n = Number(sub);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export function getUserServiceToken(): string | null {
  return localStorage.getItem(USER_SERVICE_TOKEN_KEY);
}

/** 是否已保存 user-service 的 access_token（仅表示本地有令牌，有效性由后端校验） */
export function isUserLoggedIn(): boolean {
  return Boolean(getUserServiceToken());
}

export type LoginFromLocation = { pathname: string; search?: string; hash?: string };

/** 跳转登录页，登录成功后可用 `from` 回到原页面 */
export function goLoginPage(navigate: NavigateFunction, from: LoginFromLocation) {
  navigate('/login', { state: { from } });
}

export function setUserServiceToken(token: string): void {
  localStorage.setItem(USER_SERVICE_TOKEN_KEY, token);
}

export function clearUserServiceToken(): void {
  localStorage.removeItem(USER_SERVICE_TOKEN_KEY);
}

function ensureArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export interface Skill {
  id: number;
  name: string;
  description: string | null;
  file_path: string | null;
  /** 1 内置（admin 创建） 2 自定义 */
  type?: number;
  create_time: string;
}

export interface Agent {
  id: number;
  name: string;
  description: string | null;
  prompt: string | null;
  /** 1 内置 2 自定义 */
  type?: number;
  create_time: string;
  skills?: Skill[];
}

export interface Group {
  id: number;
  name: string;
  description: string | null;
  /** 1 内置 2 自定义 */
  type?: number;
  create_time: string;
  agents: Agent[];
}

export interface ChatWindowRequest {
  user_message: string;
  org_id: number;
  session_id?: string | null;
  round_id?: string | null;
  session_type?: SessionType;
  /** 群聊：指定后候选与入群智能体仅来自该群组 */
  group_id?: number | null;
  /** 本轮上传文件 id（字符串避免大整数精度丢失） */
  file_ids?: string[] | null;
}

/** 与后端 UploadFileResponse 一致，id 为字符串 */
export interface UploadFileRecord {
  id: string;
  user_id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  create_time?: string;
  preview_url?: string | null;
}

export type SessionType = 'group' | 'ppt' | 'chat';

export interface WorkspaceArtifactFile {
  name: string;
  relative_path: string;
  round_id: string;
  size: number;
  modified_at: number;
}

export interface ChatSession {
  id: string;
  title: string;
  member_id: number;
  create_at: string;
  token_use: number | null;
  session_type: SessionType | string;
}

export interface SessionMessageFileInfo {
  file_id: string;
  file_name: string;
  file_url: string;
  file_type?: string;
}

export interface SessionMessage {
  role_type: 'user' | 'agent_selector' | 'speaker_selector' | 'speaker' | 'assistant';
  message_type: string | null;
  message_content: string;
  speaker_id: number | null;
  speaker_name: string | null;
  file_info?: SessionMessageFileInfo[] | null;
}

export interface ChatStartEvent {
  event: 'start';
  session_id: string;
  round_id: string;
}

export interface ChatFinishedEvent {
  event: 'finished';
  answer: string;
  finish_reason?: string;
}

export interface ChatSpeakerFinishedEvent {
  event: 'speaker_finished';
  answer?: string;
  finish_reason?: string;
}

export interface ChatCreateGroupEvent {
  event: 'create_group';
  group_members: Array<{ id: number; name: string }>;
  select_reason?: string;
}

export interface ChatSelectSpeakerEvent {
  event: 'select_speaker';
  current_speaker: { id: number; name: string };
  current_turn: number;
  speaker_reason?: string;
}

export interface ChatSpeakerEvent {
  event: 'speaker';
  speaker_id: number;
  speaker_name: string;
  content: string;
  timestamp?: number;
}

/** 发言节点内模型 token 增量（由后端 custom 流转发） */
export interface ChatSpeakerStreamEvent {
  event: 'speaker_stream';
  speaker_id: number;
  speaker_name: string;
  delta: string;
  inner_node?: string;
}

/** 发言节点内模型 token 增量（新事件名） */
export interface ChatSpeakerModelStreamEvent {
  event: 'speaker_model_stream';
  speaker_id: number;
  speaker_name: string;
  delta?: string;
  content?: string;
  text?: string;
  inner_node?: string;
}

export type ChatWindowEvent =
  | ChatStartEvent
  | ChatFinishedEvent
  | ChatSpeakerFinishedEvent
  | ChatCreateGroupEvent
  | ChatSelectSpeakerEvent
  | ChatSpeakerEvent
  | ChatSpeakerStreamEvent
  | ChatSpeakerModelStreamEvent;

function parseSSEChunk(chunk: string): ChatWindowEvent[] {
  const events: ChatWindowEvent[] = [];
  const blocks = chunk.split('\n\n');

  blocks.forEach((block) => {
    const line = block
      .split('\n')
      .find((item) => item.trimStart().startsWith('data:'));
    if (!line) {
      return;
    }

    const payload = line.replace(/^data:\s*/, '').trim();
    if (!payload) {
      return;
    }

    try {
      const parsed = JSON.parse(payload) as ChatWindowEvent;
      events.push(parsed);
    } catch (error) {
      console.error('解析 chat_window SSE 失败', error, payload);
    }
  });

  return events;
}

export const skillsApi = {
  getAll: () =>
    api.get<ApiResponse<Skill[]>>('/skills').then((res) => ensureArray<Skill>(res.data?.data)),
  upload: (file: File, description: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('description', description);
    return api
      .post<ApiResponse<Skill>>('/skills', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((res) => res.data.data);
  },
  delete: (id: number) => api.delete(`/skills/${id}`),
};

export const agentsApi = {
  getAll: () => api.get<ApiResponse<Agent[]>>('/agents').then((res) => ensureArray<Agent>(res.data?.data)),
  create: (data: { name: string; description?: string; prompt?: string }) =>
    api.post<ApiResponse<Agent>>('/agents', data).then((res) => res.data.data),
  update: (id: number, data: { name?: string; description?: string; prompt?: string }) =>
    api.put<ApiResponse<Agent>>(`/agents/${id}`, data).then((res) => res.data.data),
  delete: (id: number) => api.delete(`/agents/${id}`),
  addSkill: (agentId: number, skillId: number) =>
    api.post(`/agents/${agentId}/skills/${skillId}`, null),
  removeSkill: (agentId: number, skillId: number) => api.delete(`/agents/${agentId}/skills/${skillId}`),
  getWithSkills: (id: number) => api.get<ApiResponse<Agent>>(`/agents/${id}`).then((res) => res.data.data),
};

export const groupsApi = {
  getAll: () => api.get<ApiResponse<Group[]>>('/groups').then((res) => ensureArray<Group>(res.data?.data)),
  create: (data: { name: string; description?: string; agent_ids?: number[] }) =>
    api.post<ApiResponse<Group>>('/groups', data).then((res) => res.data.data),
  update: (id: number, data: { name?: string; description?: string; agent_ids?: number[] }) =>
    api.put<ApiResponse<Group>>(`/groups/${id}`, data).then((res) => res.data.data),
  delete: (id: number) => api.delete(`/groups/${id}`),
  get: (id: number) => api.get<ApiResponse<Group>>(`/groups/${id}`).then((res) => res.data.data),
};

export const chatWindowApi = {
  streamChat: async (
    data: ChatWindowRequest,
    onEvent: (event: ChatWindowEvent) => void,
  ) => {
    const token = getUserServiceToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch('http://localhost:8000/api/chat_window/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      let detail = `请求失败: ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string; message?: string };
        const fromApi = extractBackendMessage(body);
        if (fromApi) {
          detail = fromApi;
        }
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }

    if (!response.body) {
      throw new Error('服务端未返回流式响应');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        if (buffer.trim()) {
          parseSSEChunk(buffer).forEach(onEvent);
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';

      parts.forEach((part) => {
        parseSSEChunk(part).forEach(onEvent);
      });
    }
  },
  getWorkspaceFiles: async (sessionId: string) => {
    return api
      .get<ApiResponse<WorkspaceArtifactFile[]>>('/chat_window/workspace_files', {
        params: { session_id: sessionId },
      })
      .then((res) => ensureArray<WorkspaceArtifactFile>(res.data?.data));
  },
};

export const uploadFileApi = {
  /** multipart 上传，与主站 axios 同源、自动带 Authorization */
  upload: async (file: File): Promise<UploadFileRecord> => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await api.post<ApiResponse<UploadFileRecord>>('/upload_file', fd);
    const body = res.data;
    if (body.code !== 0 || body.data == null) {
      throw new Error(body.message || '上传失败');
    }
    return body.data;
  },
};

export const sessionsApi = {
  list: (sessionType: SessionType) =>
    api
      .get<ApiResponse<ChatSession[]>>('/sessions', {
        params: { session_type: sessionType },
      })
      .then((res) => ensureArray<ChatSession>(res.data?.data)),
  getMessages: (sessionId: string) =>
    api
      .get<ApiResponse<SessionMessage[]>>(`/sessions/${sessionId}/messages`)
      .then((res) => ensureArray<SessionMessage>(res.data?.data)),
};

export const authApi = {
  login: (payload: { username: string; password: string }) =>
    axios.post<LoginResponse>(`${USER_SERVICE_BASE_URL}/auth/login`, payload).then((res) => res.data),
};

/** WebSocket 消息协议 */
export type WSClientMessage =
  | {
      type: 'chat';
      user_message: string;
      org_id: number;
      session_id?: string | null;
      session_type?: SessionType;
      group_id?: number | null;
      file_ids?: string[] | null;
    }
  | { type: 'catchup'; session_id: string }
  | { type: 'ping' };

export type WSServerMessage =
  | ChatWindowEvent
  | { event: 'connected'; session_id: string }
  | { event: 'catchup_round'; round_id: string | null; events: ChatWindowEvent[]; status: string }
  | { event: 'pong' }
  | { event: 'error'; message: string };

type WSEventCallback = (event: WSServerMessage) => void;

const WS_BASE_URL = 'ws://localhost:8000/api/chat_window/ws';
const PING_INTERVAL = 30000; // 30s
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY = 1000; // 1s

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private callbacks: Set<WSEventCallback> = new Set();
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private sessionId: string | null = null;
  private intentionalClose = false;
  private pendingMessages: WSClientMessage[] = [];

  /** 是否已连接 */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /** 建立 WebSocket 连接，可传入已有 session_id */
  connect(sessionId?: string | null) {
    this.sessionId = sessionId ?? null;
    this.intentionalClose = false;
    this.pendingMessages = [];

    // 关闭已有连接
    if (this.ws) {
      this.ws.onclose = null; // 阻止重连
      this.ws.close();
      this.ws = null;
    }

    const token = getUserServiceToken();
    if (!token) {
      console.error('[ChatWebSocket] 未登录，无法建立连接');
      this._notifyError('未登录，请先登录');
      return;
    }

    const url = `${WS_BASE_URL}?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[ChatWebSocket] 已连接');
      this.reconnectAttempts = 0;
      this._startPing();

      // 发送连接中缓存的消息（catchup 等）
      const hasPendingCatchup = this.pendingMessages.some((m) => m.type === 'catchup');
      while (this.pendingMessages.length > 0) {
        const msg = this.pendingMessages.shift()!;
        this.ws!.send(JSON.stringify(msg));
      }

      // 如果没有排队的 catchup，且设置了 session_id，自动补充
      if (!hasPendingCatchup && this.sessionId) {
        this._send({ type: 'catchup', session_id: this.sessionId });
      }
    };

    this.ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as WSServerMessage;
        this.callbacks.forEach((cb) => cb(data));
      } catch {
        console.error('[ChatWebSocket] 解析服务端消息失败', event.data);
      }
    };

    this.ws.onclose = (event) => {
      console.log(`[ChatWebSocket] 连接关闭: code=${event.code} reason=${event.reason}`);
      this._stopPing();
      if (!this.intentionalClose) {
        this._tryReconnect(event.code);
      }
    };

    this.ws.onerror = (_event) => {
      console.error('[ChatWebSocket] 连接错误');
    };
  }

  /** 断开连接 */
  disconnect() {
    this.intentionalClose = true;
    this._stopPing();
    this.pendingMessages = [];
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /** 发送聊天消息，返回 true 表示已发送 */
  sendChat(params: {
    user_message: string;
    org_id: number;
    session_id?: string | null;
    session_type?: SessionType;
    group_id?: number | null;
    file_ids?: string[] | null;
  }): boolean {
    if (!this.isConnected()) {
      this._notifyError('连接未就绪，消息发送失败');
      return false;
    }
    this._send({ type: 'chat', ...params });
    return true;
  }

  /** 请求断线重放 */
  sendCatchup(sessionId: string) {
    this.sessionId = sessionId;
    this._send({ type: 'catchup', session_id: sessionId });
  }

  /** 注册事件回调 */
  onEvent(callback: WSEventCallback): () => void {
    this.callbacks.add(callback);
    return () => {
      this.callbacks.delete(callback);
    };
  }

  /** 更新 session_id（页面切换时） */
  setSessionId(sessionId: string | null) {
    this.sessionId = sessionId;
  }

  private _send(message: WSClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      this.pendingMessages.push(message);
    } else {
      console.warn('[ChatWebSocket] 连接未就绪，无法发送消息');
    }
  }

  private _notifyError(message: string) {
    const errorEvent: WSServerMessage = { event: 'error', message };
    this.callbacks.forEach((cb) => cb(errorEvent));
  }

  private _startPing() {
    this._stopPing();
    this.pingTimer = setInterval(() => {
      this._send({ type: 'ping' });
    }, PING_INTERVAL);
  }

  private _stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private _tryReconnect(closeCode?: number) {
    // 认证失败（4001）：不重连，提示用户重新登录
    if (closeCode === 4001) {
      console.error('[ChatWebSocket] 令牌无效或已过期，不重连');
      this._notifyError('登录已过期，请重新登录');
      return;
    }
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('[ChatWebSocket] 重连次数已达上限');
      this._notifyError('连接失败，请刷新页面重试');
      return;
    }
    const delay = RECONNECT_BASE_DELAY * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts += 1;
    console.log(`[ChatWebSocket] ${delay}ms 后尝试第 ${this.reconnectAttempts} 次重连`);
    this.reconnectTimer = setTimeout(() => {
      this.connect(this.sessionId);
    }, delay);
  }
}

/** 全局单例 */
export const chatWebSocket = new ChatWebSocket();

export default api;
