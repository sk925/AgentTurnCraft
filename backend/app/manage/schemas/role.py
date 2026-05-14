from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[str] | None = None


class RoleOut(BaseModel):
    id: str
    name: str
    description: str | None
    role_type: int = Field(description="1 内置 2 自定义")
    permission_ids: list[str]

    model_config = {"from_attributes": True}
