from app.models import Permission, Role, User
from app.schemas.permission import PermissionOut
from app.schemas.role import RoleOut
from app.schemas.user import UserOut


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        is_active=u.is_active,
        is_superuser=u.is_superuser,
        role_ids=[r.id for r in u.roles],
    )


def role_out(r: Role) -> RoleOut:
    return RoleOut(
        id=r.id,
        name=r.name,
        description=r.description,
        permission_ids=[p.id for p in r.permissions],
    )


def permission_out(p: Permission) -> PermissionOut:
    return PermissionOut(id=p.id, code=p.code, name=p.name, description=p.description)
