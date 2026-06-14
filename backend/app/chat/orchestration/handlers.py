"""按 SessionType 注册的 ChatModeHandler（阶段 E）。"""

from __future__ import annotations

import logging
from typing import Protocol

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.chat.orchestration.state_builder import build_group_window_state, build_single_window_state
from app.chat.orchestration.window_request import WindowChatRequest
from app.chat.shared.chat_common import SessionType, SpearkerRecord
from app.chat.shared.event_publisher import EventPublisher
from app.chat.modes.single import ChatRountInfo, chat_with_single_agent
from app.harness.round import RoundContext

logger = logging.getLogger(__name__)


class ChatModeHandler(Protocol):
    def build(
        self,
        window_chat_request: WindowChatRequest,
        db: Session,
        checkpointer,
    ) -> RoundContext: ...

    async def execute(
        self,
        window_chat_request: WindowChatRequest,
        round_ctx: RoundContext,
        publisher: EventPublisher,
    ) -> None: ...


def _build_select_agents_payload(data: dict) -> dict | None:
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    return {
        "event": "create_group",
        "group_members": [
            {"id": agent["id"], "name": agent["name"]}
            for agent in data.get("group_members", [])
        ],
        "select_reason": data.get("select_reason", ""),
    }


def _build_select_speaker_payload(data: dict) -> dict | None:
    if data.get("finished", False):
        return {
            "event": "finished",
            "answer": data.get("answer", ""),
            "finish_reason": data.get("finish_reason", ""),
        }
    payload = dict(data)
    payload.pop("session_messages", None)
    payload["event"] = "select_speaker"
    return payload


def _build_speaker_payload(data: dict) -> dict | None:
    transcript: list[SpearkerRecord] = data.get("transcript", [])
    if transcript:
        record = transcript[-1]
        record["event"] = "speaker"
        return record
    return None


class GroupChatHandler:
    """群聊 LangGraph 模式。"""

    def build(
        self,
        window_chat_request: WindowChatRequest,
        db: Session,
        checkpointer,
    ) -> RoundContext:
        return build_group_window_state(window_chat_request, db, checkpointer)

    async def execute(
        self,
        window_chat_request: WindowChatRequest,
        round_ctx: RoundContext,
        publisher: EventPublisher,
    ) -> None:
        window_graph = round_ctx.window_graph
        if window_graph is None:
            raise RuntimeError("群聊模式缺少 LangGraph 编译图")

        window_state = round_ctx.window_state
        config = round_ctx.config
        session_id = str(window_state["session_id"])
        round_id = str(window_state["round_id"])

        await publisher.publish(
            session_id,
            round_id,
            {
                "event": "start",
                "session_id": session_id,
                "round_id": round_id,
            },
        )

        stream_input: dict | Command = window_state
        if window_chat_request.resume:
            stream_input = Command(resume=window_chat_request.resume)

        round_failed = False
        round_interrupted = False
        try:
            async for chunk in window_graph.astream(
                stream_input,
                config=config,
                stream_mode=["messages", "updates", "custom"],
            ):
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    mode, data = chunk
                elif isinstance(chunk, tuple) and len(chunk) == 3:
                    _, mode, data = chunk
                else:
                    continue

                if mode == "updates":
                    if data.get("select_agents_node"):
                        agents_data = data["select_agents_node"]
                        payload = _build_select_agents_payload(agents_data)
                        if payload:
                            await publisher.publish(session_id, round_id, payload)
                        group_members = agents_data.get("group_members", [])
                        if group_members and len(group_members) == 1:
                            await publisher.publish(
                                session_id,
                                round_id,
                                {
                                    "event": "select_speaker",
                                    "current_speaker": group_members[0],
                                },
                            )

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
                            await publisher.publish(
                                session_id,
                                round_id,
                                {
                                    "event": "speaker_finished",
                                    "answer": speak_data.get("answer", ""),
                                    "finish_reason": speak_data.get("finish_reason", ""),
                                },
                            )
                    if isinstance(data, dict) and data.get("__interrupt__"):
                        round_interrupted = True
                        await publisher.publish(
                            session_id,
                            round_id,
                            {
                                "event": "main_interrupt",
                                "interrupt_data": data.get("__interrupt__")[0].value,
                            },
                        )
                elif mode == "custom":
                    await publisher.publish(session_id, round_id, data)
                elif mode == "messages":
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
            logger.exception(
                "LangGraph 群聊轮次失败 session_id=%s round_id=%s",
                session_id,
                round_id,
            )
            await publisher.publish(
                session_id,
                round_id,
                {"event": "error", "message": getattr(e, "message", None) or str(e)},
            )
            raise
        finally:
            if round_failed:
                round_status = "failed"
            elif round_interrupted:
                round_status = "interrupted"
            else:
                round_status = "completed"
            await publisher.set_round_status(session_id, round_id, round_status)
            if not round_interrupted:
                await publisher.clear_active_round(session_id)


class SingleChatHandler:
    """单聊 Deep Agent 模式（经 AgentRuntime）。"""

    def build(
        self,
        window_chat_request: WindowChatRequest,
        db: Session,
        checkpointer,
    ) -> RoundContext:
        return build_single_window_state(window_chat_request, db, checkpointer)

    async def execute(
        self,
        window_chat_request: WindowChatRequest,
        round_ctx: RoundContext,
        publisher: EventPublisher,
    ) -> None:
        window_state = round_ctx.window_state
        session_id = str(window_state["session_id"])
        round_id = str(window_state["round_id"])

        await publisher.publish(
            session_id,
            round_id,
            {
                "event": "start",
                "session_id": session_id,
                "round_id": round_id,
            },
        )

        single_agent_id: int | None = None
        if window_chat_request.single_agent_id is not None:
            try:
                single_agent_id = int(str(window_chat_request.single_agent_id).strip())
            except (TypeError, ValueError):
                single_agent_id = None

        chat_round_info = ChatRountInfo(
            user_id=window_chat_request.user_id,
            session_id=session_id,
            round_id=round_id,
            user_message=window_state["user_message"],
            agent_id=single_agent_id,
            file_ids=window_state.get("file_ids") or [],
            attachment_context=window_state.get("attachment_context") or "",
            resume=window_chat_request.resume,
        )

        round_failed = False
        round_interrupted = False
        try:
            round_interrupted = await chat_with_single_agent(chat_round_info, publisher)
        except Exception as e:
            round_failed = True
            logger.exception(
                "单聊轮次失败 session_id=%s round_id=%s",
                session_id,
                round_id,
            )
            await publisher.publish(
                session_id,
                round_id,
                {"event": "error", "message": getattr(e, "message", None) or str(e)},
            )
            raise
        finally:
            if round_failed:
                round_status = "failed"
            elif round_interrupted:
                round_status = "interrupted"
            else:
                round_status = "completed"
            await publisher.set_round_status(session_id, round_id, round_status)
            if not round_interrupted:
                await publisher.clear_active_round(session_id)


_GROUP_HANDLER = GroupChatHandler()
_SINGLE_HANDLER = SingleChatHandler()
_DEFAULT_HANDLER = _SINGLE_HANDLER

_CHAT_MODE_HANDLERS: dict[SessionType, ChatModeHandler] = {
    SessionType.GROUP_CHAT: _GROUP_HANDLER,
    SessionType.CHAT: _SINGLE_HANDLER,
    SessionType.PPT: _SINGLE_HANDLER,
}


def get_chat_mode_handler(session_type: SessionType) -> ChatModeHandler:
    return _CHAT_MODE_HANDLERS.get(session_type, _DEFAULT_HANDLER)
