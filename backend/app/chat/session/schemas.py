from datetime import datetime

from pydantic import BaseModel


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    member_id: int
    create_at: datetime
    token_use: int | None = None
    session_type: str

    class Config:
        from_attributes = True


class ChatSessionMessageFileInfo(BaseModel):
    """用户消息附带的单个文件信息"""

    file_id: str
    file_name: str
    file_url: str
    file_type: str = ""


class ChatSessionMessageResponse(BaseModel):
    """会话中对话记录消息"""
    role_type: str
    message_type: str | None = None
    message_content: str
    speaker_id: int | None = None
    speaker_name: str | None = None
    file_info: list[ChatSessionMessageFileInfo] | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None

