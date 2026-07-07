from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _optional_bigint_id(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        raise ValueError("无效的模型 ID")
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if not s:
        return None
    return int(s)


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    embedding_model_id: int | None = None

    @field_validator("embedding_model_id", mode="before")
    @classmethod
    def _embedding_model_id(cls, v: Any) -> int | None:
        return _optional_bigint_id(v)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    embedding_model_id: str | None = None
    embedding_dimension: int = 1536
    type: int = Field(validation_alias="resource_type", description="1 内置 2 自定义")
    create_time: datetime

    @field_validator("embedding_model_id", mode="before")
    @classmethod
    def _embedding_model_id_resp(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentResponse(BaseModel):
    id: int
    knowledge_base_id: int
    file_name: str
    file_type: str
    file_size: int
    status: str
    error_message: str | None = None
    chunk_count: int
    create_time: datetime

    model_config = ConfigDict(from_attributes=True)
