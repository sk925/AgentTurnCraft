from app.database import Base
from app.knowledge.enums import KnowledgeDocumentStatus
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_document"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(255), nullable=False, server_default="application/octet-stream")
    file_size = Column(BigInteger, nullable=False, server_default="0")
    status = Column(String(32), nullable=False, server_default=KnowledgeDocumentStatus.PENDING.value, index=True)
    error_message = Column(Text)
    chunk_count = Column(Integer, nullable=False, server_default="0")
    create_time = Column(DateTime, server_default=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
