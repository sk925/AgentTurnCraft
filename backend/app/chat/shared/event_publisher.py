import json
from typing import Any

from redis.asyncio import Redis

from app.redis_client import get_redis

KEY_PREFIX = "chat"
DEFAULT_TTL = 1800


def _active_round_key(session_id: str) -> str:
    return f"{KEY_PREFIX}:{session_id}:active_round"


def _events_key(session_id: str, round_id: str) -> str:
    return f"{KEY_PREFIX}:{session_id}:{round_id}:events"


def _status_key(session_id: str, round_id: str) -> str:
    return f"{KEY_PREFIX}:{session_id}:{round_id}:status"


def _channel_name(session_id: str, round_id: str) -> str:
    return f"{KEY_PREFIX}:{session_id}:{round_id}"


class EventPublisher:
    """将 LangGraph 执行事件发布到 Redis（Pub/Sub + List）"""

    def __init__(self, redis: Redis | None = None):
        self._redis = redis

    @property
    def redis(self) -> Redis:
        if self._redis is not None:
            return self._redis
        return get_redis()

    async def publish(
        self,
        session_id: str,
        round_id: str,
        event_data: dict[str, Any],
    ) -> None:
        payload = json.dumps(event_data, ensure_ascii=False)
        channel = _channel_name(session_id, round_id)
        events_key = _events_key(session_id, round_id)

        redis = self.redis
        await redis.rpush(events_key, payload)
        await redis.expire(events_key, DEFAULT_TTL)
        await redis.publish(channel, payload)

    async def get_round_events(
        self, session_id: str, round_id: str
    ) -> list[dict[str, Any]]:
        events_key = _events_key(session_id, round_id)
        raw_list = await self.redis.lrange(events_key, 0, -1)
        return [json.loads(raw) for raw in raw_list]

    async def set_active_round(self, session_id: str, round_id: str) -> None:
        key = _active_round_key(session_id)
        await self.redis.set(key, round_id, ex=DEFAULT_TTL)

    async def clear_active_round(self, session_id: str) -> None:
        await self.redis.delete(_active_round_key(session_id))

    async def get_active_round(self, session_id: str) -> str | None:
        return await self.redis.get(_active_round_key(session_id))

    async def set_round_status(self, session_id: str, round_id: str, status: str) -> None:
        key = _status_key(session_id, round_id)
        await self.redis.set(key, status, ex=DEFAULT_TTL)

    async def get_round_status(self, session_id: str, round_id: str) -> str | None:
        return await self.redis.get(_status_key(session_id, round_id))

    def channel_name(self, session_id: str, round_id: str) -> str:
        return _channel_name(session_id, round_id)
