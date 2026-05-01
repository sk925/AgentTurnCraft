from pydantic import BaseModel, Field


class PermissionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class PermissionOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None

    model_config = {"from_attributes": True}
