export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserDto {
  id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_ids: string[];
}

export interface RoleDto {
  id: string;
  name: string;
  description: string | null;
  permission_ids: string[];
  /** 1 内置 2 自定义 */
  role_type: number;
}

export interface PermissionDto {
  id: string;
  code: string;
  name: string;
  description: string | null;
  /** 1 内置 2 自定义 */
  permission_type: number;
}

/** 后端雪花 ID 以字符串返回，避免 JS Number 精度问题 */
export interface ModelProviderDto {
  id: string;
  name: string;
  base_url: string;
}

export interface ChatModelDto {
  id: string;
  name: string;
  provider_id: string;
  provider_name: string;
  model_type: string;
  description?: string | null;
}
