from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: EmailStr | None = None
    is_active: bool = True
    role_ids: list[int] = []


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    is_active: bool | None = None
    role_ids: list[int] | None = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool
    role_ids: list[int]

    model_config = {"from_attributes": True}
