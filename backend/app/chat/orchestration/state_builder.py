"""按 session 类型构建 WindowState 与 LangGraph 编译图。"""

from __future__ import annotations

from fastapi import HTTPException
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.chat.base.models import Agent, Group
from app.chat.orchestration.bootstrap import bootstrap_round
from app.chat.orchestration.window_request import WindowChatRequest
from app.chat.shared.chat_common import SessionType, WindowState
from app.constants import RESOURCE_TYPE_BUILTIN
from app.harness.round import RoundContext


def _agents_for_group_request(
    window_chat_request: WindowChatRequest,
    member_id: int,
    db: Session,
) -> list[Agent]:
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


def build_window_state_and_config(
    window_chat_request: WindowChatRequest,
    db: Session,
) -> tuple[WindowState, dict]:
    member_id = window_chat_request.user_id
    b = bootstrap_round(window_chat_request, db)
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
        "user_profile": {
            "member_id": member_id,
            "org_id": window_chat_request.org_id,
            "member_role": "STUDENT",
        },
        "question_data": {},
        "user_input": {},
    }
    config = {"configurable": {"thread_id": b.session_id}}
    return window_state, config


def build_group_window_state(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> RoundContext:
    if window_chat_request.session_type != SessionType.GROUP_CHAT:
        raise HTTPException(status_code=400, detail="会话类型不是群聊")

    window_state, config = build_window_state_and_config(window_chat_request, db)
    from app.chat.group.chat_graph import get_window_graph

    window_graph = get_window_graph(checkpointer)
    return RoundContext(window_state=window_state, window_graph=window_graph, config=config)


def build_single_window_state(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> RoundContext:
    window_state, config = build_window_state_and_config(window_chat_request, db)
    return RoundContext(window_state=window_state, window_graph=None, config=config)
