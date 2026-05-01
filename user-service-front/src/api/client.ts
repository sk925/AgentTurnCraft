import axios from 'axios';
import type {
  PermissionDto,
  RoleDto,
  TokenResponse,
  UserDto,
} from '../types';

export const TOKEN_KEY = 'user_service_token';

export const api = axios.create({
  baseURL: '/',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function login(username: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/api/auth/login', {
    username,
    password,
  });
  return data;
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
  role_ids?: number[];
}): Promise<UserDto> {
  const { data } = await api.post<UserDto>('/api/users', payload);
  return data;
}

export async function updateUser(
  id: number,
  payload: Partial<{
    email: string | null;
    password: string;
    is_active: boolean;
    role_ids: number[];
  }>,
): Promise<UserDto> {
  const { data } = await api.patch<UserDto>(`/api/users/${id}`, payload);
  return data;
}

export async function deleteUser(id: number): Promise<void> {
  await api.delete(`/api/users/${id}`);
}

export async function fetchRoles(): Promise<RoleDto[]> {
  const { data } = await api.get<RoleDto[]>('/api/roles');
  return data;
}

export async function createRole(payload: {
  name: string;
  description?: string | null;
  permission_ids?: number[];
}): Promise<RoleDto> {
  const { data } = await api.post<RoleDto>('/api/roles', payload);
  return data;
}

export async function updateRole(
  id: number,
  payload: Partial<{ name: string; description: string | null; permission_ids: number[] }>,
): Promise<RoleDto> {
  const { data } = await api.patch<RoleDto>(`/api/roles/${id}`, payload);
  return data;
}

export async function deleteRole(id: number): Promise<void> {
  await api.delete(`/api/roles/${id}`);
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
  id: number,
  payload: Partial<{ name: string; description: string | null }>,
): Promise<PermissionDto> {
  const { data } = await api.patch<PermissionDto>(`/api/permissions/${id}`, payload);
  return data;
}

export async function deletePermission(id: number): Promise<void> {
  await api.delete(`/api/permissions/${id}`);
}
