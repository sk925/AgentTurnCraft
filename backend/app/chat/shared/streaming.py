"""Deep Agent 流式事件映射（单聊 / 群聊共用）。"""

from __future__ import annotations

import json
from typing import Any

from app.chat.base.models.agent_log import AgentLogService
from app.chat.shared.chat_common import InnerNode, MsgType, RoleType
from app.chat.shared.event_publisher import EventPublisher


def message_chunk_text(message: object) -> str:
    """从 LangChain 消息 / 分片中取出可下发的文本增量。"""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    if content is not None:
        return str(content)
    return ""


async def stream_messages(
    data: Any,
    publisher: EventPublisher,
    session_id: str,
    round_id: str,
    current_speaker: dict[str, Any],
) -> None:
    """处理 Deep Agent messages 模式的流式增量。"""
    if isinstance(data, tuple) and len(data) >= 2:
        message, meta = data[0], data[1]
        delta = message_chunk_text(message)
        if delta:
            inner_node = meta.get("langgraph_node", "") if isinstance(meta, dict) else ""
            if inner_node == InnerNode.MODEL.value:
                await publisher.publish(
                    session_id,
                    round_id,
                    {
                        "event": "speaker_model_stream",
                        "speaker_id": current_speaker.get("id"),
                        "speaker_name": current_speaker.get("name"),
                        "delta": delta,
                        "inner_node": inner_node,
                    },
                )
            elif inner_node == InnerNode.TOOL.value:
                print(f"tool_output={message}")


async def stream_updates(
    data: Any,
    publisher: EventPublisher,
    session_id: str,
    round_id: str,
    current_speaker: dict[str, Any],
    user_id: int,
) -> None:
    """处理 Deep Agent updates 模式的工具调用与模型输出。"""
    if "model" in data:
        final_msg = data["model"]["messages"]
        ai_msg = final_msg[0]
        if ai_msg.tool_calls:
            tool_calls: list[dict] = []
            for tool_call in ai_msg.tool_calls:
                if tool_call["name"] == "write_todos":
                    continue
                if tool_call["name"] == "ask_user_question":
                    await publisher.publish(
                        session_id,
                        round_id,
                        {
                            "event": "speaker_interrupt",
                            "args": tool_call["args"],
                            "tool_id": tool_call.get("id") or "",
                            "speaker_id": current_speaker.get("id"),
                            "speaker_name": current_speaker.get("name"),
                        },
                    )
                    await AgentLogService.save_model_message(
                        user_id,
                        session_id,
                        round_id,
                        MsgType.INTERACTIVE.value,
                        current_speaker,
                        RoleType.SPEAKER.value,
                        json.dumps(tool_call["args"], ensure_ascii=False),
                    )
                    continue
                tool_calls.append(
                    {
                        "tool_name": tool_call["name"],
                        "tool_args": tool_call["args"],
                        "tool_id": tool_call["id"],
                    }
                )
            if len(tool_calls) > 0:
                await publisher.publish(
                    session_id,
                    round_id,
                    {
                        "event": "speaker_tool_call",
                        "tool_calls": tool_calls,
                        "speaker_id": current_speaker.get("id"),
                        "speaker_name": current_speaker.get("name"),
                    },
                )
            await AgentLogService.save_model_message(
                user_id,
                session_id,
                round_id,
                MsgType.TOOL_CALL.value,
                current_speaker,
                RoleType.SPEAKER.value,
                ai_msg,
            )
        else:
            await AgentLogService.save_model_message(
                user_id,
                session_id,
                round_id,
                MsgType.MODEL.value,
                current_speaker,
                RoleType.SPEAKER.value,
                ai_msg,
            )
    elif "tools" in data:
        print(f"[DEBUG tools] payload: {data}")
        tool_msg_list = data["tools"]["messages"]
        for tool_msg in tool_msg_list:
            if tool_msg.name == "write_todos":
                await AgentLogService.save_model_message(
                    user_id,
                    session_id,
                    round_id,
                    MsgType.TODO_LIST.value,
                    current_speaker,
                    RoleType.SPEAKER.value,
                    tool_msg,
                )
                continue
            if tool_msg.name == "ask_user_question":
                continue
            await AgentLogService.save_model_message(
                user_id,
                session_id,
                round_id,
                MsgType.TOOL_OUT.value,
                current_speaker,
                RoleType.SPEAKER.value,
                tool_msg,
            )
            await publisher.publish(
                session_id,
                round_id,
                {
                    "event": "speaker_tool_out",
                    "tool_name": tool_msg.name,
                    "content": tool_msg.content,
                    "tool_id": tool_msg.tool_call_id,
                    "speaker_id": current_speaker.get("id"),
                    "speaker_name": current_speaker.get("name"),
                },
            )
        todos = None
        if isinstance(data.get("tools"), dict):
            todos = data["tools"].get("todos")
        if todos:
            await publisher.publish(
                session_id,
                round_id,
                {
                    "event": "speaker_todo_list",
                    "todos": todos,
                    "speaker_id": current_speaker.get("id"),
                    "speaker_name": current_speaker.get("name"),
                },
            )
    elif "todos" in data and data.get("todos"):
        await publisher.publish(
            session_id,
            round_id,
            {
                "event": "speaker_todo_list",
                "todos": data["todos"],
                "speaker_id": current_speaker.get("id"),
                "speaker_name": current_speaker.get("name"),
            },
        )
