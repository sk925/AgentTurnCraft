from __future__ import annotations

from app.exceptions import AppException
from app.knowledge.constants import MAX_AGENT_KNOWLEDGE_BASES
from app.knowledge.models import KnowledgeBase
from app.chat.base.models import Agent
from fastapi import status


def validate_agent_knowledge_base_binding(
    *,
    agent: Agent,
    knowledge_base: KnowledgeBase,
    already_linked: bool,
) -> None:
    """校验智能体关联知识库：最多 3 个，且 Embedding 模型必须一致。"""
    if already_linked:
        return

    if knowledge_base.embedding_model_id is None:
        raise AppException(
            message="该知识库尚未配置 Embedding 模型，请先在上传文档时选定模型",
            code=status.HTTP_400_BAD_REQUEST,
        )

    linked: list[KnowledgeBase] = list(agent.knowledge_bases or [])
    if len(linked) >= MAX_AGENT_KNOWLEDGE_BASES:
        raise AppException(
            message=f"每个智能体最多关联 {MAX_AGENT_KNOWLEDGE_BASES} 个知识库",
            code=status.HTTP_400_BAD_REQUEST,
        )

    if not linked:
        return

    expected_model_id = linked[0].embedding_model_id
    if knowledge_base.embedding_model_id != expected_model_id:
        raise AppException(
            message="只能关联相同 Embedding 模型的知识库",
            code=status.HTTP_400_BAD_REQUEST,
        )
