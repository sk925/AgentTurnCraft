"""校验 app.manage 签发的 JWT，并以数据库中的用户与角色为准（不信任 JWT 内嵌的 roles）。"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.manage.login_session import assert_user_login_session
from app.manage.rbac_api import load_manage_user

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """当前请求用户：id 与角色名均来自数据库（JWT + user_login 会话校验通过后加载）。"""

    id: int
    roles: tuple[str, ...]

    @property
    def is_admin(self) -> bool:
        return any(r.lower() == "admin" for r in self.roles)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """解析 Bearer 令牌后，从数据库加载活跃用户并返回其真实角色。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录：请提供 Authorization Bearer 访问令牌",
        )
    uid = assert_user_login_session(db, credentials.credentials)
    row = load_manage_user(db, uid)
    if row is None or not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )
    role_names = tuple(str(r.name) for r in (row.roles or []))
    return CurrentUser(id=int(row.id), roles=role_names)


async def get_current_user_id(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> int:
    """仅需要用户 id 的路由可继续依赖本函数。"""
    return current_user.id


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser | None:
    """有合法 Bearer 且数据库中用户存在且启用时返回用户；否则视为匿名。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        uid = assert_user_login_session(db, credentials.credentials)
    except HTTPException:
        return None
    row = load_manage_user(db, uid)
    if row is None or not row.is_active:
        return None
    role_names = tuple(str(r.name) for r in (row.roles or []))
    return CurrentUser(id=int(row.id), roles=role_names)
