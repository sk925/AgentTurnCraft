import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import get_snowflake_id


class ModelType(str,Enum):
    TEXT_GENERATION = "text_generation"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    AUDIO_GENERATION = "audio_generation"
    VIDEO_GENERATION = "video_generation"
    CODE_GENERATION = "code_generation"
    DATA_GENERATION = "data_generation"


class ModelProvider(Base):
    __tablename__ = "base_model_provider"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=get_snowflake_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class ChatModel(Base):
    __tablename__ = "base_chat_model"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=get_snowflake_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_id: Mapped[int] = mapped_column(BigInteger,nullable=False)
    model_type: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())




