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
