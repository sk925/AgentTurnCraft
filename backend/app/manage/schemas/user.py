from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


def _coerce_id_list(v: Any) -> list[int]:
    if not v:
        return []
    return [int(str(x)) for x in v]


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: EmailStr | None = None
    is_active: bool = True
    role_ids: list[int] = []

    @field_validator("role_ids", mode="before")
    @classmethod
    def _role_ids_create(cls, v: Any) -> list[int]:
        return _coerce_id_list(v)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None
    role_ids: list[int] | None = None

    @field_validator("role_ids", mode="before")
    @classmethod
    def _role_ids_update(cls, v: Any) -> list[int] | None:
        if v is None:
            return None
        return _coerce_id_list(v)


class UserOut(BaseModel):
    """id / role_ids 使用字符串，与 RoleOut.id 一致，避免雪花 ID 在 JSON/JS 中精度丢失。"""

    id: str
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool
    role_ids: list[str]

    @field_validator("id", mode="before")
    @classmethod
    def _id_str(cls, v: Any) -> str:
        return str(v)

    @field_validator("role_ids", mode="before")
    @classmethod
    def _role_ids_out(cls, v: Any) -> list[str]:
        if v is None:
            return []
        return [str(x) for x in v]

    model_config = {"from_attributes": True}
