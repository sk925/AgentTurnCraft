from __future__ import annotations

import logging

from app.database import transactional_session
from app.knowledge.indexer import KnowledgeIndexService

logger = logging.getLogger(__name__)


def run_index_document_task(document_id: int) -> None:
    """后台任务：解析、切块、向量化并写入 knowledge_chunk。"""
    try:
        with transactional_session() as db:
            KnowledgeIndexService(db).index_document(document_id)
    except Exception:
        logger.exception("run_index_document_task failed document_id=%s", document_id)
