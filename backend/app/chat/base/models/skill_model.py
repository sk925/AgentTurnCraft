from app.chat.base.models.association_tables import skill_agent
from app.database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import BigInteger


class Skill(Base):
    __tablename__ = "skill"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(255), nullable=False, unique=True,comment="技能名称")
    description = Column(Text,comment="技能描述")
    file_path = Column(String(500),comment="技能文件在minio中的路径")
    resource_type = Column(Integer, nullable=False, server_default="2",comment="资源类型：内置=1、自定义=2。")
    create_time = Column(DateTime, server_default=func.now(),comment="创建时间")
    skill_desc = Column(Text, nullable=False,comment="skill.md中的描述")

    agents = relationship("Agent", secondary=skill_agent, back_populates="skills")
