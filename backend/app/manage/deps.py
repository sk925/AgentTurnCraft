from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.manage.authz import user_has_permission
from app.manage.login_session import assert_user_login_session
from app.manage.models import Role, User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_manage_user_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if creds is None:
        return None
    user_id = assert_user_login_session(db, creds.credentials)
    user = (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.id == user_id)
        .one_or_none()
    )
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def get_current_manage_user(
    user: Annotated[User | None, Depends(get_current_manage_user_optional)],
) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    return user


def require_manage_permission(code: str) -> Callable[..., User]:
    """依赖工厂：当前用户须具备指定权限编码（与路由里手写 `user_has_permission` 等价）。"""

    def _check(user: Annotated[User, Depends(get_current_manage_user)]) -> User:
        if not user_has_permission(user, code):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限 {code}",
            )
        return user

    return _check


def require_manage_roles(*role_names: str, require_all: bool = False) -> Callable[..., User]:
    """
    依赖工厂：按 **角色名**（`Role.name`）校验。

    - `require_all=False`（默认）：具备其中任意一个角色即可。
    - `require_all=True`：须同时具备所列全部角色。
    - 超级用户 `is_superuser` 直接通过。
    """

    wanted = {n.strip().lower() for n in role_names if n.strip()}
    if not wanted:
        raise ValueError("require_manage_roles 至少传入一个角色名")

    def _check(user: Annotated[User, Depends(get_current_manage_user)]) -> User:
        if user.is_superuser:
            return user
        have = {(r.name or "").lower() for r in (user.roles or [])}
        ok = wanted.issubset(have) if require_all else bool(wanted & have)
        if not ok:
            need = "且".join(sorted(wanted)) if require_all else "或".join(sorted(wanted))
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"需要角色（{'全部' if require_all else '任一'}）：{need}",
            )
        return user

    return _check
