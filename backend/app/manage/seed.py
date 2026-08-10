from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import RESOURCE_TYPE_BUILTIN
from app.enums import PermissionMenu
from app.manage.models import Permission, Role, User
from app.manage.security import hash_password


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
            db.add(Permission(code=code, name=name, permission_type=RESOURCE_TYPE_BUILTIN))

    db.commit()

    _ensure_menu_permissions(db)
    _ensure_chat_menu_roles(db)

    admin_role_name = "admin"
    if db.scalar(select(Role.id).where(Role.name == admin_role_name)) is None:
        all_perm = db.scalars(select(Permission)).all()
        admin_role = Role(
            name=admin_role_name,
            description="系统管理员",
            role_type=RESOURCE_TYPE_BUILTIN,
        )
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

    _sync_admin_role_permissions(db)


def _ensure_menu_permissions(db: Session) -> None:
    """补全侧边栏菜单对应权限行（code 与 PermissionMenu 成员名一致），并刷新 admin 角色关联。"""
    for menu in PermissionMenu:
        code = menu.name
        display = menu.value
        if db.scalar(select(Permission.id).where(Permission.code == code)) is None:
            db.add(
                Permission(
                    code=code,
                    name=display,
                    description=None,
                    permission_type=RESOURCE_TYPE_BUILTIN,
                )
            )
    db.commit()
    _sync_admin_role_permissions(db)


# 对话类菜单：角色名与 permission.code 一致（chat / group_chat / image_chat）
_CHAT_MENU_ROLE_CODES = ("chat", "group_chat", "image_chat")


def _ensure_chat_menu_roles(db: Session) -> None:
    """补全对话类菜单角色；已有 chat 角色的用户自动获得新增的 image_chat 角色。"""
    for code in _CHAT_MENU_ROLE_CODES:
        perm = db.scalar(select(Permission).where(Permission.code == code))
        if perm is None:
            continue
        role = db.scalars(
            select(Role).where(Role.name == code).options(selectinload(Role.permissions))
        ).one_or_none()
        if role is None:
            menu = next((m for m in PermissionMenu if m.name == code), None)
            role = Role(
                name=code,
                description=menu.value if menu else code,
                role_type=RESOURCE_TYPE_BUILTIN,
                permissions=[perm],
            )
            db.add(role)
        else:
            have_ids = {p.id for p in role.permissions}
            if perm.id not in have_ids:
                role.permissions = list(role.permissions) + [perm]
    db.commit()

    image_role = db.scalars(select(Role).where(Role.name == "image_chat")).one_or_none()
    if image_role is None:
        return

    # 已有「对话」角色的用户自动获得「文生图」，避免新菜单因缺权被侧栏隐藏
    chat_users = (
        db.scalars(
            select(User)
            .join(User.roles)
            .where(Role.name == "chat")
            .options(selectinload(User.roles))
        )
        .unique()
        .all()
    )
    changed = False
    for user in chat_users:
        if any(r.name == "image_chat" for r in user.roles):
            continue
        user.roles = list(user.roles) + [image_role]
        changed = True
    if changed:
        db.commit()


def _sync_admin_role_permissions(db: Session) -> None:
    """admin 角色始终关联当前库中全部权限（补首次种子后新增权限、或历史库漏关联）。"""
    admin_role = (
        db.scalars(select(Role).where(Role.name == "admin").options(selectinload(Role.permissions)))
        .one_or_none()
    )
    if admin_role is None:
        return
    all_perm = list(db.scalars(select(Permission)).all())
    if not all_perm:
        return
    have = {p.id for p in admin_role.permissions}
    need = {p.id for p in all_perm}
    if have == need:
        return
    admin_role.permissions = all_perm
    db.commit()
