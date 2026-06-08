import axios, { type AxiosError } from 'axios';
import type { NavigateFunction } from 'react-router-dom';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
});

const USER_SERVICE_TOKEN_KEY = 'user_service_access_token';

export const authApi = {
  login: (payload: { username: string; password: string }) =>
    api.post<LoginResponse>('/auth/login', payload).then((res) => res.data),
  logout: () => api.post<{ message: string }>('/auth/logout').then((res) => res.data),
};

/** 与后端 PermissionMineOut 一致 */
export interface MyPermissionsOut {
  codes: string[];
}

export const permissionsApi = {
  getMine: () => api.get<MyPermissionsOut>('/permissions/me').then((res) => res.data.codes),
};

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

/** 是否已保存 access_token（仅表示本地有令牌，有效性由后端校验） */
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

/** App 侧监听后打开侧栏 `LoginModal`（与具体页面解耦） */
export const OPEN_LOGIN_MODAL_EVENT = 'free-chat:open-login-modal';

/** 在提示（如 `message.error`）展示后延迟打开登录弹窗 */
export function requestOpenLoginModal(delayMs = 800): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.setTimeout(() => {
    window.dispatchEvent(new CustomEvent(OPEN_LOGIN_MODAL_EVENT));
  }, delayMs);
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
  /** 默认对话模型（base_chat_model.id，字符串避免大整数精度丢失） */
  chat_model_id?: string | null;
  skills?: Skill[];
}

/** 与后端 ChatModelResponse 对齐，用于智能体绑定模型下拉 */
export interface ChatModelOption {
  id: string;
  name: string;
  provider_id: string;
  provider_name: string;
  model_type: string;
  description: string | null;
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

/** 后端 `session_type` → 前端聊天路由（用于侧栏点击与 URL 对齐） */
export function chatPathForSessionType(sessionType: string | undefined | null): '/chat' | '/group-chat' {
  const t = String(sessionType ?? 'chat').toLowerCase();
  if (t === 'group' || t === 'group_chat') {
    return '/group-chat';
  }
  return '/chat';
}

export interface SessionMessageFileInfo {
  file_id: string;
  file_name: string;
  file_url: string;
  file_type?: string;
}

export interface SessionToolCallItem {
  tool_name: string;
  tool_args?: Record<string, unknown> | string | null;
  tool_id: string;
  /** 由前端在加载历史时合并 tool_out 填入 */
  result?: string | null;
}

export interface SessionMessage {
  role_type: 'user' | 'agent_selector' | 'speaker_selector' | 'speaker' | 'assistant';
  message_type: string | null;
  message_content: string;
  speaker_id: number | null;
  speaker_name: string | null;
  file_info?: SessionMessageFileInfo[] | null;
  tool_call_id?: string | null;
  tool_calls?: SessionToolCallItem[] | null;
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

/** ask_user_question 表单字段（与后端 UserInputField 对齐） */
export interface SpeakerInterruptQuestionField {
  question: string;
  field_key: string;
  field_label: string;
  field_type: string;
  placeholder?: string | null;
  choices?: string[] | null;
}

export interface SpeakerInterruptArgs {
  reason: string;
  questions: SpeakerInterruptQuestionField[];
}

export interface ChatSpeakerInterruptEvent {
  event: 'speaker_interrupt';
  args: SpeakerInterruptArgs;
  tool_id?: string;
}

/** 实时：工具调用（与历史 message_type=tool_call 对齐） */
export interface ChatSpeakerToolCallEvent {
  event: 'speaker_tool_call';
  speaker_id: number;
  speaker_name: string;
  tool_calls: SessionToolCallItem[];
}

/** 实时：工具执行结果（与历史 message_type=tool_out 对齐） */
export interface ChatSpeakerToolOutEvent {
  event: 'speaker_tool_out';
  speaker_id: number;
  speaker_name: string;
  tool_name: string;
  tool_id: string;
  content: string;
}

export type ChatWindowEvent =
  | ChatStartEvent
  | ChatFinishedEvent
  | ChatSpeakerFinishedEvent
  | ChatCreateGroupEvent
  | ChatSelectSpeakerEvent
  | ChatSpeakerEvent
  | ChatSpeakerStreamEvent
  | ChatSpeakerModelStreamEvent
  | ChatSpeakerInterruptEvent
  | ChatSpeakerToolCallEvent
  | ChatSpeakerToolOutEvent;

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
      console.error('解析 chat SSE 失败', error, payload);
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

export const modelManageApi = {
  listChatModels: () =>
    api
      .get<ApiResponse<ChatModelOption[]>>('/model-manage/chat-models')
      .then((res) => ensureArray<ChatModelOption>(res.data?.data)),
};

export const agentsApi = {
  getAll: () => api.get<ApiResponse<Agent[]>>('/agents').then((res) => ensureArray<Agent>(res.data?.data)),
  create: (data: { name: string; description?: string; prompt?: string; chat_model_id?: string | null }) =>
    api.post<ApiResponse<Agent>>('/agents', data).then((res) => res.data.data),
  update: (id: number, data: { name?: string; description?: string; prompt?: string; chat_model_id?: string | null }) =>
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
    const response = await fetch('http://localhost:8000/api/chat', {
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
      .get<ApiResponse<WorkspaceArtifactFile[]>>('/chat/workspace_files', {
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
  /** 不传 `sessionType` 时返回当前用户全部会话（与后端 `session_type` 查询参数省略一致） */
  list: (sessionType?: SessionType) =>
    api
      .get<ApiResponse<ChatSession[]>>('/sessions', {
        params: sessionType != null ? { session_type: sessionType } : {},
      })
      .then((res) => ensureArray<ChatSession>(res.data?.data)),
  getMessages: (sessionId: string) =>
    api
      .get<ApiResponse<SessionMessage[]>>(`/sessions/${sessionId}/messages`)
      .then((res) => ensureArray<SessionMessage>(res.data?.data)),
  delete: (sessionId: string) =>
    api.delete<ApiResponse<{ deleted: boolean; session_id: string }>>(`/sessions/${sessionId}`),
};

/** WebSocket 消息协议（连接建立后须先发送 type: auth） */
export type WSClientMessage =
  | { type: 'auth'; token: string }
  | {
      type: 'chat';
      user_message: string;
      org_id: number;
      session_id?: string | null;
      /** 表单 resume 等续跑场景须传上一轮 round_id，与后端 Redis 频道一致 */
      round_id?: string | null;
      session_type?: SessionType;
      group_id?: number | null;
      /** 单聊时指定智能体 id（字符串，与后端 WindowChatRequest 一致）；省略则使用服务端默认智能体 */
      single_agent_id?: string | null;
      file_ids?: string[] | null;
      resume?: { data?: Record<string, string | string[]>; cancel?: boolean };
    }
  | { type: 'catchup'; session_id: string }
  | { type: 'ping' };

export type WSServerMessage =
  | ChatWindowEvent
  | { event: 'connected'; session_id: string }
  | { event: 'authenticated' }
  | { event: 'catchup_round'; round_id: string | null; events: ChatWindowEvent[]; status: string }
  | { event: 'pong' }
  | { event: 'error'; message: string }
  | { event: 'auth_error'; message: string };

type WSEventCallback = (event: WSServerMessage) => void;

const WS_BASE_URL = 'ws://localhost:8000/api/chat/ws';
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
  /** 非预期断线重连后，在 authenticated 时补发 catchup */
  private catchupOnNextAuth = false;
  /** 服务端已对首包 auth 返回 authenticated 之前，业务消息先入队 */
  private wsAuthenticated = false;
  /** 本轮连接是否已通过 onmessage 提示过 auth_error（避免与 onclose 4001 重复弹窗） */
  private authErrorNotified = false;

  /** 是否已连接且已完成 auth */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.wsAuthenticated;
  }

  /** 无有效连接时建立连接（新建会话发消息、进入聊天页时调用） */
  ensureConnected(): void {
    if (this.isConnected()) {
      return;
    }
    if (this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }
    this.connect();
  }

  /**
   * 建立 WebSocket 连接。已连接且已认证时默认不重复建连。
   * forceReconnect：非预期断线后的重连，认证成功后会 catchup。
   */
  connect(options?: { forceReconnect?: boolean }) {
    const force = options?.forceReconnect ?? false;
    if (!force && this.isConnected()) {
      return;
    }
    if (!force && this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.intentionalClose = false;
    if (force) {
      this.pendingMessages = [];
    }

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

    this.wsAuthenticated = false;
    this.authErrorNotified = false;
    const socket = new WebSocket(WS_BASE_URL);
    this.ws = socket;

    socket.onopen = () => {
      if (this.ws !== socket) {
        return;
      }
      console.log('[ChatWebSocket] 已连接，发送认证');
      socket.send(JSON.stringify({ type: 'auth', token }));
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      if (this.ws !== socket) {
        return;
      }
      try {
        const data = JSON.parse(event.data) as WSServerMessage;
        if ('event' in data && data.event === 'authenticated') {
          this.wsAuthenticated = true;
          this.reconnectAttempts = 0;
          this._startPing();
          this._flushPendingAfterAuth();
        }
        if ('event' in data && data.event === 'auth_error') {
          this.authErrorNotified = true;
        }
        this.callbacks.forEach((cb) => cb(data));
      } catch {
        console.error('[ChatWebSocket] 解析服务端消息失败', event.data);
      }
    };

    socket.onclose = (event) => {
      if (this.ws !== socket) {
        return;
      }
      console.log(`[ChatWebSocket] 连接关闭: code=${event.code} reason=${event.reason}`);
      this.ws = null;
      this.wsAuthenticated = false;
      this._stopPing();
      if (!this.intentionalClose) {
        this._tryReconnect(event.code, event.reason);
      }
    };

    socket.onerror = (_event) => {
      if (this.ws !== socket) {
        return;
      }
      console.error('[ChatWebSocket] 连接错误');
    };
  }

  /** 断开连接 */
  disconnect() {
    this.intentionalClose = true;
    this.wsAuthenticated = false;
    this.authErrorNotified = false;
    this._stopPing();
    this.pendingMessages = [];
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      const socket = this.ws;
      this.ws = null;
      socket.onclose = null;
      socket.close();
    }
  }

  /** 发送聊天消息，返回 true 表示已发送 */
  sendChat(params: {
    user_message: string;
    org_id: number;
    session_id?: string | null;
    round_id?: string | null;
    session_type?: SessionType;
    group_id?: number | null;
    single_agent_id?: string | null;
    file_ids?: string[] | null;
    resume?: { data?: Record<string, string | string[]>; cancel?: boolean };
  }): boolean {
    this.ensureConnected();
    if (!this.ws) {
      this._notifyError('连接未就绪，消息发送失败');
      return false;
    }
    this._send({ type: 'chat', ...params });
    return true;
  }

  /** 提交 speaker_interrupt 表单，恢复 LangGraph 执行 */
  sendInterruptResume(params: {
    org_id: number;
    session_id: string;
    round_id: string;
    session_type?: SessionType;
    group_id?: number | null;
    resume: { data?: Record<string, string | string[]>; cancel?: boolean };
  }): boolean {
    return this.sendChat({
      user_message: '',
      org_id: params.org_id,
      session_id: params.session_id,
      round_id: params.round_id,
      session_type: params.session_type,
      group_id: params.group_id,
      resume: params.resume,
    });
  }

  /** 请求断线重放 */
  sendCatchup(sessionId: string) {
    this.sessionId = sessionId;
    this.ensureConnected();
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

  private _flushPendingAfterAuth() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    while (this.pendingMessages.length > 0) {
      const msg = this.pendingMessages.shift()!;
      this.ws.send(JSON.stringify(msg));
    }
    if (this.catchupOnNextAuth && this.sessionId) {
      this.catchupOnNextAuth = false;
      this.ws.send(JSON.stringify({ type: 'catchup', session_id: this.sessionId }));
    }
  }

  private _send(message: WSClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      if (!this.wsAuthenticated) {
        this.pendingMessages.push(message);
        return;
      }
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

  private _tryReconnect(closeCode?: number, closeReason?: string) {
    // 认证失败（4001）：不重连，提示用户重新登录
    if (closeCode === 4001) {
      console.error('[ChatWebSocket] 令牌无效或已过期，不重连');
      if (!this.authErrorNotified) {
        const detail = (closeReason && String(closeReason).trim()) || '登录已过期，请重新登录';
        this._notifyError(detail);
        requestOpenLoginModal(800);
      }
      this.authErrorNotified = false;
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
      this.catchupOnNextAuth = Boolean(this.sessionId);
      this.connect({ forceReconnect: true });
    }, delay);
  }
}

/** 全局单例 */
export const chatWebSocket = new ChatWebSocket();

export default api;
