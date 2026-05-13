import json
from typing import Annotated, Any

from app.auth import CurrentUser, get_current_user, get_current_user_optional
from app.config import settings
from app.group_chat.chat_common import MsgType, RoleType, SessionType
from app.models.agent_log import AgentLog
from app.models.upload_file import UploadFile
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ApiResponse, success_response
from app.session.schemas import ChatSessionMessageFileInfo, ChatSessionMessageResponse, ChatSessionResponse
from app.session.service import get_session, list_sessions

router = APIRouter(prefix="/sessions")


def _normalize_log_file_ids(raw: Any) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        if item is None:
            continue
        try:
            out.append(int(str(item).strip()))
        except (TypeError, ValueError):
            continue
    return out


def _build_user_file_info(db: Session, member_id: int, file_list_raw: Any) -> list[ChatSessionMessageFileInfo] | None:
    ids = _normalize_log_file_ids(file_list_raw)
    if not ids:
        return None
    rows = db.query(UploadFile).filter(UploadFile.id.in_(ids), UploadFile.user_id == member_id).all()
    by_id = {int(r.id): r for r in rows}
    infos: list[ChatSessionMessageFileInfo] = []
    for fid in ids:
        r = by_id.get(int(fid))
        if not r:
            continue
        file_url = f"{settings.minio_endpoint}/{settings.minio_bucket}/{r.file_path}"
        infos.append(
            ChatSessionMessageFileInfo(
                file_id=str(r.id),
                file_name=r.file_name,
                file_url=file_url,
                file_type=r.file_type or "",
            )
        )
    return infos if infos else None


def _agent_log_row_to_chat_message(row: AgentLog, db: Session, member_id: int) -> ChatSessionMessageResponse | None:
    """将 agent_log 一行转为会话消息；部分 agent_selector 按规则折叠为 assistant。"""
    role = row.role_type
    content = row.content or ""
    msg_type = row.message_type

    if role == RoleType.AGENT_SELECTOR.value:
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
        raw_selected = payload.get("selected_agent_ids")
        if raw_selected is None:
            selected_ids: list = []
        elif isinstance(raw_selected, list):
            selected_ids = raw_selected
        else:
            selected_ids = []
        if selected_ids:
            return None
        answer = payload.get("answer")
        answer_str = answer if isinstance(answer, str) else ("" if answer is None else str(answer))
        if not answer_str.strip():
            return None
        return ChatSessionMessageResponse(
            role_type=RoleType.ASSISTANT.value,
            message_type=msg_type,
            message_content=answer_str.strip(),
            speaker_id=row.speaker_id,
            speaker_name=row.speaker_name,
            file_info=None,
        )

    file_info = None
    if role == RoleType.USER.value:
        file_info = _build_user_file_info(db, member_id, row.file_list)

    return ChatSessionMessageResponse(
        role_type=role,
        message_type=msg_type,
        message_content=content,
        speaker_id=row.speaker_id,
        speaker_name=row.speaker_name,
        file_info=file_info,
    )


@router.get("", response_model=ApiResponse[list[ChatSessionResponse]])
def get_session_list(
    current_user: Annotated[CurrentUser | None, Depends(get_current_user_optional)],
    db: Session = Depends(get_db),
    session_type: SessionType | None = Query(None, description="会话类型"),
):
    """未登录时返回空列表；已登录返回当前用户的会话。"""
    if current_user is None:
        return success_response([])
    sessions = list_sessions(
        db=db,
        member_id=current_user.id,
        session_type=session_type.value if session_type else None,
    )
    return success_response(sessions)


@router.get("/{session_id}/messages", response_model=ApiResponse[list[ChatSessionMessageResponse]])
def get_session_messages(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    member_id = current_user.id
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.member_id != member_id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    rows = (
        db.query(AgentLog)
        .filter(
            AgentLog.session_id == str(session_id),
            AgentLog.user_id == session.member_id,
            AgentLog.role_type != RoleType.SPEAKER_SELECTOR.value,
            AgentLog.message_type != MsgType.TOOL_CALL.value,
        )
        .order_by(AgentLog.created_at.asc(), AgentLog.id.asc())
        .all()
    )
    filtered_messages: list[ChatSessionMessageResponse] = []
    for row in rows:
        msg = _agent_log_row_to_chat_message(row, db, session.member_id)
        if msg is not None:
            filtered_messages.append(msg)

    return success_response(filtered_messages)
