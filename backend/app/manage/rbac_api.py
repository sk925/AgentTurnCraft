"""与业务 API 共用的 RBAC 工具：从数据库加载用户（不信任 JWT 中的角色声明）。"""

from sqlalchemy.orm import Session, selectinload

from app.manage.models import Role, User


def load_manage_user(db: Session, user_id: int) -> User | None:
    """按主键加载用户（含角色与权限），用于鉴权。"""
    return (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.id == user_id)
        .one_or_none()
    )


def is_db_privileged_user(user: User) -> bool:
    """是否可将资源标为内置：超级用户或拥有 admin 角色（以数据库为准）。"""
    if user.is_superuser:
        return True
    return any((r.name or "").lower() == "admin" for r in (user.roles or []))
