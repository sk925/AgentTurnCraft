from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


class AgentRuntimeMode(str, Enum):
    """Agent 编译图缓存域：单聊与群聊发言人使用不同键策略。"""

    SINGLE = "single"
    SPEAKER = "speaker"


@dataclass(frozen=True)
class AgentBuildConfig:
    """创建 Deep Agent 编译图所需的全部输入。"""

    agent_id: int
    chat_model_id: int
    checkpointer: Any
    middleware: Sequence[Any]
    context_schema: type
    mode: AgentRuntimeMode = AgentRuntimeMode.SINGLE
    skill_ids: tuple[int, ...] = field(default_factory=tuple)
