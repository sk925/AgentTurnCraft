from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    member_id = Column(Integer, nullable=False, index=True)
    create_at = Column(DateTime, server_default=func.now(), nullable=False)
    token_use = Column(Integer, nullable=True)
    session_type = Column(String(64), nullable=False, default="group_chat")
