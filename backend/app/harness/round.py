"""Harness 轮次上下文：编排层与 AgentRuntime 之间的标准数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.chat.shared.chat_common import WindowState


@dataclass(frozen=True)
class RoundContext:
    """一轮对话的运行上下文（状态 + 可选 LangGraph + checkpointer config）。"""

    window_state: WindowState
    window_graph: CompiledStateGraph | None
    config: dict[str, Any]
