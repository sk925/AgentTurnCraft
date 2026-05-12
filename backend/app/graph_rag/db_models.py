"""GraphRAG 语料表：图结构 + 分块文本以 JSON 存于 PostgreSQL。"""

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func

from app.database import Base


class GraphRagCorpus(Base):
    __tablename__ = "graph_rag_corpus"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    source_key = Column(String(512), nullable=False)
    title = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=False)
    create_time = Column(DateTime, server_default=func.now())
    remark = Column(Text, nullable=True)
