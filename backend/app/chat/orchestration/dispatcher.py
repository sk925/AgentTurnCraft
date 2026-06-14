"""会话轮次统一入口：按 SessionType 分派到 ChatModeHandler。"""

from __future__ import annotations

from typing import Any

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.chat.orchestration.handlers import get_chat_mode_handler
from app.chat.orchestration.window_request import WindowChatRequest
from app.chat.shared.chat_common import WindowState
from app.chat.shared.event_publisher import EventPublisher
from app.harness.round import RoundContext


def build_window_state_for_session_type(
    window_chat_request: WindowChatRequest,
    db: Session,
    checkpointer,
) -> tuple[WindowState, CompiledStateGraph | None, dict[str, Any]]:
    """供 HTTP / WebSocket 统一入口调用。返回 (window_state, window_graph, config)。"""
    handler = get_chat_mode_handler(window_chat_request.session_type)
    round_ctx = handler.build(window_chat_request, db, checkpointer)
    return round_ctx.window_state, round_ctx.window_graph, round_ctx.config


async def execute_chat_round_for_session_type(
    window_chat_request: WindowChatRequest,
    window_graph,
    window_state: dict,
    config: dict,
    publisher: EventPublisher,
) -> None:
    handler = get_chat_mode_handler(window_chat_request.session_type)
    round_ctx = RoundContext(window_state=window_state, window_graph=window_graph, config=config)
    await handler.execute(window_chat_request, round_ctx, publisher)
