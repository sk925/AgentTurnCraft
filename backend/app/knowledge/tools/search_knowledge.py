from __future__ import annotations

from langchain.tools import tool
from pydantic import BaseModel, Field

from app.database import transactional_session
from app.knowledge.agent_scope import get_agent_knowledge_scope
from app.knowledge.retriever import KnowledgeRetriever, format_retrieved_chunks


class SearchKnowledgeInput(BaseModel):
    query: str = Field(description="用于检索企业知识库的自然语言问题或关键词")


def build_search_knowledge_tool(agent_id: int):
    """为指定智能体创建知识库检索工具；未绑库时返回 None。"""

    @tool("search_knowledge", args_schema=SearchKnowledgeInput)
    def search_knowledge(query: str) -> str:
        """从智能体关联的企业知识库中检索与问题相关的文档片段。

        当用户询问合同内容、制度条款、产品说明、流程规范等可能已入库文档中的事实性问题时，必须优先调用本工具；
        不得在未检索前要求用户上传文件。
        """
        with transactional_session() as db:
            scope = get_agent_knowledge_scope(db, agent_id)
            if scope is None:
                return "当前智能体未关联知识库，无法检索企业文档。"
            chunks = KnowledgeRetriever(db).retrieve(query=query, scope=scope)
            return format_retrieved_chunks(chunks)

    return search_knowledge


def build_search_knowledge_tool_if_needed(agent_id: int):
    with transactional_session() as db:
        scope = get_agent_knowledge_scope(db, agent_id)
        if scope is None:
            return None
    return build_search_knowledge_tool(agent_id)
