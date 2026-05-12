import json
import time
from typing import Any

from app.database import Base, transactional_session
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy import JSON, BigInteger, Column, Integer, String, Text


class AgentLog(Base):
    __tablename__ = 'agent_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    session_id = Column(String(128), nullable=False, index=True)
    round_id = Column(String(128), nullable=False, index=True)
    role_type = Column(
        String(32),
        nullable=False,
        comment='角色类型，如：user、agent_selector、speaker_selector、speaker、assistant',
    )
    message_type = Column(String(32), nullable=False, comment='消息类型，如：model、tool_call、tool_out')
    speaker_id = Column(Integer, nullable=True, comment='发言人ID，如果为空，则表示不是发言人')
    speaker_name = Column(String(128), nullable=True, comment='发言人名称，如果为空，则表示不是发言人')
    tool_name = Column(String(128), nullable=True, comment='工具名称，如果为空，则表示不是工具调用')
    tool_call_id = Column(String(128), nullable=True, comment='工具调用ID，如果为空，则表示不是工具调用')
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON(none_as_null=True), nullable=True)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    file_list = Column(JSON(none_as_null=True), nullable=True, comment='文件列表，如果为空，则表示没有文件')
    created_at = Column(BigInteger, nullable=False, default=lambda: int(time.time()), index=True)
    model_name = Column(String(128), nullable=True, comment='模型名称，如果为空，则表示不是模型调用')


class AgentLogService:
    @staticmethod
    def save_agent_log(agent_log: AgentLog):
        with transactional_session() as session:
            session.add(agent_log)

    @staticmethod
    async def save_model_message(
        user_id: int,
        session_id: str,
        round_id: str,
        type: str,
        current_speaker: dict[str, Any],
        role_type: str,
        message: AIMessage | ToolMessage | str,
    ):
        """保存模型每次输出，统计 token 用量"""
        if isinstance(message, str):
            row = AgentLog(
                user_id=user_id,
                session_id=session_id,
                round_id=round_id,
                role_type=role_type,
                message_type=type,
                content=message,
                speaker_id=current_speaker.get('id'),
                speaker_name=current_speaker.get('name'),
            )
        elif isinstance(message, ToolMessage):
            row = AgentLog(
                user_id=user_id,
                session_id=session_id,
                round_id=round_id,
                role_type=role_type,
                message_type=type,
                content=message.content,
                tool_name=message.name,
                tool_call_id=message.tool_call_id,
                speaker_id=current_speaker.get('id'),
                speaker_name=current_speaker.get('name'),
            )
        else:
            usage_metadata = getattr(message, 'usage_metadata', None) or {}
            try:
                content = _content_to_text_for_storage(message.content)
            except Exception:
                content = str(message.content)
            tool_calls: list[dict[str, Any]] = []
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_calls.append({
                        'tool_name': tool_call['name'],
                        'tool_args': tool_call['args'],
                        'tool_id': tool_call['id'],
                    })
            print(tool_calls)
            row = AgentLog(
                user_id=user_id,
                session_id=session_id,
                round_id=round_id,
                role_type=role_type,
                message_type=type,
                content=content,
                input_tokens=usage_metadata.get('input_tokens', 0),
                output_tokens=usage_metadata.get('output_tokens', 0),
                total_tokens=usage_metadata.get('total_tokens', 0),
                tool_calls=tool_calls if tool_calls else None,
                speaker_id=current_speaker.get('id'),
                speaker_name=current_speaker.get('name'),
            )
        with transactional_session() as session:
            session.add(row)


def _content_to_text_for_storage(content: Any) -> str:
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)
