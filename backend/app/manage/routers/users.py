from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.manage.authz import user_has_permission
from app.manage.converters import user_out
from app.manage.deps import get_current_manage_user
from app.manage.models import Role, User
from app.manage.schemas import UserCreate, UserOut, UserUpdate
from app.manage.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _load_user(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.id == user_id)
        .one_or_none()
    )


@router.get("", response_model=list[UserOut])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_manage_user)],
):
    if not user_has_permission(current, "user:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 user:read")
    users = db.query(User).options(selectinload(User.roles)).all()
    return [user_out(u) for u in users]


@router.get("/me", response_model=UserOut)
def me(current: Annotated[User, Depends(get_current_manage_user)]):
    return user_out(current)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_manage_user)],
):
    if current.id != user_id and not user_has_permission(current, "user:read"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 user:read")
    u = _load_user(db, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user_out(u)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_manage_user)],
):
    if not user_has_permission(current, "user:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 user:write")
    if db.query(User).filter(User.username == body.username).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="用户名已存在")
    roles: list[Role] = []
    if body.role_ids:
        roles = db.query(Role).filter(Role.id.in_(body.role_ids)).all()
        if len(roles) != len(set(body.role_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="包含无效的角色 ID")
    u = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        is_active=body.is_active,
        is_superuser=False,
        roles=roles,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    u = _load_user(db, u.id)
    assert u is not None
    return user_out(u)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_manage_user)],
):
    if current.id != user_id and not user_has_permission(current, "user:write"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 user:write")
    u = db.query(User).options(selectinload(User.roles)).filter(User.id == user_id).one_or_none()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if u.is_superuser and current.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="不能修改其他超级用户账户")
    if body.email is not None:
        u.email = body.email
    if body.password is not None:
        u.hashed_password = hash_password(body.password)
    if body.is_active is not None:
        if u.is_superuser and not body.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能禁用超级用户")
        u.is_active = body.is_active
    if body.role_ids is not None:
        if not user_has_permission(current, "user:write"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="仅有管理员可变更角色绑定")
        roles = db.query(Role).filter(Role.id.in_(body.role_ids)).all()
        if len(roles) != len(set(body.role_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="包含无效的角色 ID")
        u.roles = roles
    db.commit()
    u2 = _load_user(db, user_id)
    assert u2 is not None
    return user_out(u2)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(get_current_manage_user)],
):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if current.id == user_id:
        db.delete(u)
        db.commit()
        return
    if not user_has_permission(current, "user:delete"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="缺少权限 user:delete")
    if u.is_superuser and not current.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="仅超级管理员可删除其他超级用户账户")
    db.delete(u)
    db.commit()
