from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


skill_agent = Table(
    'skill_agent',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('skill_id', Integer, ForeignKey('skill.id', ondelete='CASCADE')),
    Column('agent_id', Integer, ForeignKey('agent.id', ondelete='CASCADE')),
    Column('create_time', DateTime, server_default=func.now()),
    extend_existing=True
)


class Skill(Base):
    __tablename__ = 'skill'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False,unique=True)
    description = Column(Text)
    file_path = Column(String(500))
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship('Agent', secondary=skill_agent, back_populates='skills')


class Agent(Base):
    __tablename__ = 'agent'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    prompt = Column(Text)
    create_time = Column(DateTime, server_default=func.now())

    skills = relationship('Skill', secondary=skill_agent, back_populates='agents')
