from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from app.exceptions import AppException
from app.knowledge.constants import DEFAULT_EMBEDDING_DIMENSION, EMBED_BATCH_SIZE
from app.model_manage.model_cat import ChatModel, ModelProvider, ModelType
from fastapi import status


@dataclass(frozen=True, slots=True)
class EmbeddingModelConfig:
    model_name: str
    base_url: str
    api_key: str


class KnowledgeEmbedder:
    def __init__(self, db: Session):
        self.db = db

    def get_embedding_config(self, embedding_model_id: int) -> EmbeddingModelConfig:
        row = (
            self.db.query(ChatModel, ModelProvider)
            .join(ModelProvider, ModelProvider.id == ChatModel.provider_id)
            .filter(
                ChatModel.id == embedding_model_id,
                ChatModel.model_type == ModelType.EMBEDDING.value,
            )
            .first()
        )
        if row is None:
            raise AppException(message="Embedding 模型不存在或类型不正确", code=status.HTTP_400_BAD_REQUEST)
        chat_model, provider = row
        if not provider.api_key:
            raise AppException(message="Embedding 模型提供者未配置 API Key", code=status.HTTP_400_BAD_REQUEST)
        return EmbeddingModelConfig(
            model_name=chat_model.name,
            base_url=provider.base_url,
            api_key=provider.api_key,
        )

    def embed_texts(self, texts: list[str], *, embedding_model_id: int) -> list[list[float]]:
        """将多个文本块批量向量化，供知识库索引写入 pgvector。

        Args:
            texts: 切块后的纯文本列表，顺序与 indexer 中的 TextChunk 一一对应。
            embedding_model_id: 知识库绑定的 Embedding 模型 ID（来自 model_manage）。

        Returns:
            与 texts 等长的向量列表；每条向量维度须为 DEFAULT_EMBEDDING_DIMENSION。

        Raises:
            AppException: 模型不存在、未配置 API Key，或返回维度与库表不一致。
        """
        if not texts:
            return []

        config = self.get_embedding_config(embedding_model_id)
        client = OpenAIEmbeddings(
            model=config.model_name,
            openai_api_key=config.api_key,
            openai_api_base=config.base_url,
            check_embedding_ctx_length=False,
        )

        vectors: list[list[float]] = []
        # 分批调用 Embedding API，避免单次请求体过大或触发限流
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            batch_vectors = client.embed_documents(batch)
            # knowledge_chunk.embedding 列固定维度，入库前必须校验
            for vector in batch_vectors:
                if len(vector) != DEFAULT_EMBEDDING_DIMENSION:
                    raise AppException(
                        message=(
                            f"Embedding 维度为 {len(vector)}，当前系统要求 "
                            f"{DEFAULT_EMBEDDING_DIMENSION} 维，请更换模型或调整配置"
                        ),
                        code=status.HTTP_400_BAD_REQUEST,
                    )
            vectors.extend(batch_vectors)
        return vectors

    def embed_query(self, query: str, *, embedding_model_id: int) -> list[float]:
        config = self.get_embedding_config(embedding_model_id)
        client = OpenAIEmbeddings(
            model=config.model_name,
            openai_api_key=config.api_key,
            openai_api_base=config.base_url,
            check_embedding_ctx_length=False,
        )
        vector = client.embed_query(query)
        if len(vector) != DEFAULT_EMBEDDING_DIMENSION:
            raise AppException(
                message=(
                    f"Embedding 维度为 {len(vector)}，当前系统要求 "
                    f"{DEFAULT_EMBEDDING_DIMENSION} 维，请更换模型或调整配置"
                ),
                code=status.HTTP_400_BAD_REQUEST,
            )
        return vector
