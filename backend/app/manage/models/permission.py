from sqlalchemy import BIGINT, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import RESOURCE_TYPE_CUSTOM
from app.database import Base
from app.utils.snowflake import get_snowflake_id


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, default=get_snowflake_id)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=RESOURCE_TYPE_CUSTOM,
        comment="1 内置 2 自定义",
    )

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")
