from app.constants import RESOURCE_TYPE_CUSTOM
from app.database import Base
from app.chat.base.models.association_tables import knowledge_base_agent
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    embedding_model_id = Column(BigInteger, nullable=True, index=True)
    embedding_dimension = Column(Integer, nullable=False, server_default="1536")
    resource_type = Column("type", Integer, nullable=False, server_default=str(RESOURCE_TYPE_CUSTOM))
    create_time = Column(DateTime, server_default=func.now())

    agents = relationship("Agent", secondary=knowledge_base_agent, back_populates="knowledge_bases")
    documents = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
