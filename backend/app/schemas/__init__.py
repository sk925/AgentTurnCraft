from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
