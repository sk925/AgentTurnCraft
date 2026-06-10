"""多节点技能缓存失效广播（Redis Pub/Sub）。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis as sync_redis

from app.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "agent-turncraft:skill-cache:invalidate"

_listener_task: asyncio.Task[None] | None = None


def _publish_sync(payload: dict[str, Any]) -> None:
    client = sync_redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        client.publish(CHANNEL, json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.exception("skill cache broadcast publish failed: %s", payload)
    finally:
        client.close()


def broadcast_skill_deleted(skill_id: int) -> None:
    _publish_sync({"action": "skill_deleted", "skill_id": int(skill_id)})


def broadcast_agent_skills_changed(
    agent_ids: list[int],
    *,
    materialize_skill_ids: list[int] | None = None,
) -> None:
    ids = [int(aid) for aid in agent_ids if aid is not None]
    if not ids and not materialize_skill_ids:
        return
    payload: dict[str, Any] = {"action": "agent_skills_changed", "agent_ids": ids}
    if materialize_skill_ids:
        payload["materialize_skill_ids"] = [int(sid) for sid in materialize_skill_ids]
    _publish_sync(payload)


def _handle_message(payload: dict[str, Any]) -> None:
    action = payload.get("action")
    if action == "skill_deleted":
        from app.chat.base.skill_materializer import remove_skill_cache

        skill_id = int(payload["skill_id"])
        remove_skill_cache(skill_id)
        logger.info("skill cache removed on this node: skill_id=%s", skill_id)
        return

    if action == "agent_skills_changed":
        from app.chat.base.skill_materializer import materialize_skill_by_id
        from app.chat.group.speaker import evict_speaker_agent_graph_cache_for_agent_ids
        from app.chat.single.single_chat import evict_single_chat_agent_cache_for_agent_ids

        for skill_id in payload.get("materialize_skill_ids", []):
            try:
                materialize_skill_by_id(int(skill_id))
            except Exception:
                logger.exception("materialize skill on this node failed: skill_id=%s", skill_id)

        agent_ids = [int(aid) for aid in payload.get("agent_ids", [])]
        if agent_ids:
            evict_speaker_agent_graph_cache_for_agent_ids(agent_ids)
            evict_single_chat_agent_cache_for_agent_ids(agent_ids)
            logger.info("agent skill caches evicted on this node: agent_ids=%s", agent_ids)


async def _listen_loop() -> None:
    from app.redis_client import get_redis

    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    logger.info("skill cache invalidation listener started on channel=%s", CHANNEL)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("invalid skill cache broadcast payload: %r", raw)
                continue
            try:
                _handle_message(payload)
            except Exception:
                logger.exception("handle skill cache broadcast failed: %s", payload)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.close()


async def start_skill_cache_invalidation_listener() -> None:
    global _listener_task
    if _listener_task is not None and not _listener_task.done():
        return
    _listener_task = asyncio.create_task(_listen_loop(), name="skill-cache-invalidation-listener")


async def stop_skill_cache_invalidation_listener() -> None:
    global _listener_task
    if _listener_task is None:
        return
    _listener_task.cancel()
    try:
        await _listener_task
    except asyncio.CancelledError:
        pass
    _listener_task = None
