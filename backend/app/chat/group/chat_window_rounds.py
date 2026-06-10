"""
按 session_type 拆分的「构建状态 + 执行 LangGraph」逻辑。

WebSocket / HTTP 路由里的事件订阅、Redis 转发、鉴权等仍放在 app.chat.chat_router；
此处仅负责：不同会话类型使用不同的 window_state / 编译图 / astream 事件映射。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.chat.single.single_chat import ChatRountInfo, chat_with_single_agent
from fastapi import HTTPException
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.constants import RESOURCE_TYPE_BUILTIN
from app.chat.group.chat_common import SessionType, SpearkerRecord, WindowState
from app.chat.group.chat_graph import get_chat_window_graph, get_window_graph
from app.chat.group.event_publisher import EventPublisher
from app.chat.group.window_chat_models import WindowChatRequest, normalize_window_file_ids
from app.chat.base.models import Agent, Group
from app.chat.base.models.upload_file import UploadFile as UploadFileModel
from app.chat.base.models.agent_log import AgentLogService
from app.chat.session.service import get_or_create_session
from app.utils import snowflake

logger = logging.getLogger(__name__)


def _build_attachment_context(db: Session, member_id: int, file_ids: list[int]) -> str:
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


@dataclass(frozen=True)
class _RoundBootstrap:
    session_id: str
    round_id: int
    file_ids: list[int]
    attachment_context: str
    effective_user_message: str
    raw_user_message: str


def _bootstrap_round(
    window_chat_request: WindowChatRequest,
    db: Session,
) -> _RoundBootstrap:
    """会话落库、round_id、附件与有效用户文案（与群聊/单聊无关的共用步骤）。"""
    session_id = window_chat_request.session_id
    if not session_id:
        session_id = str(snowflake.get_snowflake_id())

    file_ids = normalize_window_file_ids(window_chat_request.file_ids)
    attachment_context = _build_attachment_context(db, window_chat_request.user_id, file_ids) if file_ids else ""

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

    return _RoundBootstrap(
        session_id=session_id,
        round_id=round_id,
        file_ids=file_ids,
        attachment_context=attachment_context,
        effective_user_message=effective_user_message,
        raw_user_message=raw_user_message,
    )


def _agents_for_group_request(
    window_chat_request: WindowChatRequest,
    member_id: int,
    db: Session,
) -> list[Agent]:
    """群聊：指定群组内智能体；未指定 group_id 时退回为「当前用户可见 + 内置」智能体池。"""
    if window_chat_request.session_type == SessionType.GROUP_CHAT and window_chat_request.group_id is not None:
        group = db.query(Group).filter(Group.id == window_chat_request.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="群组不存在")
        if group.resource_type != RESOURCE_TYPE_BUILTIN and group.user_id != member_id:
            raise HTTPException(status_code=404, detail="群组不存在")
        all_agents = list(group.agents or [])
        if not all_agents:
            raise HTTPException(status_code=400, detail="该群组下暂无智能体，请先在群组管理中添加成员")
        return all_agents
    return (
        db.query(Agent)
        .filter(
            or_(Agent.user_id == member_id, Agent.resource_type == RESOURCE_TYPE_BUILTIN),
        )
        .all()
    )


def _agents_for_single_chat(member_id: int, db: Session) -> list[Agent]:
    """普通对话：当前用户自建 + 内置智能体。"""
    return (
        db.query(Agent)
        .filter(
            or_(Agent.user_id == member_id, Agent.resource_type == RESOURCE_TYPE_BUILTIN),
        )
        .all()
    )


def _agents_to_state_payload(all_agents: list[Agent]) -> list[dict]:
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "prompt": agent.prompt,
            "chat_model_id": agent.chat_model_id,
        }
        for agent in all_agents
    ]


def build_window_state_and_config(window_chat_request: WindowChatRequest,db: Session) -> WindowState:
    """构建窗口状态和配置"""
    member_id = window_chat_request.user_id
    b = _bootstrap_round(window_chat_request, db)
    all_agents = _agents_for_group_request(window_chat_request, member_id, db)
    all_agents_data = _agents_to_state_payload(all_agents)

    window_state: WindowState = {
        "session_id": b.session_id,
        "round_id": b.round_id,
        "user_message": b.effective_user_message,
        "file_ids": b.file_ids,
        "attachment_context": b.attachment_context,
        "member_id": member_id,
        "all_agents": all_agents_data,
        "user_profile": {"member_id": member_id, "org_id": window_chat_request.org_id, "member_role": "STUDENT"},
        # 同 session 复用 checkpoint thread；新轮次 input 须显式覆盖，否则沿用上一轮 interrupt 残留
        "question_data": {},
        "user_input": {},
    }
    config = {"configurable": {"thread_id": b.session_id}}
    return window_state, config

def build_group_window_state(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> tuple[WindowState, CompiledStateGraph, dict]:
    """群聊（含 session_type=group 且未带 group_id 时的退化池）。"""
    if window_chat_request.session_type != SessionType.GROUP_CHAT:
        raise HTTPException(status_code=400, detail="会话类型不是群聊")

    window_state, config = build_window_state_and_config(window_chat_request, db)
    window_graph = get_window_graph(checkpointer)
    return window_state, window_graph, config

def build_single_window_state(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> tuple[WindowState, CompiledStateGraph, dict]:
    """普通单聊。"""
    window_state, config = build_window_state_and_config(window_chat_request, db)
    return window_state, None, config


def build_window_state_for_session_type(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> tuple[WindowState, CompiledStateGraph, dict]:
    """供 HTTP / WebSocket 统一入口调用。"""
    if window_chat_request.session_type == SessionType.GROUP_CHAT:
        return build_group_window_state(window_chat_request, db, checkpointer)

    return build_single_window_state(window_chat_request, db, checkpointer)


# ---------- 群聊：节点 updates → Redis 事件 ----------


def _build_select_agents_payload(data: dict) -> dict | None:
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    return {
        "event": "create_group",
        "group_members": [
            {"id": agent["id"], "name": agent["name"]}
            for agent in data.get("group_members", [])
        ],
        "select_reason": data.get("select_reason", ""),
    }


def _build_select_speaker_payload(data: dict) -> dict | None:
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    payload = dict(data)
    payload.pop("session_messages", None)
    payload["event"] = "select_speaker"
    return payload


def _build_speaker_payload(data: dict) -> dict | None:
    transcript: list[SpearkerRecord] = data.get("transcript", [])
    if transcript:
        record = transcript[-1]
        record["event"] = "speaker"
        return record
    return None


async def execute_group_chat_round(
    window_chat_request: WindowChatRequest,
    window_graph: CompiledStateGraph,
    window_state: dict,
    config: dict,
    publisher: EventPublisher,
) -> None:
    """群聊 LangGraph：astream 映射为现有前端事件（create_group / select_speaker / speaker / …）。"""
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "start",
            "session_id": session_id,
            "round_id": round_id,
        },
    )
    
    stream_input = window_state
    if window_chat_request.resume:
        stream_input = Command(resume=window_chat_request.resume)
    round_failed = False
    try:
        
        async for chunk in window_graph.astream(
            stream_input, 
            config=config, 
            stream_mode=["messages", "updates", "custom"]
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                mode, data = chunk
            elif isinstance(chunk, tuple) and len(chunk) == 3:
                _, mode, data = chunk
            else:
                continue

            if mode == "updates":
                if data.get("select_agents_node"):
                    agents_data = data["select_agents_node"]
                    payload = _build_select_agents_payload(agents_data)
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                    group_members = agents_data.get("group_members", [])
                    if group_members and len(group_members) == 1:
                        await publisher.publish(session_id, round_id, {
                            "event": "select_speaker",
                            "current_speaker": group_members[0],
                        })
                    
                    
                if data.get("select_speaker_node"):
                    payload = _build_select_speaker_payload(data["select_speaker_node"])
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                if data.get("speak_node"):
                    speak_data = data["speak_node"]
                    payload = _build_speaker_payload(speak_data)
                    
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                    if speak_data.get("finished", False):
                        await publisher.publish(
                            session_id,
                            round_id,
                            {
                                "event": "speaker_finished",
                                "answer": speak_data.get("answer", ""),
                                "finish_reason": speak_data.get("finish_reason", "")
                            },
                        )
                       
                if isinstance(data, dict) and data.get("__interrupt__"):
                    await publisher.publish(session_id, round_id, {
                        "event": "main_interrupt",
                        "interrupt_data": data.get("__interrupt__")[0].value,
                    })
            elif mode == "custom":
                await publisher.publish(session_id, round_id, data)
            elif mode == "messages":
                if not isinstance(data, tuple) or len(data) < 2:
                    continue
                meta = data[1]
                if not isinstance(meta, dict):
                    continue
                langgraph_node = meta.get("langgraph_node", "")
                if langgraph_node in ["select_agents_node", "select_speaker_node"]:
                    continue

    except Exception as e:
        round_failed = True
        logger.exception(
            "LangGraph 群聊轮次失败 session_id=%s round_id=%s",
            session_id,
            round_id,
        )
        await publisher.publish(
            session_id,
            round_id,
            {
                "event": "error",
                "message": getattr(e, "message", None) or str(e),
            },
        )
        raise
    finally:
        await publisher.set_round_status(session_id, round_id, "failed" if round_failed else "completed")
        await publisher.clear_active_round(session_id)


async def execute_single_chat_round(
    window_chat_request: WindowChatRequest,
    window_graph: CompiledStateGraph,
    window_state: dict,
    config: dict,
    publisher: EventPublisher,
) -> None:
    """普通单聊：委托 single_chat，经 Redis 下发 start / 流式 / speaker_finished。"""
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "start",
            "session_id": session_id,
            "round_id": round_id,
        },
    )

    single_agent_id: int | None = None
    if window_chat_request.single_agent_id is not None:
        try:
            single_agent_id = int(str(window_chat_request.single_agent_id).strip())
        except (TypeError, ValueError):
            single_agent_id = None

    chat_round_info = ChatRountInfo(
        user_id=window_chat_request.user_id,
        session_id=session_id,
        round_id=round_id,
        user_message=window_state["user_message"],
        agent_id=single_agent_id,
        file_ids=window_state.get("file_ids") or [],
        attachment_context=window_state.get("attachment_context") or "",
        resume=window_chat_request.resume,
    )

    round_failed = False
    round_interrupted = False
    try:
        round_interrupted = await chat_with_single_agent(chat_round_info, publisher)
    except Exception as e:
        round_failed = True
        logger.exception(
            "单聊轮次失败 session_id=%s round_id=%s",
            session_id,
            round_id,
        )
        await publisher.publish(
            session_id,
            round_id,
            {"event": "error", "message": getattr(e, "message", None) or str(e)},
        )
        raise
    finally:
        if round_failed:
            round_status = "failed"
        elif round_interrupted:
            round_status = "interrupted"
        else:
            round_status = "completed"
        await publisher.set_round_status(session_id, round_id, round_status)
        if not round_interrupted:
            await publisher.clear_active_round(session_id)


def execute_chat_round_for_session_type(
    window_chat_request: WindowChatRequest,
    window_graph: CompiledStateGraph,
    window_state: dict,
    config: dict,
    publisher: EventPublisher,
):
    """返回 awaitable，供 asyncio.create_task 使用。"""
    if window_chat_request.session_type == SessionType.GROUP_CHAT:
        return execute_group_chat_round(window_chat_request, window_graph, window_state, config, publisher)
    return execute_single_chat_round(window_chat_request, window_graph, window_state, config, publisher)
