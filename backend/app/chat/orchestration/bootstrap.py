"""轮次 bootstrap：与 session 类型无关的共用步骤。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chat.base.models.agent_log import AgentLogService
from app.chat.base.models.upload_file import UploadFile as UploadFileModel
from app.chat.orchestration.window_request import WindowChatRequest
from app.chat.session.service import get_or_create_session
from app.utils import snowflake


@dataclass(frozen=True)
class RoundBootstrap:
    session_id: str
    round_id: str
    file_ids: list[int]
    attachment_context: str
    effective_user_message: str
    raw_user_message: str


def build_attachment_context(db: Session, member_id: int, file_ids: list[int]) -> str:
    """按 id 拉取当前用户可见的上传文件元数据，供发言人 prompt 使用（不含文件正文）。"""
    if not file_ids:
        return ""
    rows = (
        db.query(UploadFileModel)
        .filter(UploadFileModel.id.in_(file_ids), UploadFileModel.user_id == member_id)
        .all()
    )
    if not rows:
        return ""
    by_id = {int(r.id): r for r in rows}
    lines = [
        "## 本轮用户附件（仅元数据；正文请通过工具按 file_id 读取）",
    ]
    for fid in file_ids:
        r = by_id.get(int(fid))
        if r:
            lines.append(
                f"- file_id: {r.id}\n  file_name: {r.file_name}\n  file_type: {r.file_type}\n  file_size: {r.file_size} bytes"
            )
    return "\n".join(lines)


def bootstrap_round(
    window_chat_request: WindowChatRequest,
    db: Session,
) -> RoundBootstrap:
    """会话落库、round_id、附件与有效用户文案。"""
    session_id = window_chat_request.session_id
    if not session_id:
        session_id = str(snowflake.get_snowflake_id())

    file_ids = list(window_chat_request.file_ids or [])
    attachment_context = build_attachment_context(db, window_chat_request.user_id, file_ids) if file_ids else ""

    raw_user_message = (window_chat_request.user_message or "").strip()
    effective_user_message = raw_user_message
    if not effective_user_message and file_ids:
        effective_user_message = "请根据我上传的附件处理。"

    get_or_create_session(
        db=db,
        session_id=session_id,
        member_id=window_chat_request.user_id,
        user_message=raw_user_message or effective_user_message,
        session_type=window_chat_request.session_type.value,
    )
    round_id = window_chat_request.round_id
    if not round_id:
        round_id = str(snowflake.get_snowflake_id())

    AgentLogService.save_user_question(
        user_id=window_chat_request.user_id,
        session_id=session_id,
        round_id=str(round_id),
        content=raw_user_message,
        file_ids=file_ids if file_ids else None,
    )

    return RoundBootstrap(
        session_id=session_id,
        round_id=str(round_id),
        file_ids=file_ids,
        attachment_context=attachment_context,
        effective_user_message=effective_user_message,
        raw_user_message=raw_user_message,
    )
