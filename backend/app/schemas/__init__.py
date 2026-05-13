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


def api_error_dict(*, code: int, message: str) -> dict:
    """与 ApiResponse 字段一致，供异常处理器 JSON 返回（非 0 的 code 表示失败）。"""
    return {"code": code, "message": message, "data": None}


class SkillBase(BaseModel):
    name: str
    description: Optional[str] = None


class SkillCreate(SkillBase):
    file_path: Optional[str] = None


class SkillResponse(SkillBase):
    id: int
    type: int = Field(validation_alias='resource_type', description='1 内置 2 自定义')
    file_path: Optional[str] = None
    create_time: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None


class AgentResponse(AgentBase):
    id: int
    type: int = Field(validation_alias='resource_type', description='1 内置 2 自定义')
    create_time: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentWithSkills(AgentResponse):
    skills: list[SkillResponse] = []


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
