from __future__ import annotations

from typing import Any

from app.tools.ask_user import ask_user_question
from app.tools.parse_file import FileParser
from langchain_community.tools import DuckDuckGoSearchRun

_web_search: DuckDuckGoSearchRun | None = None


def get_web_search_tool() -> DuckDuckGoSearchRun:
    global _web_search
    if _web_search is None:
        _web_search = DuckDuckGoSearchRun()
    return _web_search


def get_default_agent_tools() -> list[Any]:
    """宿主侧默认工具集（FileParser / web_search 不受 Docker 沙箱隔离）。"""
    return [ask_user_question, FileParser(), get_web_search_tool()]


def get_agent_tools(agent_id: int) -> list[Any]:
    """按智能体装配工具；已绑知识库时追加 search_knowledge。"""
    tools: list[Any] = get_default_agent_tools()
    from app.knowledge.tools import build_search_knowledge_tool_if_needed

    kb_tool = build_search_knowledge_tool_if_needed(agent_id)
    if kb_tool is not None:
        tools.append(kb_tool)
    return tools
