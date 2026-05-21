"""群聊/技能与智能体、群组与智能体的关联表（先于 ORM 类加载，避免循环导入）。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table
from sqlalchemy.sql import func

from app.database import Base

skill_agent = Table(
    "skill_agent",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("skill_id", Integer, ForeignKey("skill.id", ondelete="CASCADE")),
    Column("agent_id", Integer, ForeignKey("agent.id", ondelete="CASCADE")),
    Column("create_time", DateTime, server_default=func.now()),
    extend_existing=True,
)

group_agent = Table(
    "group_agent",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("group_id", Integer, ForeignKey("group.id", ondelete="CASCADE")),
    Column("agent_id", Integer, ForeignKey("agent.id", ondelete="CASCADE")),
    Column("create_time", DateTime, server_default=func.now()),
    extend_existing=True,
)
