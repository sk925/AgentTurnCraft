from typing import TypedDict
from app.chat.base.models.association_tables import group_agent, skill_agent
from app.database import Base, transactional_session
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Agent(Base):
    __tablename__ = "agent"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    prompt = Column(Text)
    resource_type = Column("type", Integer, nullable=False, server_default="2")
    create_time = Column(DateTime, server_default=func.now())
    chat_model_id = Column(BigInteger, nullable=True)

    skills = relationship("Skill", secondary=skill_agent, back_populates="agents")


Agent.groups = relationship("Group", secondary=group_agent, back_populates="agents")



class SingleAgentInfo(TypedDict, total=False):
    id: int
    name: str
    prompt: str
    chat_model_id: int
    skills: list[dict]


    
class AgentService:
    @staticmethod
    def get_agent_info_by_id(agent_id: int) -> SingleAgentInfo | None:
        with transactional_session() as session:
            agent: Agent = session.query(Agent).filter(Agent.id == agent_id).first()
            if agent is None:
                return None
            return SingleAgentInfo(
                id=agent.id,
                name=agent.name,
                prompt=agent.prompt,
                chat_model_id=agent.chat_model_id,
                skills=[{"id": skill.id, "name": skill.name, "file_path": skill.file_path} for skill in agent.skills],
            )
