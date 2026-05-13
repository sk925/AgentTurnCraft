import asyncio
import json
from typing import Annotated, Any

from app.auth import get_current_user_id
from app.manage.login_session import assert_user_login_session
from app.manage.rbac_api import load_manage_user
from app.group_chat.chat_common import SessionType, SpearkerRecord, WindowState
from app.group_chat.chat_graph import get_checkpointer, get_window_graph
from app.group_chat.event_publisher import EventPublisher
from sqlalchemy import or_

from app.constants import RESOURCE_TYPE_BUILTIN
from app.models import Agent, Group
from app.models.upload_file import UploadFile as UploadFileModel
from app.session.service import get_or_create_session
from app.utils import snowflake
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from app.database import SessionLocal, get_db
from app.models.agent_log import AgentLogService


router = APIRouter(prefix="/chat_window")

# WebSocket 长连接期间定期重验令牌（秒）；到期/吊销/禁用时中断对话
_WS_AUTH_RECHECK_INTERVAL_S = 8.0


def _ws_close_reason(detail: object) -> str:
    """WebSocket close reason 长度受限，截断为安全短串。"""
    s = detail if isinstance(detail, str) else "认证失败"
    return s[:120]


def _http_exc_detail(exc: HTTPException) -> str:
    d = exc.detail
    return d if isinstance(d, str) else str(d)


def verify_websocket_token(token: str, *, expected_member_id: int | None = None) -> int:
    """校验 JWT、user_login 行未吊销、用户存在且启用。expected_member_id 传入时须与令牌 sub 一致。"""
    db_verify = SessionLocal()
    try:
        uid = assert_user_login_session(db_verify, token)
        if expected_member_id is not None and int(uid) != int(expected_member_id):
            raise HTTPException(status_code=401, detail="令牌与用户不一致")
        u = load_manage_user(db_verify, uid)
        if u is None or not u.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return int(uid)
    finally:
        db_verify.close()


def _normalize_file_ids(raw: Any) -> list[int]:
    """解析 WebSocket / JSON 中的 file_ids（支持 int 或字符串形式的雪花 id）。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        if item is None:
            continue
        try:
            out.append(int(str(item).strip()))
        except (TypeError, ValueError):
            continue
    return out


def _build_attachment_context(db: Session, member_id: int, file_ids: list[int]) -> str:
    """按 id 拉取当前用户可见的上传文件元数据，供发言人 prompt 使用（不含文件正文）。"""
    if not file_ids:
        return ""
    rows = (
        db.query(UploadFileModel)
        .filter(UploadFileModel.id.in_(file_ids), UploadFileModel.user_id == member_id)
        .all()
    )
    if not rows:
        return ""
    by_id = {int(r.id): r for r in rows}
    lines = [
        "## 本轮用户附件（仅元数据；正文请通过工具按 file_id 读取）",
    ]
    for fid in file_ids:
        r = by_id.get(int(fid))
        if r:
            lines.append(
                f"- file_id: {r.id}\n  file_name: {r.file_name}\n  file_type: {r.file_type}\n  file_size: {r.file_size} bytes"
            )
    return "\n".join(lines)


class WindowChatRequest(BaseModel):
    """窗口聊天请求"""

    user_message: str = ""
    org_id: int
    session_id: str | None
    round_id: str | None
    session_type: SessionType = SessionType.CHAT
    group_id: int | None = Field(
        default=None,
        description="群聊时可选：仅允许该群组内的智能体进入候选池",
    )
    file_ids: list[int] | None = Field(
        default=None,
        description="文件ID列表",
    )

    @field_validator("file_ids", mode="before")
    @classmethod
    def _coerce_file_ids(cls, v: Any) -> list[int] | None:
        if v is None:
            return None
        parsed = _normalize_file_ids(v)
        return parsed or None


def _build_window_state(
    window_chat_request: WindowChatRequest,
    member_id: int,
    db: Session,
    checkpointer,
) -> tuple[WindowState, CompiledStateGraph, dict]:
    """构建 window_state、编译后的图、以及 config。供 HTTP 和 WebSocket 共用。"""
    session_id = window_chat_request.session_id
    if not session_id:
        session_id = str(snowflake.get_snowflake_id())

    file_ids = _normalize_file_ids(window_chat_request.file_ids)
    attachment_context = _build_attachment_context(db, member_id, file_ids) if file_ids else ""

    raw_user_message = (window_chat_request.user_message or "").strip()
    effective_user_message = raw_user_message
    if not effective_user_message and file_ids:
        effective_user_message = "请根据我上传的附件处理。"

    get_or_create_session(
        db=db,
        session_id=session_id,
        member_id=member_id,
        user_message=raw_user_message or effective_user_message,
        session_type=window_chat_request.session_type.value,
    )

    round_id = snowflake.get_snowflake_id()

    # 查询可用智能体
    if window_chat_request.session_type == SessionType.GROUP_CHAT and window_chat_request.group_id is not None:
        group = db.query(Group).filter(Group.id == window_chat_request.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="群组不存在")
        if group.resource_type != RESOURCE_TYPE_BUILTIN and group.user_id != member_id:
            raise HTTPException(status_code=404, detail="群组不存在")
        all_agents = list(group.agents or [])
        if not all_agents:
            raise HTTPException(status_code=400, detail="该群组下暂无智能体，请先在群组管理中添加成员")
    else:
        all_agents = (
            db.query(Agent)
            .filter(
                or_(Agent.user_id == member_id, Agent.resource_type == RESOURCE_TYPE_BUILTIN),
            )
            .all()
        )

    all_agents_data = [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "prompt": agent.prompt,
        }
        for agent in all_agents
    ]

    config = {"configurable": {"thread_id": session_id}}
    window_state: WindowState = {
        "session_id": session_id,
        "round_id": round_id,
        "user_message": effective_user_message,
        "file_ids": file_ids,
        "attachment_context": attachment_context,
        "member_id": member_id,
        "all_agents": all_agents_data,
        "user_profile": {"member_id": member_id, "org_id": window_chat_request.org_id, "member_role": "STUDENT"},
    }
    window_graph: CompiledStateGraph = get_window_graph(checkpointer)

    AgentLogService.save_user_question(
        user_id=member_id,
        session_id=session_id,
        round_id=str(round_id),
        content=raw_user_message,
        file_ids=file_ids if file_ids else None,
    )

    return window_state, window_graph, config


async def _relay_redis_pubsub_to_websocket(
    websocket: WebSocket,
    publisher: EventPublisher,
    channel: str,
    send_lock: asyncio.Lock,
    token: str,
    member_id: int,
) -> None:
    """在独立任务中把 Redis 频道转发到 WebSocket，避免阻塞 receive_text 主循环。"""
    pubsub = publisher.redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        while True:
            event = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_WS_AUTH_RECHECK_INTERVAL_S,
            )
            if event is None:
                try:
                    verify_websocket_token(token, expected_member_id=member_id)
                except HTTPException as e:
                    d = _http_exc_detail(e)
                    try:
                        async with send_lock:
                            await websocket.send_json({"event": "auth_error", "message": d})
                    except Exception:
                        pass
                    try:
                        await websocket.close(code=4001, reason=_ws_close_reason(d))
                    except Exception:
                        pass
                    return
                continue
            if event["type"] != "message":
                continue
            data = json.loads(event["data"])
            try:
                async with send_lock:
                    await websocket.send_json(data)
            except Exception:
                break
            if data.get("event") in ("finished", "error"):
                break
    finally:
        await pubsub.unsubscribe(channel)


@router.post("/chat")
async def window_chat(
    window_chat_request: WindowChatRequest,
    request: Request,
    member_id: Annotated[int, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    """非流式 HTTP 端点：触发 LangGraph 执行并立即返回 session_id/round_id。
    流式事件通过 WebSocket 端点 /chat_window/ws 下发。
    """
    window_state, window_graph, config = _build_window_state(
        window_chat_request, member_id, db, request.app.state.checkpointer
    )

    publisher = EventPublisher()
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    await publisher.set_active_round(session_id, round_id)
    await publisher.set_round_status(session_id, round_id, "running")

    # 后台执行（不等待），通过 Redis 下发事件
    asyncio.create_task(_execute_chat_round(window_graph, window_state, config, publisher))

    return JSONResponse({"session_id": session_id, "round_id": round_id})


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket 端点：先握手，首条客户端消息须为 JSON `{type:\"auth\", token:\"<JWT>\"}`，验过后再处理 chat/catchup/ping。"""
    await websocket.accept()

    publisher = EventPublisher()
    try:
        checkpointer = get_checkpointer()
    except RuntimeError as e:
        await websocket.send_json({"event": "error", "message": f"服务未就绪: {e}"})
        await websocket.close(code=1011, reason="checkpointer 未初始化")
        return

    ws_send_lock = asyncio.Lock()

    async def send_ws(payload: dict) -> None:
        async with ws_send_lock:
            await websocket.send_json(payload)

    # 首包鉴权（token 不出现在 URL，避免进访问日志）
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
    except asyncio.TimeoutError:
        await send_ws({"event": "auth_error", "message": "认证超时，请重连"})
        await websocket.close(code=4001, reason="认证超时")
        return
    except WebSocketDisconnect:
        return

    try:
        first = json.loads(raw)
    except json.JSONDecodeError:
        await send_ws({"event": "auth_error", "message": "无效的 JSON 格式"})
        await websocket.close(code=4001, reason="无效 JSON")
        return

    if not isinstance(first, dict) or first.get("type") != "auth":
        await send_ws({
            "event": "auth_error",
            "message": '首条消息须为认证：{"type":"auth","token":"<访问令牌>"}',
        })
        await websocket.close(code=4001, reason="需要 auth")
        return

    token_raw = first.get("token")
    if not token_raw or not str(token_raw).strip():
        await send_ws({"event": "auth_error", "message": "缺少 token"})
        await websocket.close(code=4001, reason="缺少 token")
        return

    token = str(token_raw).strip()

    try:
        member_id = verify_websocket_token(token)
    except HTTPException as e:
        detail = _http_exc_detail(e)
        await send_ws({"event": "auth_error", "message": detail})
        await websocket.close(code=4001, reason=_ws_close_reason(detail))
        return

    await send_ws({"event": "authenticated"})

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await send_ws({"event": "error", "message": "无效的 JSON 格式"})
                continue

            try:
                verify_websocket_token(token, expected_member_id=member_id)
            except HTTPException as e:
                d = _http_exc_detail(e)
                await send_ws({"event": "auth_error", "message": d})
                await websocket.close(code=4001, reason=_ws_close_reason(d))
                return

            msg_type = message.get("type")

            if msg_type == "chat":
                # 每次消息使用独立的 DB session
                db = SessionLocal()
                try:
                    window_chat_request = WindowChatRequest(
                        user_message=message.get("user_message") or "",
                        org_id=message.get("org_id", 1),
                        session_id=message.get("session_id"),
                        round_id=None,
                        session_type=message.get("session_type", "chat"),
                        group_id=message.get("group_id"),
                        file_ids=_normalize_file_ids(message.get("file_ids")) or None,
                    )
                    try:
                        window_state, window_graph, config = _build_window_state(
                            window_chat_request, member_id, db, checkpointer
                        )
                    except HTTPException as e:
                        await send_ws({"event": "error", "message": e.detail})
                        continue

                    session_id = str(window_state["session_id"])
                    round_id = str(window_state["round_id"])

                    await publisher.set_active_round(session_id, round_id)
                    await publisher.set_round_status(session_id, round_id, "running")

                    # 先订阅 Redis，再启动 LangGraph 执行（避免丢失事件）
                    channel = publisher.channel_name(session_id, round_id)
                    pubsub = publisher.redis.pubsub()
                    await pubsub.subscribe(channel)

                    # 后台执行 LangGraph
                    task = asyncio.create_task(
                        _execute_chat_round(window_graph, window_state, config, publisher)
                    )

                    # 将 Redis Pub/Sub 事件转发到 WebSocket（超时则重验令牌，过期或登出则中断）
                    auth_failed = False
                    auth_fail_detail: str | None = None
                    try:
                        while True:
                            event = await pubsub.get_message(
                                ignore_subscribe_messages=True,
                                timeout=_WS_AUTH_RECHECK_INTERVAL_S,
                            )
                            if event is None:
                                try:
                                    verify_websocket_token(token, expected_member_id=member_id)
                                except HTTPException as e:
                                    task.cancel()
                                    auth_failed = True
                                    auth_fail_detail = _http_exc_detail(e)
                                    break
                                continue
                            if event.get("type") != "message":
                                continue
                            data = json.loads(event["data"])
                            await send_ws(data)
                            if data.get("event") in ("finished", "error"):
                                break
                    finally:
                        await pubsub.unsubscribe(channel)
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    if auth_failed:
                        await publisher.set_round_status(session_id, round_id, "failed")
                        await publisher.clear_active_round(session_id)
                        await send_ws({"event": "auth_error", "message": auth_fail_detail or "认证失败"})
                        await websocket.close(code=4001, reason=_ws_close_reason(auth_fail_detail))
                        return

                    await publisher.set_round_status(session_id, round_id, "completed")
                    await publisher.clear_active_round(session_id)
                finally:
                    db.close()

            elif msg_type == "catchup":
                session_id = message.get("session_id")
                if not session_id:
                    await send_ws({"event": "error", "message": "缺少 session_id"})
                    continue

                active_round = await publisher.get_active_round(session_id)
                if not active_round:
                    await send_ws({
                        "event": "catchup_round",
                        "round_id": None,
                        "events": [],
                        "status": "no_active_round",
                    })
                    continue

                status = await publisher.get_round_status(session_id, active_round)
                events = await publisher.get_round_events(session_id, active_round)

                await send_ws({
                    "event": "catchup_round",
                    "round_id": active_round,
                    "events": events,
                    "status": status or "unknown",
                })

                # 如果 round 仍在运行，在后台订阅转发；若在此处阻塞 listen()，主循环无法 receive_text，后续 chat 永远进不来
                if status == "running":
                    channel = publisher.channel_name(session_id, active_round)
                    asyncio.create_task(
                        _relay_redis_pubsub_to_websocket(
                            websocket, publisher, channel, ws_send_lock, token, member_id
                        )
                    )

            elif msg_type == "ping":
                await send_ws({"event": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 捕获未预期的异常，避免 1006
        try:
            async with ws_send_lock:
                await websocket.send_json({"event": "error", "message": f"服务端内部错误: {e}"})
        except Exception:
            pass


async def _execute_chat_round(
    window_graph: CompiledStateGraph,
    window_state: dict,
    config: dict,
    publisher: EventPublisher,
):
    """执行一轮 LangGraph 群聊，所有事件通过 Redis 下发。"""
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    await publisher.publish(session_id, round_id, {
        "event": "start",
        "session_id": session_id,
        "round_id": round_id,
    })

    round_failed = False
    try:
        async for chunk in window_graph.astream(
            window_state, config=config, stream_mode=["messages", "updates", "custom"]
        ):
            # 兼容 (mode, data) 与 (namespace, mode, data)
            if isinstance(chunk, tuple) and len(chunk) == 2:
                mode, data = chunk
            elif isinstance(chunk, tuple) and len(chunk) == 3:
                _, mode, data = chunk
            else:
                continue

            if mode == "updates":
                if data.get("select_agents_node"):
                    payload = _build_select_agents_payload(data["select_agents_node"])
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                if data.get("select_speaker_node"):
                    payload = _build_select_speaker_payload(data["select_speaker_node"])
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                if data.get("speak_node"):
                    speak_data = data["speak_node"]
                    payload = _build_speaker_payload(speak_data)
                    if payload:
                        await publisher.publish(session_id, round_id, payload)
                    if speak_data.get("finished", False):
                        await publisher.publish(session_id, round_id, {
                            "event": "speaker_finished",
                            "answer": speak_data.get("answer", ""),
                            "finish_reason": speak_data.get("finish_reason", ""),
                        })
            elif mode == "custom":
                # speak_node 内层流式增量已通过 EventPublisher 直接发送
                # 这里做兼容：如果还有 custom 事件未处理，直接转发 data
                await publisher.publish(session_id, round_id, data)
            elif mode == "messages":
                # 过滤 select_* 节点的 LLM 消息（这些已在 updates 中处理）
                if not isinstance(data, tuple) or len(data) < 2:
                    continue
                meta = data[1]
                if not isinstance(meta, dict):
                    continue
                langgraph_node = meta.get("langgraph_node", "")
                if langgraph_node in ["select_agents_node", "select_speaker_node"]:
                    continue

    except Exception as e:
        round_failed = True
        await publisher.publish(session_id, round_id, {
            "event": "error",
            "message": str(e),
        })
        raise
    finally:
        # 避免异常或 HTTP  fire-and-forget 路径下 Redis 长期停留在 running / 占用 active_round
        await publisher.set_round_status(
            session_id, round_id, "failed" if round_failed else "completed"
        )
        await publisher.clear_active_round(session_id)


def _build_select_agents_payload(data: dict) -> dict | None:
    """构建 select_agents_node 的事件 payload"""
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    else:
        return {
            "event": "create_group",
            "group_members": [
                {"id": agent["id"], "name": agent["name"]}
                for agent in data.get("group_members", [])
            ],
            "select_reason": data.get("select_reason", ""),
        }


def _build_select_speaker_payload(data: dict) -> dict | None:
    """构建 select_speaker_node 的事件 payload"""
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    else:
        payload = dict(data)
        payload.pop("session_messages", None)
        payload["event"] = "select_speaker"
        return payload


def _build_speaker_payload(data: dict) -> dict | None:
    """构建 speak_node 的事件 payload"""
    transcript: list[SpearkerRecord] = data.get("transcript", [])
    if transcript:
        record = transcript[-1]
        record["event"] = "speaker"
        return record
    return None
