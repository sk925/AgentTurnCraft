from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


def success_response(data: T | None = None, message: str = "ok") -> ApiResponse[T]:
    return ApiResponse[T](code=0, message=message, data=data)


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def api_error_dict(*, code: int, message: str) -> dict:
    """与 ApiResponse 字段一致，供异常处理器 JSON 返回（非 0 的 code 表示失败）。"""
    return {"code": code, "message": message, "data": None}


class SkillBase(BaseModel):
    name: str
    description: Optional[str] = None


class SkillCreate(SkillBase):
    file_path: Optional[str] = None


class SkillUpdate(BaseModel):
    description: Optional[str] = None


class SkillResponse(SkillBase):
    id: int
    type: int = Field(validation_alias='resource_type', description='1 内置 2 自定义')
    file_path: Optional[str] = None
    skill_desc: Optional[str] = None
    create_time: datetime

    model_config = ConfigDict(from_attributes=True)


def _optional_chat_model_id(v: Any) -> int | None:
    """接受 JSON 数字或字符串（大整数），写入 ORM 前转为 int。"""
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


class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None


class AgentCreate(AgentBase):
    chat_model_id: int | None = None

    @field_validator("chat_model_id", mode="before")
    @classmethod
    def _chat_model_id_create(cls, v: Any) -> int | None:
        return _optional_chat_model_id(v)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    chat_model_id: int | None = None

    @field_validator("chat_model_id", mode="before")
    @classmethod
    def _chat_model_id_update(cls, v: Any) -> int | None:
        return _optional_chat_model_id(v)


class AgentResponse(AgentBase):
    id: int
    user_id: int
    type: int = Field(validation_alias='resource_type', description='1 内置 2 自定义')
    create_time: datetime
    chat_model_id: str | None = None

    @field_validator("chat_model_id", mode="before")
    @classmethod
    def _chat_model_id_resp(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)

    model_config = ConfigDict(from_attributes=True)


class AgentWithSkills(AgentResponse):
    skills: list[SkillResponse] = []


class KnowledgeBaseBrief(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    embedding_model_id: str | None = None

    @field_validator("embedding_model_id", mode="before")
    @classmethod
    def _embedding_model_id_resp(cls, v: Any) -> str | None:
        if v is None:
            return None
        return str(v)

    model_config = ConfigDict(from_attributes=True)


_MCP_SENSITIVE_HEADER_KEYS = frozenset({"authorization", "proxy-authorization", "x-api-key"})


def _mask_mcp_headers(headers: dict[str, Any] | None) -> dict[str, str] | None:
    if not headers:
        return None
    masked: dict[str, str] = {}
    for key, value in headers.items():
        k = str(key)
        if k.lower() in _MCP_SENSITIVE_HEADER_KEYS:
            masked[k] = "***"
        else:
            masked[k] = str(value)
    return masked


class McpServerBase(BaseModel):
    name: str
    description: Optional[str] = None
    transport: str = Field(description="http / streamable_http / stdio")
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    enabled: bool = True


class McpServerCreate(McpServerBase):
    pass


class McpServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    transport: Optional[str] = None
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    enabled: Optional[bool] = None


class McpServerResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    transport: str
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    enabled: bool = True
    type: int = Field(validation_alias="resource_type", description="1 内置 2 自定义")
    create_time: datetime
    has_headers: bool = False

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> "McpServerResponse":  # type: ignore[override]
        if hasattr(obj, "headers") and not isinstance(obj, dict):
            raw_headers = getattr(obj, "headers", None)
            data = {
                "id": obj.id,
                "name": obj.name,
                "description": obj.description,
                "transport": obj.transport,
                "url": obj.url,
                "command": obj.command,
                "args": list(obj.args) if isinstance(obj.args, list) else None,
                "headers": _mask_mcp_headers(raw_headers if isinstance(raw_headers, dict) else None),
                "enabled": bool(obj.enabled),
                "resource_type": obj.resource_type,
                "create_time": obj.create_time,
                "has_headers": bool(raw_headers),
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class AgentWithSkillsAndKnowledgeBases(AgentWithSkills):
    knowledge_bases: list[KnowledgeBaseBrief] = []
    mcp_servers: list[McpServerResponse] = []


class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class GroupCreate(GroupBase):
    agent_ids: list[int] = []


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_ids: Optional[list[int]] = None


class GroupResponse(GroupBase):
    id: int
    type: int = Field(validation_alias='resource_type', description='1 内置 2 自定义')
    create_time: datetime
    agents: list[AgentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class UploadFileResponse(BaseModel):
    """上传成功返回；id 使用字符串避免超过 JS Number 安全整数时前端精度丢失。"""

    id: str
    user_id: int
    file_name: str
    file_path: str
    file_type: str
    file_size: int
    preview_url: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""
