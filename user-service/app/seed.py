from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission, Role, User
from app.security import hash_password


def seed_if_empty(db: Session) -> None:
    perms_defined = (
        ("user:read", "查看用户"),
        ("user:write", "创建/修改用户"),
        ("user:delete", "删除用户"),
        ("role:read", "查看角色"),
        ("role:write", "创建/修改角色"),
        ("permission:read", "查看权限"),
        ("permission:write", "创建/修改权限"),
    )
    if db.scalar(select(Permission.id).limit(1)) is None:
        for code, name in perms_defined:
            db.add(Permission(code=code, name=name))

    db.commit()

    admin_role_name = "admin"
    if db.scalar(select(Role.id).where(Role.name == admin_role_name)) is None:
        all_perm = db.scalars(select(Permission)).all()
        admin_role = Role(name=admin_role_name, description="系统管理员")
        admin_role.permissions = list(all_perm)
        db.add(admin_role)
        db.commit()

    if db.scalar(select(User.id).where(User.username == "admin")) is None:
        admin_role = db.scalars(select(Role).where(Role.name == admin_role_name)).one()
        u = User(
            username="admin",
            email="admin@localhost",
            hashed_password=hash_password("admin123"),
            is_active=True,
            is_superuser=True,
            roles=[admin_role],
        )
        db.add(u)
        db.commit()
