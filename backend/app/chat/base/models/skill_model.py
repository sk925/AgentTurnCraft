from app.chat.base.models.association_tables import skill_agent
from app.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Skill(Base):
    __tablename__ = "skill"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    file_path = Column(String(500))
    resource_type = Column("type", Integer, nullable=False, server_default="2")
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship("Agent", secondary=skill_agent, back_populates="skills")
