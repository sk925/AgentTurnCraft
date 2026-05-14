from app.manage.models import Permission, Role, User
from app.manage.schemas.permission import PermissionOut
from app.manage.schemas.role import RoleOut
from app.manage.schemas.user import UserOut


def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        username=u.username,
        email=u.email,
        is_active=u.is_active,
        is_superuser=u.is_superuser,
        role_ids=[str(r.id) for r in u.roles],
    )


def role_out(r: Role) -> RoleOut:
    return RoleOut(
        id=str(r.id),
        name=r.name,
        description=r.description,
        role_type=r.role_type,
        permission_ids=[str(p.id) for p in r.permissions],
    )


def permission_out(p: Permission) -> PermissionOut:
    return PermissionOut(
        id=str(p.id),
        code=p.code,
        name=p.name,
        description=p.description,
        permission_type=p.permission_type,
    )
