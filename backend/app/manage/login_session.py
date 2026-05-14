"""user_login 会话：注册、校验、吊销、过期清理。"""

import hashlib
import time
from typing import Any

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.manage.models.user_login import UserLogin


def _sha256_hex(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def register_user_login_session(db: Session, raw_token: str, user_id: int) -> None:
    """登录成功后写入会话行（须在签发 JWT 之后调用）。"""
    payload: dict[str, Any] = jwt.decode(
        raw_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    sub = payload.get("sub")
    if sub is None or sub == "":
        raise ValueError("JWT 缺少 sub")
    if int(sub) != int(user_id):
        raise ValueError("JWT sub 与 user_id 不一致")
    h = _sha256_hex(raw_token)
    exp = int(payload["exp"])
    now = int(time.time())
    row = UserLogin(access_token_hash=h, user_id=int(user_id), expires_at=exp, created_at=now)
    db.add(row)
    db.commit()


def assert_user_login_session(db: Session, raw_token: str) -> int:
    """校验 JWT 且会话行存在；返回 user_id（sub）。否则 401。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            raw_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录",
        ) from None
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已损坏",
        ) from None

    sub = payload.get("sub")
    if sub is None or sub == "":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效：缺少主体",
        )
    uid = int(sub)
    h = _sha256_hex(raw_token)
    row = db.query(UserLogin).filter(UserLogin.access_token_hash == h).one_or_none()
    if row is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="会话已结束，请重新登录",
        )
    if int(row.user_id) != uid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="令牌与会话不一致",
        )
    now = int(time.time())
    if int(row.expires_at) < now:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="令牌已过期，请重新登录",
        )
    return uid


def revoke_user_login_session(db: Session, raw_token: str) -> int:
    """退出登录：删除当前令牌对应行。令牌无法解析时返回 0（幂等）。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            raw_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        sub = payload.get("sub")
        if sub is None or sub == "":
            return 0
        int(sub)
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        return 0
    h = _sha256_hex(raw_token)
    n = db.query(UserLogin).filter(UserLogin.access_token_hash == h).delete(synchronize_session=False)
    db.commit()
    return int(n)


def delete_expired_user_login_rows(db: Session) -> int:
    """清理已过期的会话行。"""
    now = int(time.time())
    n = db.query(UserLogin).filter(UserLogin.expires_at < now).delete(synchronize_session=False)
    db.commit()
    return int(n)
