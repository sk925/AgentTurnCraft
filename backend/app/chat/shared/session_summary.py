"""单聊会话上下文滚动摘要：轮次结束后压缩 LangGraph checkpoint messages。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.constants import CONFIG_KEY_CHECKPOINTER
from langgraph.graph.state import CompiledStateGraph
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.config import settings
from app.database import transactional_session
from app.chat.session.models import ChatSession

logger = logging.getLogger(__name__)

_AGET_STATE_TIMEOUT_SEC = 30.0
_SUMMARY_MODEL_TIMEOUT_SEC = 90.0
_DB_CONNECT_TIMEOUT_SEC = 10.0
# astream 收尾后再压，避免与全局 checkpointer 单连接锁打架
_DEFER_COMPACT_SEC = 0.5

SUMMARY_PROMPT = """
<role>
对话上下文提炼助手
</role>

<primary_objective>
从下方对话历史中提取后续继续对话所必需的高价值上下文。
</primary_objective>

<objective_information>
当前上下文即将超出可接受的输入长度，你必须从历史中提炼最重要的信息。
提炼结果将替换下方整段历史，因此只保留继续完成用户目标所必需的内容。
</objective_information>

<instructions>
请按以下结构输出（某节无内容时写「无」）：

## 会话意图
用户的主要目标或请求是什么？

## 摘要
记录关键结论、选择、约束、用户偏好，以及重要决策的理由；被否决的方案也简要记下。

## 产物
创建/修改/访问过的文件、资源或工具结果要点（含路径若有）。

## 下一步
尚未完成、需要继续推进的具体事项。
</instructions>

只输出提炼后的上下文，不要附加前后说明。

<messages>
待摘要的消息：
{messages}
</messages>
""".strip()


class _SessionSummarizationMiddleware(SummarizationMiddleware):
    """中文摘要消息包装。"""

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"以下是此前对话的摘要，请在后续回复中延续这些上下文：\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]


_middleware: _SessionSummarizationMiddleware | None = None
_middleware_key: tuple[Any, ...] | None = None


def _resolve_summary_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.summary_model_name or settings.agent_selector_model_name,
        base_url=settings.summary_model_base_url or settings.agent_selector_model_base_url,
        api_key=settings.summary_model_api_key or settings.agent_selector_model_api_key,
        temperature=0.2,
        timeout=_SUMMARY_MODEL_TIMEOUT_SEC,
        max_retries=1,
    )


def get_summarization_middleware() -> _SessionSummarizationMiddleware:
    global _middleware, _middleware_key
    key = (
        settings.summary_trigger_tokens,
        settings.summary_keep_messages,
        settings.summary_model_name,
        settings.summary_model_base_url,
        settings.summary_model_api_key,
    )
    if _middleware is None or _middleware_key != key:
        _middleware = _SessionSummarizationMiddleware(
            model=_resolve_summary_model(),
            trigger=("tokens", settings.summary_trigger_tokens),
            keep=("messages", settings.summary_keep_messages),
            summary_prompt=SUMMARY_PROMPT,
        )
        _middleware_key = key
    return _middleware


def _extract_summary_text(messages: list[Any]) -> str | None:
    for msg in messages:
        kwargs = getattr(msg, "additional_kwargs", None) or {}
        if kwargs.get("lc_source") == "summarization":
            content = getattr(msg, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


def _last_reported_total_tokens(messages: list[Any]) -> int | None:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.usage_metadata:
            total = msg.usage_metadata.get("total_tokens")
            if isinstance(total, int):
                return total
    return None


def _persist_session_summary(session_id: str, summary: str, token_use: int | None) -> None:
    with transactional_session() as db:
        row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if row is None:
            return
        row.summary = summary
        if token_use is not None:
            row.token_use = token_use


def schedule_compact_after_round(
    compiled_graph: CompiledStateGraph,
    config: dict[str, Any],
    session_id: str,
) -> None:
    """不阻塞对话收尾：延迟到后台压缩。"""
    cfg = {
        **config,
        "configurable": dict(config.get("configurable") or {}),
    }
    task = asyncio.create_task(
        _deferred_compact(compiled_graph, cfg, session_id),
        name=f"session-summary-{session_id}",
    )

    def _done(t: asyncio.Task[bool]) -> None:
        try:
            t.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("session summary background task failed session_id=%s", session_id)

    task.add_done_callback(_done)


async def _deferred_compact(
    compiled_graph: CompiledStateGraph,
    config: dict[str, Any],
    session_id: str,
) -> bool:
    logger.info(
        "session summary: scheduled session_id=%s defer=%.1fs",
        session_id,
        _DEFER_COMPACT_SEC,
    )
    await asyncio.sleep(_DEFER_COMPACT_SEC)
    return await maybe_compact_after_round(compiled_graph, config, session_id)


async def maybe_compact_after_round(
    compiled_graph: CompiledStateGraph,
    config: dict[str, Any],
    session_id: str,
) -> bool:
    """一轮正常结束后尝试压缩 checkpoint；返回是否发生了摘要。"""
    logger.info("session summary: enter session_id=%s enabled=%s", session_id, settings.summary_enabled)
    if not settings.summary_enabled:
        return False

    thread_id = str((config.get("configurable") or {}).get("thread_id") or session_id)

    try:
        logger.info("session summary: open db connection session_id=%s", session_id)
        conn = await asyncio.wait_for(
            AsyncConnection.connect(
                settings.database_url,
                autocommit=True,
                prepare_threshold=0,
                row_factory=dict_row,
                connect_timeout=int(_DB_CONNECT_TIMEOUT_SEC),
            ),
            timeout=_DB_CONNECT_TIMEOUT_SEC + 5.0,
        )
    except Exception:
        logger.exception("session summary: db connect failed session_id=%s", session_id)
        return False

    try:
        async with conn:
            # 独立连接 + 独立 lock，不碰全局 astream 用的 checkpointer
            saver = AsyncPostgresSaver(conn=conn)
            compact_config: dict[str, Any] = {
                **config,
                "configurable": {
                    **(config.get("configurable") or {}),
                    "thread_id": thread_id,
                    CONFIG_KEY_CHECKPOINTER: saver,
                },
            }

            logger.info("session summary: aget_state start session_id=%s", session_id)
            try:
                snapshot = await asyncio.wait_for(
                    compiled_graph.aget_state(compact_config),
                    timeout=_AGET_STATE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "session summary: aget_state timed out session_id=%s",
                    session_id,
                )
                return False

            values = snapshot.values or {}
            messages = list(values.get("messages") or [])
            if not messages:
                logger.info("session summary: skip empty messages session_id=%s", session_id)
                return False

            middleware = get_summarization_middleware()
            approx = middleware.token_counter(messages)
            reported = _last_reported_total_tokens(messages)
            logger.info(
                "session summary: check session_id=%s msgs=%s approx≈%s reported_total=%s "
                "trigger=%s keep=%s",
                session_id,
                len(messages),
                approx,
                reported,
                settings.summary_trigger_tokens,
                settings.summary_keep_messages,
            )

            logger.info("session summary: abefore_model start session_id=%s", session_id)
            try:
                update = await asyncio.wait_for(
                    middleware.abefore_model({"messages": messages}, None),  # type: ignore[arg-type]
                    timeout=_SUMMARY_MODEL_TIMEOUT_SEC + 15.0,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "session summary: abefore_model timed out session_id=%s",
                    session_id,
                )
                return False

            if not update:
                logger.info(
                    "session summary: no compact needed session_id=%s",
                    session_id,
                )
                return False

            logger.info("session summary: aupdate_state start session_id=%s", session_id)
            try:
                await asyncio.wait_for(
                    compiled_graph.aupdate_state(compact_config, update),
                    timeout=_AGET_STATE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "session summary: aupdate_state timed out session_id=%s",
                    session_id,
                )
                return False

            new_messages = [m for m in update["messages"] if not isinstance(m, RemoveMessage)]
            summary_text = _extract_summary_text(new_messages)
            token_use = middleware.token_counter(new_messages) if new_messages else None
            if summary_text:
                _persist_session_summary(session_id, summary_text, token_use)

            logger.info(
                "session summary compacted session_id=%s kept=%s tokens≈%s",
                session_id,
                len(new_messages),
                token_use,
            )
            return True
    except Exception:
        logger.exception("session summary compact failed session_id=%s", session_id)
        return False
