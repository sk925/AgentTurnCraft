export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserDto {
  id: number;
  username: string;
  email: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_ids: number[];
}

export interface RoleDto {
  id: number;
  name: string;
  description: string | null;
  permission_ids: number[];
}

export interface PermissionDto {
  id: number;
  code: string;
  name: string;
  description: string | null;
}
