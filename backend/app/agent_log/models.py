import time
from app.database import Base
from sqlalchemy import JSON, BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class AgentLog(Base):
    __tablename__ = "agent_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    round_id: Mapped[str] = mapped_column(String(128), index=True)
    role_type: Mapped[str] = mapped_column(String(32), comment="角色类型，如：user、agent_selector、speaker_selector、speaker、assistant")
    message_type: Mapped[str] = mapped_column(String(32),comment="消息类型，如：model、tool_call、tool_out")
    speaker_id: Mapped[int] = mapped_column(Integer, nullable=True,comment="发言人ID，如果为空，则表示不是发言人")
    speaker_name: Mapped[str] = mapped_column(String(128), nullable=True,comment="发言人名称，如果为空，则表示不是发言人")
    tool_name: Mapped[str] = mapped_column(String(128), nullable=True,comment="工具名称，如果为空，则表示不是工具调用")
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=True,comment="工具调用ID，如果为空，则表示不是工具调用")
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True,default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True,default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=True,default=0)
    file_list: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True),
        nullable=True,
        comment="文件列表，如果为空，则表示没有文件",
    )
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()), index=True)    