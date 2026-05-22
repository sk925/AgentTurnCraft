"""删除会话：agent_log、chat_session、LangGraph checkpoint、Redis 轮次缓存与会话工作空间。"""

from __future__ import annotations

import logging
import shutil
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.chat.base.models.agent_log import AgentLog
from app.chat.group.event_publisher import EventPublisher
from app.chat.session.models import ChatSession
from app.chat.session.service import get_session
from app.config import _BACKEND_ROOT

logger = logging.getLogger(__name__)


def _collect_checkpoint_thread_ids(db: Session, session_id: str) -> list[str]:
    """主图 thread_id=session_id；发言人子图 thread_id=session_id_{speaker_id}。"""
    sid = str(session_id)
    thread_ids = [sid]
    rows = (
        db.query(AgentLog.speaker_id)
        .filter(AgentLog.session_id == sid, AgentLog.speaker_id.isnot(None))
        .distinct()
        .all()
    )
    for (speaker_id,) in rows:
        if speaker_id is not None:
            thread_ids.append(f"{sid}_{int(speaker_id)}")
    return list(dict.fromkeys(thread_ids))


def _collect_round_ids(db: Session, session_id: str) -> list[str]:
    sid = str(session_id)
    rows = db.query(AgentLog.round_id).filter(AgentLog.session_id == sid).distinct().all()
    return list(dict.fromkeys(str(r[0]) for r in rows if r[0]))


def delete_session_records(db: Session, session_id: str, member_id: int) -> tuple[list[str], list[str]]:
    """删除 DB 中的会话与聊天记录，返回待清理的 checkpoint thread_id 与 round_id。"""
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.member_id != member_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该会话")

    thread_ids = _collect_checkpoint_thread_ids(db, session_id)
    round_ids = _collect_round_ids(db, session_id)

    sid = str(session_id)
    db.query(AgentLog).filter(AgentLog.session_id == sid).delete(synchronize_session=False)
    db.delete(session)
    db.commit()
    return thread_ids, round_ids


def purge_session_workspace(member_id: int, session_id: str) -> None:
    """删除宿主机会话工作空间目录，并释放该会话的 Docker 沙箱容器（若存在）。"""
    workspace_dir = (_BACKEND_ROOT / "workspace" / str(member_id) / str(session_id)).resolve()
    artifact_root = _BACKEND_ROOT / "workspace"
    try:
        workspace_dir.relative_to(artifact_root.resolve())
    except ValueError:
        logger.error("拒绝删除非法工作空间路径: %s", workspace_dir)
        return

    if workspace_dir.is_dir():
        shutil.rmtree(workspace_dir)
        logger.info("已删除会话工作空间: %s", workspace_dir)

    try:
        from app.sandbox import get_sandbox_manager

        get_sandbox_manager().release_session(member_id, session_id)
    except Exception:
        logger.warning(
            "释放会话沙箱容器失败 session_id=%s member_id=%s",
            session_id,
            member_id,
            exc_info=True,
        )


async def purge_session_runtime_state(
    checkpointer: Any,
    session_id: str,
    thread_ids: list[str],
    round_ids: list[str],
) -> None:
    """删除 LangGraph Postgres checkpoint 中对应 thread，并清理 Redis 轮次键。"""
    for thread_id in thread_ids:
        await checkpointer.adelete_thread(thread_id)

    publisher = EventPublisher()
    await publisher.clear_active_round(str(session_id))
    for round_id in round_ids:
        redis = publisher.redis
        await redis.delete(f"chat:{session_id}:{round_id}:events")
        await redis.delete(f"chat:{session_id}:{round_id}:status")
