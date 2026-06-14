"""聊天窗口请求模型（供 HTTP / WebSocket / 各 session 类型的 round 构建共用）。"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.chat.shared.chat_common import SessionType


def normalize_window_file_ids(raw: Any) -> list[int]:
    """解析 WebSocket / JSON 中的 file_ids（支持 int 或字符串形式的雪花 id）。"""
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


class WindowChatRequest(BaseModel):
    """窗口聊天请求"""

    user_message: str = ""
    org_id: int
    user_id: int
    session_id: str | None
    round_id: str | None
    session_type: SessionType = SessionType.CHAT
    group_id: int | None = Field(
        default=None,
        description="群聊时可选：仅允许该群组内的智能体进入候选池",
    )
    file_ids: list[int] | None = Field(
        default=None,
        description="文件ID列表",
    )
    single_agent_id: str | None = Field(
        default=None,
        description="单聊时可选：指定智能体ID",
    )
    resume: dict[str, Any] | None = Field(
        default=None,
        description="继续对话时可选：继续对话数据",
    )

    @field_validator("file_ids", mode="before")
    @classmethod
    def _coerce_file_ids(cls, v: Any) -> list[int] | None:
        if v is None:
            return None
        parsed = normalize_window_file_ids(v)
        return parsed or None
