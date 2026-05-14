from pydantic import BaseModel, Field


class PermissionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class PermissionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class PermissionOut(BaseModel):
    id: str
    code: str
    name: str
    description: str | None
    permission_type: int = Field(description="1 内置 2 自定义")

    model_config = {"from_attributes": True}


class PermissionMineOut(BaseModel):
    """当前用户拥有的权限编码（含菜单与其它），用于前端侧栏等。"""

    codes: list[str]
