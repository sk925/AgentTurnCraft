import axios, { type AxiosError } from 'axios';
import type {
  ChatModelDto,
  ModelProviderDto,
  PermissionDto,
  RoleDto,
  TokenResponse,
  UserDto,
} from '../types';

export const TOKEN_KEY = 'user_service_token';

export const api = axios.create({
  baseURL: '/',
});

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

function expectApiOk<T>(env: ApiEnvelope<T>): T {
  if (env.code !== 0) {
    throw new Error(env.message || '请求失败');
  }
  return env.data as T;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string }>) => {
    const msg = error.response?.data?.message;
    if (msg) return Promise.reject(new Error(msg));
    return Promise.reject(error);
  },
);

export async function login(username: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/api/auth/login', {
    username,
    password,
  });
  return data;
}

export async function logout(): Promise<void> {
  await api.post('/api/auth/logout');
}

export async function fetchMe(): Promise<UserDto> {
  const { data } = await api.get<UserDto>('/api/users/me');
  return data;
}

export async function fetchUsers(): Promise<UserDto[]> {
  const { data } = await api.get<UserDto[]>('/api/users');
  return data;
}

export async function createUser(payload: {
  username: string;
  password: string;
  email?: string | null;
  is_active?: boolean;
  role_ids?: string[] | number[];
}): Promise<UserDto> {
  const { data } = await api.post<UserDto>('/api/users', payload);
  return data;
}

export async function updateUser(
  id: string,
  payload: Partial<{
    email: string | null;
    password: string;
    is_active: boolean;
    role_ids: string[] | number[];
  }>,
): Promise<UserDto> {
  const { data } = await api.patch<UserDto>(`/api/users/${encodeURIComponent(id)}`, payload);
  return data;
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/api/users/${encodeURIComponent(id)}`);
}

export async function fetchRoles(): Promise<RoleDto[]> {
  const { data } = await api.get<RoleDto[]>('/api/roles');
  return data;
}

export async function createRole(payload: {
  name: string;
  description?: string | null;
  permission_ids?: string[] | number[];
}): Promise<RoleDto> {
  const { data } = await api.post<RoleDto>('/api/roles', payload);
  return data;
}

export async function updateRole(
  id: string,
  payload: Partial<{ name: string; description: string | null; permission_ids: string[] | number[] }>,
): Promise<RoleDto> {
  const { data } = await api.patch<RoleDto>(`/api/roles/${encodeURIComponent(id)}`, payload);
  return data;
}

export async function deleteRole(id: string): Promise<void> {
  await api.delete(`/api/roles/${encodeURIComponent(id)}`);
}

export async function fetchPermissions(): Promise<PermissionDto[]> {
  const { data } = await api.get<PermissionDto[]>('/api/permissions');
  return data;
}

export async function createPermission(payload: {
  code: string;
  name: string;
  description?: string | null;
}): Promise<PermissionDto> {
  const { data } = await api.post<PermissionDto>('/api/permissions', payload);
  return data;
}

export async function updatePermission(
  id: string,
  payload: Partial<{ name: string; description: string | null }>,
): Promise<PermissionDto> {
  const { data } = await api.patch<PermissionDto>(`/api/permissions/${encodeURIComponent(id)}`, payload);
  return data;
}

export async function deletePermission(id: string): Promise<void> {
  await api.delete(`/api/permissions/${encodeURIComponent(id)}`);
}

export async function fetchModelProviders(): Promise<ModelProviderDto[]> {
  const { data } = await api.get<ApiEnvelope<ModelProviderDto[]>>('/api/model-manage/model-providers');
  return expectApiOk(data);
}

export async function fetchModelProvider(id: string): Promise<ModelProviderDto> {
  const { data } = await api.get<ApiEnvelope<ModelProviderDto>>(`/api/model-manage/model-provider/${encodeURIComponent(id)}`);
  return expectApiOk(data);
}

export async function createModelProvider(payload: {
  name: string;
  base_url: string;
  api_key: string;
}): Promise<ModelProviderDto> {
  const { data } = await api.post<ApiEnvelope<ModelProviderDto>>('/api/model-manage/model-provider', payload);
  return expectApiOk(data);
}

export async function updateModelProvider(payload: {
  id: string;
  name?: string | null;
  base_url?: string | null;
  api_key?: string | null;
}): Promise<ModelProviderDto> {
  const { data } = await api.patch<ApiEnvelope<ModelProviderDto>>('/api/model-manage/model-provider', payload);
  return expectApiOk(data);
}

export async function deleteModelProvider(id: string): Promise<void> {
  const { data } = await api.delete<ApiEnvelope<null>>(`/api/model-manage/model-provider/${encodeURIComponent(id)}`);
  expectApiOk(data);
}

export async function fetchChatModels(providerId: string): Promise<ChatModelDto[]> {
  const { data } = await api.get<ApiEnvelope<ChatModelDto[]>>('/api/model-manage/chat-models', {
    params: { provider_id: providerId },
  });
  return expectApiOk(data);
}

export async function createChatModel(payload: {
  name: string;
  provider_id: string;
  model_type: string;
  description?: string | null;
}): Promise<ChatModelDto> {
  const { data } = await api.post<ApiEnvelope<ChatModelDto>>('/api/model-manage/chat-model', payload);
  return expectApiOk(data);
}

export async function updateChatModel(payload: {
  id: string;
  name?: string | null;
  provider_id?: string | null;
  model_type?: string | null;
  description?: string | null;
}): Promise<ChatModelDto> {
  const { data } = await api.patch<ApiEnvelope<ChatModelDto>>('/api/model-manage/chat-model', payload);
  return expectApiOk(data);
}

export async function deleteChatModel(id: string): Promise<void> {
  const { data } = await api.delete<ApiEnvelope<null>>(`/api/model-manage/chat-model/${encodeURIComponent(id)}`);
  expectApiOk(data);
}
