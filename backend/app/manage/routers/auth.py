from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.manage.login_session import register_user_login_session, revoke_user_login_session
from app.manage.models import User
from app.manage.schemas import LoginRequest, TokenResponse
from app.manage.security import create_access_token, verify_password

router = APIRouter()
_logout_bearer = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.username == body.username)
        .one_or_none()
    )
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账户已禁用")
    token = create_access_token(str(user.id))
    register_user_login_session(db, token, user.id)
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_logout_bearer)],
    db: Session = Depends(get_db),
):
    """退出登录：吊销当前 access_token（删除 user_login 对应行）。"""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="未提供访问令牌")
    revoke_user_login_session(db, creds.credentials)
    return {"message": "已退出登录"}
