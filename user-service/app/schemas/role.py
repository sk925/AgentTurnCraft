from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[int] | None = None


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None
    permission_ids: list[int]

    model_config = {"from_attributes": True}
