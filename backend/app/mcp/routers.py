"""MCP Server 管理 API。"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.chat.base.schemas import (
    ApiResponse,
    McpServerCreate,
    McpServerResponse,
    McpServerUpdate,
    PaginatedData,
    success_response,
)
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.manage.deps import require_manage_roles
from app.manage.models import User
from app.mcp.client import invalidate_server_tools, refresh_server_tools_sync
from app.mcp.models import McpServer
from app.query_access import get_mcp_server_if_readable, list_mcp_servers_page

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_TRANSPORTS = frozenset({"http", "streamable_http", "stdio"})


def _to_response(row: McpServer) -> McpServerResponse:
    """ORM → 响应模型（含 headers 脱敏）。"""
    return McpServerResponse.model_validate(row)


def _validate_connection_fields(
    *,
    transport: str,
    url: str | None,
    command: str | None,
    args: list[str] | None,
    headers: dict[str, str] | None,
) -> None:
    transport = transport.strip().lower()
    if transport not in _ALLOWED_TRANSPORTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 transport，可选：{', '.join(sorted(_ALLOWED_TRANSPORTS))}",
        )

    if transport in ("http", "streamable_http"):
        if not (url or "").strip():
            raise HTTPException(status_code=400, detail="HTTP 类传输必须填写 url")
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(status_code=400, detail="url 必须是有效的 http/https 地址")
    else:
        if not (command or "").strip():
            raise HTTPException(status_code=400, detail="stdio 传输必须填写 command")
        if args is not None and not isinstance(args, list):
            raise HTTPException(status_code=400, detail="args 必须是字符串数组")

    if headers is not None and not isinstance(headers, dict):
        raise HTTPException(status_code=400, detail="headers 必须是对象")


def _normalize_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if len(cleaned) > 255:
        raise HTTPException(status_code=400, detail="名称过长")
    return cleaned


def _evict_bound_agents(row: McpServer) -> None:
    agent_ids = [a.id for a in (row.agents or [])]
    if not agent_ids:
        return
    from app.harness import evict_agent_runtime_cache_for_agent_ids

    evict_agent_runtime_cache_for_agent_ids(agent_ids)


@router.get("/mcp-servers", response_model=ApiResponse[PaginatedData[McpServerResponse]])
def list_mcp_servers(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
    q: Annotated[str | None, Query(max_length=200)] = None,
    type: Annotated[int | None, Query(ge=1, le=2, description="1 内置 2 自定义")] = None,
):
    """分页获取 MCP 服务列表。"""
    if type is not None and type not in (RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM):
        raise HTTPException(status_code=400, detail="无效的类型筛选")

    items, total = list_mcp_servers_page(
        db,
        current_user,
        page=page,
        page_size=page_size,
        q=q,
        resource_type=type,
    )
    return success_response(
        PaginatedData[McpServerResponse](
            items=[_to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/mcp-servers", response_model=ApiResponse[McpServerResponse])
def create_mcp_server(
    body: McpServerCreate,
    current_user: Annotated[User, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    """新增 MCP 服务。"""
    name = _normalize_name(body.name)
    transport = body.transport.strip().lower()
    _validate_connection_fields(
        transport=transport,
        url=body.url,
        command=body.command,
        args=body.args,
        headers=body.headers,
    )

    exists = db.query(McpServer.id).filter(McpServer.name == name).first()
    if exists:
        raise HTTPException(status_code=409, detail="MCP 服务名称已存在")

    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_superuser else RESOURCE_TYPE_CUSTOM
    row = McpServer(
        user_id=current_user.id,
        name=name,
        description=(body.description or "").strip() or None,
        transport=transport,
        url=(body.url or "").strip() or None,
        command=(body.command or "").strip() or None,
        args=body.args,
        headers=body.headers,
        enabled=bool(body.enabled),
        resource_type=resource_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if row.enabled:
        try:
            refresh_server_tools_sync(row.id)
        except Exception as exc:
            logger.warning("MCP server %s created but tool prefetch failed: %s", row.id, exc)

    return success_response(_to_response(row))


@router.get("/mcp-servers/{mcp_server_id}", response_model=ApiResponse[McpServerResponse])
def get_mcp_server(
    mcp_server_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    row = get_mcp_server_if_readable(db, mcp_server_id, current_user)
    if not row:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    return success_response(_to_response(row))


@router.put("/mcp-servers/{mcp_server_id}", response_model=ApiResponse[McpServerResponse])
def update_mcp_server(
    mcp_server_id: int,
    body: McpServerUpdate,
    current_user: Annotated[User, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    row = db.query(McpServer).filter(McpServer.id == mcp_server_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权编辑：仅创建人可修改该 MCP 服务")

    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        data["name"] = _normalize_name(data["name"] or "")
        conflict = (
            db.query(McpServer.id)
            .filter(McpServer.name == data["name"], McpServer.id != mcp_server_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="MCP 服务名称已存在")

    transport = str(data.get("transport", row.transport)).strip().lower()
    url = data["url"] if "url" in data else row.url
    command = data["command"] if "command" in data else row.command
    args = data["args"] if "args" in data else row.args
    headers = data["headers"] if "headers" in data else row.headers
    _validate_connection_fields(
        transport=transport,
        url=url,
        command=command,
        args=args if isinstance(args, list) or args is None else None,
        headers=headers if isinstance(headers, dict) or headers is None else None,
    )
    data["transport"] = transport

    if "description" in data and data["description"] is not None:
        data["description"] = str(data["description"]).strip() or None
    if "url" in data and data["url"] is not None:
        data["url"] = str(data["url"]).strip() or None
    if "command" in data and data["command"] is not None:
        data["command"] = str(data["command"]).strip() or None

    for field, value in data.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)

    invalidate_server_tools(row.id)
    _evict_bound_agents(row)
    if row.enabled:
        try:
            refresh_server_tools_sync(row.id)
        except Exception as exc:
            logger.warning("MCP server %s updated but tool refresh failed: %s", row.id, exc)

    return success_response(_to_response(row))


@router.delete("/mcp-servers/{mcp_server_id}")
def delete_mcp_server(
    mcp_server_id: int,
    current_user: Annotated[User, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    row = db.query(McpServer).filter(McpServer.id == mcp_server_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该 MCP 服务")

    if row.agents:
        raise HTTPException(status_code=400, detail="该 MCP 服务仍有关联的智能体，请先解关联")

    invalidate_server_tools(row.id)
    db.delete(row)
    db.commit()
    return success_response({"deleted": True}, message="删除成功")


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    name = str(getattr(tool, "name", "") or "")
    description = getattr(tool, "description", None)
    if description is not None:
        description = str(description).strip() or None
    args_schema: Any = getattr(tool, "args_schema", None)
    schema: dict[str, Any] | None = None
    if args_schema is not None:
        try:
            if hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            elif isinstance(args_schema, dict):
                schema = args_schema
        except Exception:
            schema = None
    return {
        "name": name,
        "description": description,
        "args_schema": schema,
        "parameters": _schema_to_parameters(schema),
    }


def _schema_to_parameters(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    """将 JSON Schema / args_schema 展平为前端友好的参数列表。"""
    if not schema or not isinstance(schema, dict):
        return []
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    required = {str(x) for x in (schema.get("required") or []) if x is not None}
    params: list[dict[str, Any]] = []
    for key, prop in props.items():
        if not isinstance(prop, dict):
            continue
        type_val = prop.get("type")
        if isinstance(type_val, list):
            type_str = " | ".join(str(t) for t in type_val)
        elif type_val is None and "anyOf" in prop:
            type_str = "any"
        else:
            type_str = str(type_val) if type_val is not None else "any"
        params.append(
            {
                "name": str(key),
                "type": type_str,
                "title": prop.get("title"),
                "description": prop.get("description"),
                "default": prop.get("default", None) if "default" in prop else None,
                "has_default": "default" in prop,
                "required": str(key) in required,
                "maximum": prop.get("maximum"),
                "minimum": prop.get("minimum"),
            }
        )
    return params


@router.get("/mcp-servers/{mcp_server_id}/tools", response_model=ApiResponse[dict])
def list_mcp_server_tools(
    mcp_server_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """拉取并返回该 MCP 服务当前可用的工具列表。"""
    row = get_mcp_server_if_readable(db, mcp_server_id, current_user)
    if not row:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    if not row.enabled:
        return success_response(
            {"tools": [], "disabled": True},
            message="服务已禁用，无法拉取工具",
        )
    try:
        tools = refresh_server_tools_sync(row.id)
        payload = [_tool_to_dict(t) for t in tools]
        return success_response(
            {"tools": payload, "disabled": False, "tool_count": len(payload)},
            message="ok",
        )
    except Exception as exc:
        logger.warning("MCP list tools failed for %s: %s", mcp_server_id, exc)
        raise HTTPException(status_code=502, detail=f"拉取工具失败: {exc}") from exc


@router.post("/mcp-servers/{mcp_server_id}/test", response_model=ApiResponse[dict])
def test_mcp_server(
    mcp_server_id: int,
    current_user: Annotated[User, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    """探测 MCP 连通性并返回工具数量。"""
    row = get_mcp_server_if_readable(db, mcp_server_id, current_user)
    if not row:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    try:
        tools = refresh_server_tools_sync(row.id)
        names = [getattr(t, "name", "") for t in tools]
        return success_response(
            {"ok": True, "tool_count": len(tools), "tool_names": names},
            message="连接成功",
        )
    except Exception as exc:
        logger.warning("MCP test failed for %s: %s", mcp_server_id, exc)
        raise HTTPException(status_code=502, detail=f"连接失败: {exc}") from exc
