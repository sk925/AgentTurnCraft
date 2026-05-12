from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.graph_rag.schemas import ChunkExtraction, QueryEntityParse
from app.group_chat.chat_common import llm

_EXTRACT_SYSTEM = """你是信息抽取模块。从用户给出的文本中抽取：
1) entities：文中出现的重要实体（人名、组织、地点、产品、概念、时间事件等），并给出粗略 entity_type。
2) relationships：仅当文本能明确支持时，输出 (source, relation, target) 三元组；relation 用简短中文谓词。
不要臆造文本中不存在的关系。若无关系，relationships 为空列表。"""

_QUERY_PARSE_SYSTEM = """分析用户问题，输出：
- entity_names：问题中涉及的专有名词或核心对象（尽量与文档可能用语一致，可多个）。
- is_global_query：若用户在问「全文/整体/主要/总结/大纲/主题/讲了什么」类宏观问题则为 true，否则 false。"""


class _CommunitySummary(BaseModel):
    summary: str = Field(description="社区主题摘要")


def extract_from_chunk(chunk_text: str) -> ChunkExtraction:
    structured = llm.with_structured_output(ChunkExtraction)
    messages = [
        SystemMessage(content=_EXTRACT_SYSTEM),
        HumanMessage(content=chunk_text),
    ]
    try:
        out = structured.invoke(messages)
        if isinstance(out, ChunkExtraction):
            return out
    except Exception:
        pass
    return ChunkExtraction()


def parse_question(question: str) -> QueryEntityParse:
    structured = llm.with_structured_output(QueryEntityParse)
    messages = [
        SystemMessage(content=_QUERY_PARSE_SYSTEM),
        HumanMessage(content=question),
    ]
    try:
        out = structured.invoke(messages)
        if isinstance(out, QueryEntityParse):
            return out
    except Exception:
        pass
    return QueryEntityParse(entity_names=[], is_global_query=False)


def summarize_community(entity_names: list[str], chunk_excerpt: str) -> str:
    structured = llm.with_structured_output(_CommunitySummary)
    prompt = f"""下列实体属于同一关联社区：{', '.join(entity_names[:40])}
下列是原文摘录（可能不完整），请用 2-5 句中文概括该社区在材料中讨论的主题与要点。不要编造。"""
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=chunk_excerpt[:12000]),
    ]
    try:
        out = structured.invoke(messages)
        if isinstance(out, _CommunitySummary):
            return out.summary.strip()
    except Exception:
        pass
    return ""


def answer_with_context(question: str, context: str) -> str:
    """基于检索到的上下文生成答案（非结构化，纯文本）。"""
    messages = [
        SystemMessage(
            content="你是问答助手。仅依据用户提供的「知识库材料」作答；若材料不足以回答，请明确说明，不要编造。"
        ),
        HumanMessage(
            content=f"【知识库材料】\n{context}\n\n【问题】\n{question}"
        ),
    ]
    try:
        msg = llm.invoke(messages)
        return (msg.content or "").strip()
    except Exception:
        return "生成答案时发生错误，请稍后重试。"
