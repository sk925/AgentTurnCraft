from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_client: Any | None = None
_tools: list[Any] | None = None
_init_lock = asyncio.Lock()

_HTTP_TRANSPORTS = frozenset({"http", "streamable_http", "streamable-http"})


def _direct_mcp_http_client_factory(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """创建不走系统代理的 httpx 客户端，避免本地 MCP 被 HTTP_PROXY 转发后 502。"""
    from langchain_mcp_adapters.sessions import (
        DEFAULT_STREAMABLE_HTTP_SSE_READ_TIMEOUT,
        DEFAULT_STREAMABLE_HTTP_TIMEOUT,
    )

    kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "trust_env": False,
    }
    kwargs["timeout"] = timeout or httpx.Timeout(
        DEFAULT_STREAMABLE_HTTP_TIMEOUT,
        read=DEFAULT_STREAMABLE_HTTP_SSE_READ_TIMEOUT,
    )
    if headers is not None:
        kwargs["headers"] = headers
    if auth is not None:
        kwargs["auth"] = auth
    return httpx.AsyncClient(**kwargs)


def _prepare_connections(connections: dict[str, Any]) -> dict[str, Any]:
    prepared: dict[str, Any] = {}
    for name, config in connections.items():
        if not isinstance(config, dict):
            prepared[name] = config
            continue
        merged = dict(config)
        transport = str(merged.get("transport", "")).lower()
        if transport in _HTTP_TRANSPORTS and "httpx_client_factory" not in merged:
            merged["httpx_client_factory"] = _direct_mcp_http_client_factory
        prepared[name] = merged
    return prepared


def _mcp_enabled() -> bool:
    return settings.mcp_enabled


def _parse_mcp_servers() -> dict[str, Any]:
    raw = settings.mcp_servers
    if isinstance(raw, dict):
        return raw
    if not raw or not str(raw).strip():
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError as exc:
        logger.error("Invalid MCP_SERVERS JSON: %s", exc)
        return {}
    if not isinstance(parsed, dict):
        logger.error("MCP_SERVERS must be a JSON object, got %s", type(parsed).__name__)
        return {}
    return parsed


async def init_mcp() -> list[Any]:
    """启动时加载 MCP 工具；未启用或配置为空时返回空列表。"""
    global _client, _tools

    if not _mcp_enabled():
        logger.info("MCP disabled (mcp_enabled=false)")
        _tools = []
        return _tools

    async with _init_lock:
        if _tools is not None:
            return _tools

        connections = _prepare_connections(_parse_mcp_servers())
        if not connections:
            logger.info("MCP enabled but no servers configured")
            _tools = []
            return _tools

        from langchain_mcp_adapters.client import MultiServerMCPClient

        _client = MultiServerMCPClient(
            connections,
            tool_name_prefix=True,
            handle_tool_errors=True,
        )
        try:
            _tools = await _client.get_tools()
        except Exception as exc:
            logger.error(
                "MCP initialization failed (%s); continuing without MCP tools",
                exc,
                exc_info=True,
            )
            close = getattr(_client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            _client = None
            _tools = []
            return _tools

        logger.info(
            "MCP initialized: %d server(s), %d tool(s)",
            len(connections),
            len(_tools),
        )
        return _tools


async def close_mcp() -> None:
    """关闭 MCP 客户端并释放资源。"""
    global _client, _tools

    async with _init_lock:
        if _client is not None:
            close = getattr(_client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        _client = None
        _tools = None


def get_mcp_tools_sync() -> list[Any]:
    """同步获取已加载的 MCP 工具（供 AgentRuntime.build 使用）。"""
    if _tools is not None:
        return list(_tools)
    if not _mcp_enabled():
        return []

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(init_mcp())

    logger.warning("MCP tools requested before init_mcp(); returning empty list")
    return []
