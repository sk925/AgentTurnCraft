from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.authz import user_has_permission
from app.converters import permission_out
from app.database import get_db
from app.deps import get_current_user
from app.models import Permission, User
from app.schemas import PermissionCreate, PermissionOut, PermissionUpdate

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("", response_model=list[PermissionOut])
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "permission:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 permission:read")
    perms = db.query(Permission).order_by(Permission.id).all()
    return [permission_out(p) for p in perms]


@router.get("/{permission_id}", response_model=PermissionOut)
def get_permission(
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "permission:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 permission:read")
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
    return permission_out(p)


@router.post("", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
def create_permission(
    body: PermissionCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "permission:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 permission:write")
    if db.query(Permission).filter(Permission.code == body.code).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="权限编码已存在")
    p = Permission(code=body.code, name=body.name, description=body.description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return permission_out(p)


@router.patch("/{permission_id}", response_model=PermissionOut)
def update_permission(
    permission_id: int,
    body: PermissionUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "permission:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 permission:write")
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
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
    current: Annotated[User, Depends(get_current_user)],
):
    if not user_has_permission(current, "permission:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 permission:write")
    p = db.get(Permission, permission_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="权限不存在")
    seeded = {"user:read", "user:write", "user:delete", "role:read", "role:write", "permission:read", "permission:write"}
    if p.code in seeded:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除内置系统权限")
    db.delete(p)
    db.commit()
