from __future__ import annotations

from typing import Any

from app.tools.ask_user import ask_user_question
from app.tools.fetch_webpage import fetch_webpage
from app.tools.get_current_time import get_current_time
from app.tools.parse_file import FileParser
from app.mcp.client import get_mcp_tools_sync
from langchain_community.tools import DuckDuckGoSearchRun

_web_search: DuckDuckGoSearchRun | None = None


def get_web_search_tool() -> DuckDuckGoSearchRun:
    global _web_search
    if _web_search is None:
        _web_search = DuckDuckGoSearchRun()
    return _web_search


def get_default_agent_tools() -> list[Any]:
    """宿主侧默认工具集（FileParser / web_search / fetch_webpage 不受 Docker 沙箱隔离）。"""
    return [
        ask_user_question,
        get_current_time,
        FileParser(),
        fetch_webpage,
        get_web_search_tool(),
    ]


def get_agent_tools(agent_id: int) -> list[Any]:
    """按智能体装配工具；已绑知识库时追加 search_knowledge；全局 MCP 工具追加在末尾。"""
    tools: list[Any] = get_default_agent_tools()
    from app.knowledge.tools import build_search_knowledge_tool_if_needed

    kb_tool = build_search_knowledge_tool_if_needed(agent_id)
    if kb_tool is not None:
        tools.append(kb_tool)
    tools.extend(get_mcp_tools_sync())
    return tools
