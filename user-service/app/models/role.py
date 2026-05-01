from sqlalchemy import BIGINT, ForeignKey, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.id_generator import get_snowflake_id

role_permission_association = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BIGINT, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        BIGINT,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, default=get_snowflake_id)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    permissions = relationship("Permission", secondary=role_permission_association, back_populates="roles")
    users = relationship("User", secondary="user_roles", back_populates="roles")
