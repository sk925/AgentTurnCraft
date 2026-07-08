"""面向移动端 / 第三方应用的免登录单聊 HTTP 接口。"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.chat.base.schemas import ApiResponse, success_response
from app.chat.orchestration import (
    build_window_state_for_session_type,
    execute_chat_round_for_session_type,
)
from app.chat.shared.chat_common import SessionType
from app.chat.shared.event_publisher import EventPublisher
from app.chat.shared.window_models import WindowChatRequest
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/open/chat", tags=["open-chat"])


class OpenSingleChatRequest(BaseModel):
    """免登录单聊请求体。"""

    message: str = Field(default="", description="用户消息；resume 时可留空")
    session_id: str | None = Field(default=None, description="多轮对话时回传上次返回的 session_id")
    agent_id: int | None = Field(default=None, description="可选，指定智能体 id；默认使用 DEFAULT_SINGLE_AGENT_ID")
    resume: dict[str, Any] | None = Field(default=None, description="人机中断后继续对话时传入")


class OpenSingleChatResponse(BaseModel):
    session_id: str
    round_id: str
    answer: str = ""
    interrupted: bool = False
    interrupt_data: Any | None = None


def _ensure_public_chat_enabled() -> None:
    if not settings.public_chat_enabled:
        raise HTTPException(status_code=404, detail="开放单聊接口未启用")


def _verify_public_chat_api_key(
    x_app_key: Annotated[str | None, Header(alias="X-App-Key")] = None,
) -> None:
    expected = (settings.public_chat_api_key or "").strip()
    if not expected:
        return
    provided = (x_app_key or "").strip()
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="无效的 X-App-Key")


def _extract_chat_result(events: list[dict[str, Any]]) -> OpenSingleChatResponse:
    answer_parts: list[str] = []
    final_answer = ""
    interrupted = False
    interrupt_data: Any | None = None
    error_message: str | None = None
    session_id = ""
    round_id = ""

    for ev in events:
        event_type = ev.get("event")
        if event_type == "start":
            session_id = str(ev.get("session_id") or session_id)
            round_id = str(ev.get("round_id") or round_id)
        elif event_type == "error":
            error_message = str(ev.get("message") or "对话失败")
        elif event_type == "speaker_model_stream":
            delta = ev.get("delta")
            if isinstance(delta, str) and delta:
                answer_parts.append(delta)
        elif event_type == "speaker":
            content = ev.get("content")
            if isinstance(content, str) and content.strip():
                final_answer = content
        elif event_type == "speaker_finished":
            final_answer = str(ev.get("answer") or final_answer)
        elif event_type == "main_interrupt":
            interrupted = True
            interrupt_data = ev.get("interrupt_data")

    if error_message:
        raise HTTPException(status_code=500, detail=error_message)

    answer = final_answer or "".join(answer_parts)
    return OpenSingleChatResponse(
        session_id=session_id,
        round_id=round_id,
        answer=answer,
        interrupted=interrupted,
        interrupt_data=interrupt_data,
    )


@router.post("/single", response_model=ApiResponse[OpenSingleChatResponse])
async def open_single_chat(
    body: OpenSingleChatRequest,
    request: Request,
    _: Annotated[None, Depends(_ensure_public_chat_enabled)],
    __: Annotated[None, Depends(_verify_public_chat_api_key)],
    db: Session = Depends(get_db),
):
    """免登录单聊：同步返回完整回复。多轮对话请携带 session_id。"""
    message = (body.message or "").strip()
    if not message and not body.resume:
        raise HTTPException(status_code=400, detail="message 不能为空")

    window_chat_request = WindowChatRequest(
        user_message=message,
        org_id=1,
        user_id=int(settings.public_chat_user_id),
        session_id=body.session_id,
        round_id=None,
        session_type=SessionType.CHAT,
        single_agent_id=str(body.agent_id) if body.agent_id is not None else None,
        resume=body.resume,
    )

    window_state, window_graph, config = build_window_state_for_session_type(
        window_chat_request, db, request.app.state.checkpointer
    )
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    publisher = EventPublisher()
    await publisher.set_active_round(session_id, round_id)
    await publisher.set_round_status(session_id, round_id, "running")

    try:
        await execute_chat_round_for_session_type(
            window_chat_request,
            window_graph,
            window_state,
            config,
            publisher,
        )
    except Exception as exc:
        logger.exception("open_single_chat failed session_id=%s", session_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await publisher.clear_active_round(session_id)

    events = await publisher.get_round_events(session_id, round_id)
    result = _extract_chat_result(events)
    if not result.session_id:
        result.session_id = session_id
    if not result.round_id:
        result.round_id = round_id
    return success_response(result)
