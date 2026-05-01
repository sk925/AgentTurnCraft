from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


def success_response(data: T | None = None, message: str = "ok") -> ApiResponse[T]:
    return ApiResponse[T](code=0, message=message, data=data)


class SkillBase(BaseModel):
    name: str
    description: Optional[str] = None


class SkillCreate(SkillBase):
    file_path: Optional[str] = None


class SkillResponse(SkillBase):
    id: int
    file_path: Optional[str] = None
    create_time: datetime

    class Config:
        from_attributes = True


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
    create_time: datetime

    class Config:
        from_attributes = True


class AgentWithSkills(AgentResponse):
    skills: list[SkillResponse] = []
