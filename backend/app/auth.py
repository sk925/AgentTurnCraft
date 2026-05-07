"""校验 user-service 签发的 JWT，与 user-service 的 HS256 + jwt_secret_key 一致。"""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """当前请求用户（来自 JWT）。"""

    id: int
    roles: tuple[str, ...]

    @property
    def is_admin(self) -> bool:
        return any(r.lower() == "admin" for r in self.roles)


def _decode_token(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if sub is None or sub == "":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌无效：缺少主体",
            )
        raw_roles = payload.get("roles")
        if raw_roles is None:
            roles: tuple[str, ...] = ()
        elif isinstance(raw_roles, str):
            roles = (raw_roles,)
        elif isinstance(raw_roles, list):
            roles = tuple(str(x) for x in raw_roles)
        else:
            roles = ()
        return CurrentUser(id=int(sub), roles=roles)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录",
        ) from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已损坏",
        ) from None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """解析 `Authorization: Bearer` 中的用户 id 与角色列表（`roles`  claim）。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录：请提供 Authorization Bearer 访问令牌",
        )
    return _decode_token(credentials.credentials)


async def get_current_user_id(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> int:
    """仅需要用户 id 的路由可继续依赖本函数。"""
    return current_user.id


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser | None:
    """有合法 Bearer 时解析用户；未携带或令牌无效时视为匿名（不抛 401）。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return _decode_token(credentials.credentials)
    except HTTPException:
        return None
