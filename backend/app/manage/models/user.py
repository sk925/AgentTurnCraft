from sqlalchemy import BIGINT, Boolean, ForeignKey, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import get_snowflake_id

user_role_association = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BIGINT, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BIGINT, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, default=get_snowflake_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    roles = relationship("Role", secondary=user_role_association, back_populates="users")
