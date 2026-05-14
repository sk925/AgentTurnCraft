from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.enums import PermissionMenu
from app.manage.converters import permission_out
from app.manage.deps import get_current_manage_user, require_manage_permission
from app.manage.models import Permission, Role, User
from app.manage.schemas import PermissionCreate, PermissionMineOut, PermissionOut, PermissionUpdate

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me", response_model=PermissionMineOut)
def get_my_permission_codes(
    user: Annotated[User, Depends(get_current_manage_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """当前登录用户拥有的权限编码列表（含菜单与其它），用于前端侧栏等。"""
    u = (
        db.query(User)
        .options(joinedload(User.roles).joinedload(Role.permissions))
        .filter(User.id == user.id)
        .one()
    )
    codes: set[str] = set()
    if u.is_superuser:
        codes.update(m.name for m in PermissionMenu)
    for role in u.roles:
        for p in role.permissions:
            codes.add(p.code)
    return PermissionMineOut(codes=sorted(codes))


@router.get("", response_model=list[PermissionOut])
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_manage_permission("permission:read"))],
):
    perms = db.query(Permission).order_by(Permission.id).all()
    return [permission_out(p) for p in perms]


@router.get("/{permission_id}", response_model=PermissionOut)
def get_permission(
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_manage_permission("permission:read"))],
):
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
    return permission_out(p)


@router.post("", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
def create_permission(
    body: PermissionCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_manage_permission("permission:write"))],
):
    if db.query(Permission).filter(Permission.code == body.code).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="权限编码已存在")
    p = Permission(
        code=body.code,
        name=body.name,
        description=body.description,
        permission_type=RESOURCE_TYPE_CUSTOM,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return permission_out(p)


@router.patch("/{permission_id}", response_model=PermissionOut)
def update_permission(
    permission_id: int,
    body: PermissionUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_manage_permission("permission:write"))],
):
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
    if p.permission_type == RESOURCE_TYPE_BUILTIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能修改内置权限")
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    db.commit()
    db.refresh(p)
    return permission_out(p)


@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_manage_permission("permission:write"))],
):
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
    if p.permission_type == RESOURCE_TYPE_BUILTIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除内置权限")
    db.delete(p)
    db.commit()
