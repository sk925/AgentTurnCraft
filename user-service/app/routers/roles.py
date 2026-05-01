from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.authz import user_has_permission
from app.converters import role_out
from app.database import get_db
from app.deps import get_current_user
from app.models import Permission, Role, User
from app.schemas import RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/roles", tags=["roles"])


def _load_role(db: Session, role_id: int) -> Role | None:
    return (
        db.query(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.id == role_id)
        .one_or_none()
    )


@router.get("", response_model=list[RoleOut])
def list_roles(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "role:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 role:read")
    roles = db.query(Role).options(selectinload(Role.permissions)).all()
    return [role_out(r) for r in roles]


@router.get("/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "role:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 role:read")
    r = _load_role(db, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return role_out(r)


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "role:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 role:write")
    if db.query(Role).filter(Role.name == body.name).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="角色名称已存在")
    perms: list[Permission] = []
    if body.permission_ids:
        perms = db.query(Permission).filter(Permission.id.in_(body.permission_ids)).all()
        if len(perms) != len(set(body.permission_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="包含无效的权限 ID")
    r = Role(name=body.name, description=body.description, permissions=perms)
    db.add(r)
    db.commit()
    db.refresh(r)
    rr = _load_role(db, r.id)
    assert rr is not None
    return role_out(rr)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    body: RoleUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "role:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 role:write")
    r = db.query(Role).options(selectinload(Role.permissions)).filter(Role.id == role_id).one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="角色不存在")
    if r.name == "admin" and body.name not in (None, "admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="内置 admin 角色不可改名")
    if body.name is not None:
        hit = db.query(Role).filter(Role.name == body.name).one_or_none()
        if hit is not None and hit.id != r.id:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="角色名称已存在")
        r.name = body.name
    if body.description is not None:
        r.description = body.description
    if body.permission_ids is not None:
        perms = db.query(Permission).filter(Permission.id.in_(body.permission_ids)).all()
        if len(perms) != len(set(body.permission_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="包含无效的权限 ID")
        r.permissions = perms
    db.commit()
    rr = _load_role(db, role_id)
    assert rr is not None
    return role_out(rr)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "role:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 role:write")
    r = db.get(Role, role_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="角色不存在")
    if r.name == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除内置 admin 角色")
    db.delete(r)
    db.commit()
