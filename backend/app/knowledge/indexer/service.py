from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import AppException
from app.knowledge.chunker import chunk_document
from app.knowledge.embedder import KnowledgeEmbedder
from app.knowledge.enums import KnowledgeDocumentStatus
from app.knowledge.models import KnowledgeBase, KnowledgeChunk, KnowledgeDocument
from app.knowledge.parser import DocumentParseError, parse_document
from app.model_manage.model_cat import ChatModel, ModelType
from app.utils.minio_storage import download_bytes, remove_object
from app.utils.snowflake import get_snowflake_id
from fastapi import status
from minio.error import S3Error

logger = logging.getLogger(__name__)


def _safe_filename(name: str) -> str:
    base = re.sub(r"[/\\]", "", name).strip() or "file"
    base = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", base)
    return base[:200] if len(base) > 200 else base


def build_knowledge_object_key(*, user_id: int, knowledge_base_id: int, document_id: int, file_name: str) -> str:
    safe = _safe_filename(file_name)
    return f"knowledge/{user_id}/{knowledge_base_id}/{document_id}_{safe}"


class KnowledgeIndexService:
    def __init__(self, db: Session):
        self.db = db
        self.embedder = KnowledgeEmbedder(db)

    def resolve_embedding_model_id(
        self,
        knowledge_base: KnowledgeBase,
        embedding_model_id: int | None,
    ) -> int:
        if knowledge_base.embedding_model_id is None:
            if embedding_model_id is None:
                raise AppException(message="请为知识库选择 Embedding 模型", code=status.HTTP_400_BAD_REQUEST)
            model = (
                self.db.query(ChatModel)
                .filter(
                    ChatModel.id == embedding_model_id,
                    ChatModel.model_type == ModelType.EMBEDDING.value,
                )
                .first()
            )
            if model is None:
                raise AppException(message="所选 Embedding 模型不存在或类型不正确", code=status.HTTP_400_BAD_REQUEST)
            knowledge_base.embedding_model_id = int(embedding_model_id)
            self.db.flush()
            return int(embedding_model_id)

        if embedding_model_id is not None and int(embedding_model_id) != int(knowledge_base.embedding_model_id):
            raise AppException(
                message="该知识库已锁定 Embedding 模型，请使用相同模型上传文档",
                code=status.HTTP_400_BAD_REQUEST,
            )
        return int(knowledge_base.embedding_model_id)

    def create_document_record(
        self,
        *,
        knowledge_base: KnowledgeBase,
        user_id: int,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(
            knowledge_base_id=knowledge_base.id,
            user_id=user_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            status=KnowledgeDocumentStatus.PENDING.value,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def index_document(self, document_id: int) -> None:
        document = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if document is None:
            logger.warning("index_document: document %s not found", document_id)
            return

        knowledge_base = (
            self.db.query(KnowledgeBase).filter(KnowledgeBase.id == document.knowledge_base_id).first()
        )
        if knowledge_base is None or knowledge_base.embedding_model_id is None:
            document.status = KnowledgeDocumentStatus.FAILED.value
            document.error_message = "知识库未配置 Embedding 模型"
            self.db.commit()
            return

        document.status = KnowledgeDocumentStatus.PROCESSING.value
        document.error_message = None
        self.db.flush()

        try:
            data = download_bytes(settings.minio_bucket, document.file_path)
            parsed = parse_document(
                data=data,
                file_name=document.file_name,
                mime_or_ext=document.file_type,
            )
            if parsed.is_empty:
                raise DocumentParseError("文档解析结果为空", file_name=document.file_name)

            text_chunks = chunk_document(parsed)
            if not text_chunks:
                raise DocumentParseError("文档切块结果为空", file_name=document.file_name)

            vectors = self.embedder.embed_texts(
                [chunk.content for chunk in text_chunks],
                embedding_model_id=int(knowledge_base.embedding_model_id),
            )

            self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()

            for chunk, vector in zip(text_chunks, vectors, strict=True):
                self.db.add(
                    KnowledgeChunk(
                        id=get_snowflake_id(),
                        knowledge_base_id=knowledge_base.id,
                        document_id=document.id,
                        chunk_index=chunk.index,
                        content=chunk.content,
                        chunk_metadata=chunk.metadata,
                        embedding=vector,
                    )
                )

            document.chunk_count = len(text_chunks)
            document.status = KnowledgeDocumentStatus.READY.value
            self.db.commit()
        except Exception as exc:
            logger.exception("index_document failed document_id=%s", document_id)
            self.db.rollback()
            document = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
            if document is not None:
                document.status = KnowledgeDocumentStatus.FAILED.value
                document.error_message = str(exc)[:2000]
                document.chunk_count = 0
                self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
                self.db.commit()

    def delete_document(self, document: KnowledgeDocument) -> None:
        try:
            remove_object(settings.minio_bucket, document.file_path)
        except S3Error as exc:
            logger.warning("delete_document minio remove failed: %s", exc.message)
        self.db.delete(document)
        self.db.commit()

    def prepare_reindex(self, document: KnowledgeDocument) -> None:
        """将文档重置为待索引，供失败后重试或手动重建向量。"""
        if document.status == KnowledgeDocumentStatus.PROCESSING.value:
            raise AppException(message="文档正在索引中，请稍后再试", code=status.HTTP_409_CONFLICT)
        if not document.file_path or document.file_path == "pending":
            raise AppException(message="文档文件不存在，请重新上传", code=status.HTTP_400_BAD_REQUEST)

        document.status = KnowledgeDocumentStatus.PENDING.value
        document.error_message = None
        document.chunk_count = 0
        self.db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document.id).delete()
        self.db.flush()
