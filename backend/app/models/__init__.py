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
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False,unique=True)
    description = Column(Text)
    file_path = Column(String(500))
    # 1 内置（admin 创建） 2 自定义；列名为 type
    resource_type = Column('type', Integer, nullable=False, server_default='2')
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship('Agent', secondary=skill_agent, back_populates='skills')


class Agent(Base):
    __tablename__ = 'agent'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    prompt = Column(Text)
    resource_type = Column('type', Integer, nullable=False, server_default='2')
    create_time = Column(DateTime, server_default=func.now())

    skills = relationship('Skill', secondary=skill_agent, back_populates='agents')


group_agent = Table(
    'group_agent',
    Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('group_id', Integer, ForeignKey('group.id', ondelete='CASCADE')),
    Column('agent_id', Integer, ForeignKey('agent.id', ondelete='CASCADE')),
    Column('create_time', DateTime, server_default=func.now()),
    extend_existing=True
)


class Group(Base):
    __tablename__ = 'group'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    resource_type = Column('type', Integer, nullable=False, server_default='2')
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship('Agent', secondary=group_agent, back_populates='groups')


Agent.groups = relationship('Group', secondary=group_agent, back_populates='agents')
