from __future__ import annotations

from typing import Any, TypedDict


class ExecutionContext(TypedDict, total=False):
    """Harness 标准执行上下文。

    单聊 ``SingleChatContext`` 与群聊 ``SpeakContext`` 的公共字段在此收敛，
    后续 Policy / Observability 层可统一读取。
    """

    user_id: int
    session_id: str
    round_id: str
    agent_id: int
    user_custom_prompt: str
    speaker_prompt: str
    speaker_id: int
    user_message: str
    user_profile: dict[str, Any]
    history_messages: list[dict[str, Any]]
    group_members: list[dict[str, Any]]
    transcript: list[dict[str, Any]] | None
