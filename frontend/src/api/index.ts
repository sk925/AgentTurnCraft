import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
});

export interface Skill {
  id: number;
  name: string;
  description: string | null;
  file_path: string | null;
  create_time: string;
}

export interface Agent {
  id: number;
  name: string;
  description: string | null;
  prompt: string | null;
  create_time: string;
  skills?: Skill[];
}

export interface ChatWindowRequest {
  user_message: string;
  org_id: number;
  member_id: number;
  session_id?: string | null;
  round_id?: string | null;
}

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
  session_type: string;
}

export interface SessionMessage {
  role_type: 'user' | 'agent_selector' | 'speaker_selector' | 'speaker' | 'assistant';
  message_type: string | null;
  message_content: string;
  speaker_id: number | null;
  speaker_name: string | null;
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
  getAll: () => api.get<Skill[]>('/skills').then(res => res.data),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<Skill>('/skills', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(res => res.data);
  },
  delete: (id: number) => api.delete(`/skills/${id}`),
};

export const agentsApi = {
  getAll: () => api.get<Agent[]>('/agents').then(res => res.data),
  create: (data: { name: string; description?: string; prompt?: string }) =>
    api.post<Agent>('/agents', data).then(res => res.data),
  update: (id: number, data: { name?: string; description?: string; prompt?: string }) =>
    api.put<Agent>(`/agents/${id}`, data).then(res => res.data),
  delete: (id: number) => api.delete(`/agents/${id}`),
  addSkill: (agentId: number, skillId: number) =>
    api.post(`/agents/${agentId}/skills/${skillId}`),
  removeSkill: (agentId: number, skillId: number) =>
    api.delete(`/agents/${agentId}/skills/${skillId}`),
  getWithSkills: (id: number) => api.get<Agent>(`/agents/${id}`).then(res => res.data),
};

export const chatWindowApi = {
  streamChat: async (
    data: ChatWindowRequest,
    onEvent: (event: ChatWindowEvent) => void,
  ) => {
    const response = await fetch('http://localhost:8000/api/chat_window/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`);
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
  getWorkspaceFiles: async (memberId: number, sessionId: string) => {
    return api
      .get<{ files: WorkspaceArtifactFile[] }>('/chat_window/workspace_files', {
        params: { member_id: memberId, session_id: sessionId },
      })
      .then((res) => res.data.files);
  },
};

export const sessionsApi = {
  list: (memberId: number) =>
    api
      .get<ChatSession[]>('/sessions', {
        params: { member_id: memberId, session_type: 'group_chat' },
      })
      .then((res) => res.data),
  getMessages: (sessionId: string, memberId: number) =>
    api
      .get<SessionMessage[]>(`/sessions/${sessionId}/messages`, {
        params: { member_id: memberId },
      })
      .then((res) => res.data),
};

export default api;
