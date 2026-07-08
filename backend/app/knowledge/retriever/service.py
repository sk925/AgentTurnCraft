from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge.agent_scope import AgentKnowledgeScope, get_agent_knowledge_scope
from app.knowledge.constants import RETRIEVAL_TOP_K
from app.knowledge.embedder import KnowledgeEmbedder
from app.knowledge.enums import KnowledgeDocumentStatus
from app.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """向量检索命中的知识库分块。"""

    content: str
    score: float
    knowledge_base_id: int
    knowledge_base_name: str
    document_id: int
    file_name: str
    chunk_index: int
    metadata: dict[str, Any]


class KnowledgeRetriever:
    def __init__(self, db: Session):
        self.db = db
        self.embedder = KnowledgeEmbedder(db)

    def retrieve_for_agent(
        self,
        *,
        agent_id: int,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> list[RetrievedChunk]:
        scope = get_agent_knowledge_scope(self.db, agent_id)
        if scope is None:
            return []
        return self.retrieve(
            query=query,
            scope=scope,
            top_k=top_k,
        )

    def retrieve(
        self,
        *,
        query: str,
        scope: AgentKnowledgeScope,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> list[RetrievedChunk]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        query_vector = self.embedder.embed_query(
            normalized_query,
            embedding_model_id=scope.embedding_model_id,
        )

        distance_expr = KnowledgeChunk.embedding.cosine_distance(query_vector)
        rows = (
            self.db.query(
                KnowledgeChunk,
                KnowledgeDocument,
                KnowledgeBase,
                distance_expr.label("distance"),
            )
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .join(KnowledgeBase, KnowledgeBase.id == KnowledgeChunk.knowledge_base_id)
            .filter(
                KnowledgeChunk.knowledge_base_id.in_(scope.knowledge_base_ids),
                KnowledgeDocument.status == KnowledgeDocumentStatus.READY.value,
            )
            .order_by(distance_expr)
            .limit(top_k)
            .all()
        )

        results: list[RetrievedChunk] = []
        for chunk, document, knowledge_base, distance in rows:
            score = max(0.0, 1.0 - float(distance))
            results.append(
                RetrievedChunk(
                    content=chunk.content,
                    score=score,
                    knowledge_base_id=knowledge_base.id,
                    knowledge_base_name=knowledge_base.name,
                    document_id=document.id,
                    file_name=document.file_name,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.chunk_metadata or {},
                )
            )
        return results


def format_retrieved_chunks(chunks: list[RetrievedChunk]) -> str:
    """将检索结果格式化为模型可读文本。"""
    if not chunks:
        return "未在关联知识库中检索到相关内容。"

    parts: list[str] = []
    for index, item in enumerate(chunks, start=1):
        parts.append(
            "\n".join(
                [
                    f"## 片段 {index}",
                    f"- 知识库: {item.knowledge_base_name}",
                    f"- 文档: {item.file_name}",
                    f"- 相关度: {item.score:.3f}",
                    "",
                    item.content.strip(),
                ]
            )
        )
    result=  "\n\n".join(parts)
    print(result)
    return result
