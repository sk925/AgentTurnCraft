from app.chat.base.models.association_tables import group_agent
from app.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Group(Base):
    __tablename__ = "group"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    resource_type = Column("type", Integer, nullable=False, server_default="2")
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship("Agent", secondary=group_agent, back_populates="groups")
