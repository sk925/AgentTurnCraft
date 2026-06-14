"""共用对话 HTTP / WebSocket 路由（/api/chat/*）。"""

import asyncio
import json
import logging
from typing import Annotated

from app.auth import get_current_user_id
from app.chat.orchestration import (
    build_window_state_for_session_type,
    execute_chat_round_for_session_type,
)
from app.chat.shared.checkpointer import get_checkpointer
from app.chat.shared.event_publisher import EventPublisher
from app.chat.shared.window_models import WindowChatRequest, normalize_window_file_ids
from app.database import SessionLocal, get_db
from app.manage.login_session import assert_user_login_session
from app.manage.rbac_api import load_manage_user
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

router = APIRouter(prefix="/chat")

logger = logging.getLogger(__name__)


def _consume_task_exception(task: asyncio.Task) -> None:
    """避免 fire-and-forget 任务异常未被 retrieve 时 asyncio 报 Task exception was never retrieved。"""
    if not task.done() or task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


# WebSocket 长连接期间定期重验令牌（秒）；到期/吊销/禁用时中断对话
_WS_AUTH_RECHECK_INTERVAL_S = 8.0

# 单成员发言结束时 execute_group_chat_round 只发 speaker_finished（不发 finished），内层 pubsub 循环须据此退出以继续 receive_text
_WS_ROUND_DONE_EVENTS = frozenset({"finished", "error", "speaker_finished","main_interrupt"})


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


async def _relay_redis_pubsub_to_websocket(
    websocket: WebSocket,
    publisher: EventPublisher,
    channel: str,
    send_lock: asyncio.Lock,
    token: str,
    member_id: int,
    session_id: str,
    round_id: str,
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
                        logger.debug(
                            "relay: send_json auth_error failed",
                            exc_info=True,
                        )
                    try:
                        await websocket.close(code=4001, reason=_ws_close_reason(d))
                    except Exception:
                        logger.debug(
                            "relay: close after auth_error failed",
                            exc_info=True,
                        )
                    return
                continue
            if event["type"] != "message":
                continue
            try:
                data = json.loads(event["data"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "relay: invalid Redis message on %s: %s",
                    channel,
                    e,
                    exc_info=True,
                )
                continue
            try:
                async with send_lock:
                    await websocket.send_json(data)
            except Exception:
                logger.debug(
                    "relay: WebSocket send_json failed, stop relay on %s",
                    channel,
                    exc_info=True,
                )
                break
            if data.get("event") in _WS_ROUND_DONE_EVENTS:
                break
    finally:
        await pubsub.unsubscribe(channel)


@router.post("")
async def window_chat(
    window_chat_request: WindowChatRequest,
    request: Request,
    member_id: Annotated[int, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    """非流式 HTTP：触发 LangGraph，流式事件经 WebSocket ``/api/chat/ws`` 下发。"""
    window_state, window_graph, config = build_window_state_for_session_type(
        window_chat_request, db, request.app.state.checkpointer
    )

    publisher = EventPublisher()
    session_id = str(window_state["session_id"])
    round_id = str(window_state["round_id"])

    await publisher.set_active_round(session_id, round_id)
    await publisher.set_round_status(session_id, round_id, "running")

    task = asyncio.create_task(
        execute_chat_round_for_session_type(
            window_chat_request,
            window_graph,
            window_state,
            config,
            publisher,
        )
    )
    task.add_done_callback(_consume_task_exception)

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
    relay_task: asyncio.Task | None = None

    async def stop_relay() -> None:
        nonlocal relay_task
        if relay_task is None or relay_task.done():
            relay_task = None
            return
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        relay_task = None

    async def send_ws(payload: dict) -> None:
        async with ws_send_lock:
            await websocket.send_json(payload)

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
                chat_session_id = message.get("session_id")
                if chat_session_id and not message.get("resume"):
                    active_round = await publisher.get_active_round(str(chat_session_id))
                    if active_round:
                        await send_ws({"event": "error", "message": "当前有活跃的对话，请等待结束"})
                        continue
                db = SessionLocal()
                try:
                    window_chat_request = WindowChatRequest(
                        user_id=member_id,
                        user_message=message.get("user_message") or "",
                        org_id=message.get("org_id", 1),
                        session_id=message.get("session_id"),
                        round_id=message.get("round_id"),
                        session_type=message.get("session_type", "chat"),
                        group_id=message.get("group_id"),
                        file_ids=normalize_window_file_ids(message.get("file_ids")) or None,
                        single_agent_id=message.get("single_agent_id"),
                        resume=message.get("resume"),
                    )
                    
                    try:
                        window_state, window_graph, config = build_window_state_for_session_type(
                            window_chat_request, db, checkpointer
                        )
                    except HTTPException as e:
                        await send_ws({"event": "error", "message": e.detail})
                        continue

                    session_id = str(window_state["session_id"])
                    round_id = str(window_state["round_id"])

                    await publisher.set_active_round(session_id, round_id)
                    await publisher.set_round_status(session_id, round_id, "running")

                    channel = publisher.channel_name(session_id, round_id)
                    pubsub = publisher.redis.pubsub()
                    await pubsub.subscribe(channel)

                    task = asyncio.create_task(
                        execute_chat_round_for_session_type(
                            window_chat_request,
                            window_graph,
                            window_state,
                            config,
                            publisher,
                        )
                    )
                    task.add_done_callback(_consume_task_exception)

                    auth_failed = False
                    auth_fail_detail: str | None = None
                    terminal_event: str | None = None
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
                            try:
                                data = json.loads(event["data"])
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(
                                    "chat ws: invalid Redis payload session_id=%s round_id=%s: %s",
                                    session_id,
                                    round_id,
                                    e,
                                    exc_info=True,
                                )
                                continue
                            await send_ws(data)
                            if data.get("event") in _WS_ROUND_DONE_EVENTS:
                                terminal_event = data.get("event")
                                break
                    finally:
                        await pubsub.unsubscribe(channel)
                        task_exc: BaseException | None = None
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                        elif not task.cancelled():
                            task_exc = task.exception()
                        # 勿 await 已失败的任务（会 re-raise）；若 Redis error 未及时送达，直接经 WS 补发
                        if task_exc is not None and terminal_event not in _WS_ROUND_DONE_EVENTS:
                            await send_ws(
                                {"event": "error", "message": str(task_exc)},
                            )
                            terminal_event = "error"

                    if auth_failed:
                        await publisher.set_round_status(session_id, round_id, "failed")
                        await publisher.clear_active_round(session_id)
                        await send_ws({"event": "auth_error", "message": auth_fail_detail or "认证失败"})
                        await websocket.close(code=4001, reason=_ws_close_reason(auth_fail_detail))
                        return

                    if terminal_event == "error":
                        await publisher.set_round_status(session_id, round_id, "failed")
                        await publisher.clear_active_round(session_id)
                    elif terminal_event in {"finished", "speaker_finished"}:
                        await publisher.set_round_status(session_id, round_id, "completed")
                        await publisher.clear_active_round(session_id)
                    elif terminal_event == "main_interrupt":
                        await publisher.set_round_status(session_id, round_id, "interrupted")
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

                if status == "running":
                    await stop_relay()
                    channel = publisher.channel_name(session_id, active_round)
                    relay_task = asyncio.create_task(
                        _relay_redis_pubsub_to_websocket(
                            websocket, publisher, channel, ws_send_lock, token, member_id, session_id, active_round
                        )
                    )
                    relay_task.add_done_callback(_consume_task_exception)

            elif msg_type == "ping":
                await send_ws({"event": "pong"})

    except WebSocketDisconnect:
        await stop_relay()
    except Exception as e:
        await stop_relay()
        logger.exception("chat_websocket: 未处理异常")
        try:
            async with ws_send_lock:
                await websocket.send_json({"event": "error", "message": f"服务端内部错误: {e}"})
        except Exception:
            logger.debug(
                "chat_websocket: failed to send error frame to client",
                exc_info=True,
            )
