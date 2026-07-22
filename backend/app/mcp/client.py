"""MCP 客户端：按 server / agent 加载工具。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from typing import Any

import httpx

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

_tools_by_server_id: dict[int, list[Any]] = {}
_server_lock = asyncio.Lock()
_cache_lock = threading.Lock()

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


def connection_from_row(row: Any) -> dict[str, Any]:
    """将 McpServer ORM 行转为 langchain-mcp-adapters 连接配置。"""
    transport = str(row.transport or "").strip().lower()
    if transport in ("http", "streamable_http"):
        config: dict[str, Any] = {
            "transport": transport,
            "url": (row.url or "").strip(),
        }
        if isinstance(row.headers, dict) and row.headers:
            config["headers"] = {str(k): str(v) for k, v in row.headers.items()}
        return config
    if transport == "stdio":
        return {
            "transport": "stdio",
            "command": (row.command or "").strip(),
            "args": list(row.args) if isinstance(row.args, list) else [],
        }
    raise ValueError(f"不支持的 transport: {transport}")


async def _fetch_tools_for_connection(server_name: str, connection: dict[str, Any]) -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    prepared = _prepare_connections({server_name: connection})
    client = MultiServerMCPClient(
        prepared,
        tool_name_prefix=False,
        handle_tool_errors=True,
    )
    try:
        return list(await client.get_tools())
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def load_server_tools(server_id: int) -> list[Any]:
    """加载并缓存指定 MCP server 的工具。"""
    from app.mcp.models import McpServer

    async with _server_lock:
        db = SessionLocal()
        try:
            row = db.query(McpServer).filter(McpServer.id == server_id).first()
            if row is None:
                with _cache_lock:
                    _tools_by_server_id.pop(server_id, None)
                return []
            if not row.enabled:
                with _cache_lock:
                    _tools_by_server_id.pop(server_id, None)
                return []
            connection = connection_from_row(row)
            server_name = row.name
        finally:
            db.close()

        tools = await _fetch_tools_for_connection(server_name, connection)
        with _cache_lock:
            _tools_by_server_id[server_id] = tools
        logger.info("MCP server id=%s loaded %d tool(s)", server_id, len(tools))
        return list(tools)


def refresh_server_tools_sync(server_id: int) -> list[Any]:
    """同步刷新某 server 工具缓存（供 API 调用）。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(load_server_tools(server_id))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(load_server_tools(server_id))).result(timeout=60)


def invalidate_server_tools(server_id: int | None = None) -> None:
    """清除工具缓存。"""
    with _cache_lock:
        if server_id is None:
            _tools_by_server_id.clear()
        else:
            _tools_by_server_id.pop(server_id, None)


def _get_cached_or_load(server_id: int) -> list[Any]:
    with _cache_lock:
        cached = _tools_by_server_id.get(server_id)
        if cached is not None:
            return list(cached)
    try:
        return refresh_server_tools_sync(server_id)
    except Exception as exc:
        logger.error("Failed to load MCP tools for server %s: %s", server_id, exc, exc_info=True)
        return []


def get_bound_mcp_server_ids(agent_id: int) -> list[int]:
    """查询智能体已绑定且启用的 MCP server id 列表。"""
    from app.chat.base.models import Agent

    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent is None:
            return []
        return [
            int(s.id)
            for s in (agent.mcp_servers or [])
            if bool(getattr(s, "enabled", True))
        ]
    finally:
        db.close()


def get_mcp_tools_for_agent(agent_id: int) -> list[Any]:
    """按智能体绑定返回 MCP 工具列表。"""
    if not settings.mcp_enabled:
        return []

    server_ids = get_bound_mcp_server_ids(agent_id)
    if not server_ids:
        return []

    tools: list[Any] = []
    for sid in server_ids:
        tools.extend(_get_cached_or_load(sid))
    return tools


async def init_mcp() -> None:
    """启动时初始化：清空缓存；若开启 MCP 则预热已启用 server。"""
    invalidate_server_tools()
    if not settings.mcp_enabled:
        logger.info("MCP disabled (mcp_enabled=false); DB-bound tools still require mcp_enabled=true")
        return

    from app.mcp.models import McpServer

    db = SessionLocal()
    try:
        rows = db.query(McpServer.id).filter(McpServer.enabled.is_(True)).all()
        server_ids = [int(r[0]) for r in rows]
    finally:
        db.close()

    if not server_ids:
        logger.info("MCP enabled but no enabled servers in DB")
        return

    for sid in server_ids:
        try:
            await load_server_tools(sid)
        except Exception as exc:
            logger.warning("MCP warmup failed for server %s: %s", sid, exc)


async def close_mcp() -> None:
    """关闭并清空 MCP 工具缓存。"""
    invalidate_server_tools()


def get_mcp_tools_sync() -> list[Any]:
    """兼容旧接口：返回所有已缓存工具（不推荐；请用 get_mcp_tools_for_agent）。"""
    with _cache_lock:
        tools: list[Any] = []
        for items in _tools_by_server_id.values():
            tools.extend(items)
        return tools
