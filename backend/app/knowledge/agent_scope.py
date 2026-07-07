from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.chat.base.models import Agent
from app.exceptions import AppException
from app.knowledge.models import KnowledgeBase
from fastapi import status


@dataclass(frozen=True, slots=True)
class AgentKnowledgeScope:
    """智能体当前可用于检索的知识库范围。"""

    knowledge_base_ids: tuple[int, ...]
    embedding_model_id: int
    knowledge_base_names: dict[int, str]


def get_agent_knowledge_scope(db: Session, agent_id: int) -> AgentKnowledgeScope | None:
    """读取智能体已绑定且已配置 Embedding 的知识库；无绑定则返回 None。"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if agent is None or not agent.knowledge_bases:
        return None

    knowledge_bases: list[KnowledgeBase] = list(agent.knowledge_bases)
    embedding_model_id = knowledge_bases[0].embedding_model_id
    if embedding_model_id is None:
        return None

    for kb in knowledge_bases[1:]:
        if kb.embedding_model_id != embedding_model_id:
            raise AppException(
                message="智能体关联的知识库 Embedding 模型不一致，请检查绑库配置",
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    return AgentKnowledgeScope(
        knowledge_base_ids=tuple(kb.id for kb in knowledge_bases),
        embedding_model_id=int(embedding_model_id),
        knowledge_base_names={kb.id: kb.name for kb in knowledge_bases},
    )
