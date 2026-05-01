
import json
from typing import Any
from app.agent_log.models import AgentLog
from app.database import get_db, transactional_session
from app.group_chat.chat_common import RoleType
from langchain_core.messages import AIMessage, ToolMessage


async def save_model_message(user_id: int, session_id: str, round_id: str, type: str, current_speaker: dict[str, Any], message: AIMessage | ToolMessage | str):
    """保存模型每次输出，统计token用量"""
    if isinstance(message, str):
        row = AgentLog(
            user_id=user_id,
            session_id=session_id,
            round_id=round_id,
            role_type=RoleType.SPEAKER.value,
            message_type=type,
            content=message,
            speaker_id=current_speaker.get("id"),
            speaker_name=current_speaker.get("name"),
        )
    elif isinstance(message, ToolMessage):
        row = AgentLog(
            user_id=user_id,
            session_id=session_id,
            round_id=round_id,
            role_type=RoleType.SPEAKER.value,
            message_type=type,
            content=message.content,
            tool_name=message.name,
            tool_call_id=message.tool_call_id,
            speaker_id=current_speaker.get("id"),
            speaker_name=current_speaker.get("name"),
        )
    else:
        usage_metadata = getattr(message, "usage_metadata", None) or {}
        try:
            content = _content_to_text_for_storage(message.content)
        except Exception:
            content = str(message.content)
        tool_calls: list[dict[str, Any]] = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append({
                                    "tool_name": tool_call["name"],
                                    "tool_args": tool_call["args"],
                                    "tool_id": tool_call["id"],
                                })
        print(tool_calls)
        row = AgentLog(
            user_id=user_id,
            session_id=session_id,
            round_id=round_id,
            role_type=RoleType.SPEAKER.value,
            message_type=type,
            content=content,
            input_tokens=usage_metadata.get("input_tokens", 0),
            output_tokens=usage_metadata.get("output_tokens", 0),
            total_tokens=usage_metadata.get("total_tokens", 0),
            tool_calls=tool_calls if tool_calls else None,
            speaker_id=current_speaker.get("id"),
            speaker_name=current_speaker.get("name"),
        )
    with transactional_session() as session:
        session.add(row)


def _content_to_text_for_storage(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)        