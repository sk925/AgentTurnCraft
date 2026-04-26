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


class ChatSessionMessageResponse(BaseModel):
    role_type: str
    message_type: str | None = None
    message_content: str
    speaker_id: int | None = None
    speaker_name: str | None = None
