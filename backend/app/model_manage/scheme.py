from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_bigint(v: Any) -> int:
    if isinstance(v, bool):
        raise ValueError("无效的 ID")
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            raise ValueError("无效的 ID")
        return int(s)
    raise ValueError("无效的 ID")


class ModelProviderCreateRequest(BaseModel):
    name: str = Field(..., description="模型提供者名称")
    api_key: str = Field(..., description="模型提供者API密钥")
    base_url: str


class ModelProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v: Any) -> str:
        return str(v)


class ModelProviderUpdateRequest(BaseModel):
    id: str
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v: Any) -> str:
        return str(v)


class ChatModelCreateRequest(BaseModel):
    name: str = Field(..., description="聊天模型名称")
    provider_id: str = Field(..., description="模型提供者ID")
    model_type: str = Field(..., description="模型类型")
    description: str | None = None

    @field_validator("provider_id", mode="before")
    @classmethod
    def _pid_str(cls, v: Any) -> str:
        return str(_coerce_bigint(v))


class ChatModelResponse(BaseModel):
    id: str
    name: str
    provider_id: str
    provider_name: str = ""
    model_type: str
    description: str | None = None

    @field_validator("id", "provider_id", mode="before")
    @classmethod
    def _ids_str(cls, v: Any) -> str:
        return str(v)


class ChatModelUpdateRequest(BaseModel):
    id: str
    name: str | None = None
    provider_id: str | None = None
    model_type: str | None = None
    description: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v: Any) -> str:
        return str(v)

    @field_validator("provider_id", mode="before")
    @classmethod
    def _pid_opt(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(_coerce_bigint(v))



class AgentChatModelInfo(BaseModel):
    """给智能体使用的模型信息"""
    model_name: str
    base_url: str
    api_key: str
