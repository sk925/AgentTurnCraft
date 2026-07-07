from app.database import Base
from app.knowledge.constants import DEFAULT_EMBEDDING_DIMENSION
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id = Column(BigInteger, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_document.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_metadata = Column(JSON, nullable=False, server_default="{}")
    embedding = Column(Vector(DEFAULT_EMBEDDING_DIMENSION), nullable=False)
    create_time = Column(DateTime, server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")
