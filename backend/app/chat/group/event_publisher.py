import json
from typing import Any

from redis.asyncio import Redis

from app.redis_client import get_redis

# Redis key 前缀
KEY_PREFIX = "chat"

# TTL 常量（秒）
DEFAULT_TTL = 1800  # 30 分钟


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
        """发布事件：PUBLISH 到频道 + RPUSH 到列表"""
        payload = json.dumps(event_data, ensure_ascii=False)
        channel = _channel_name(session_id, round_id)
        events_key = _events_key(session_id, round_id)

        redis = self.redis
        await redis.publish(channel, payload)
        await redis.rpush(events_key, payload)
        await redis.expire(events_key, DEFAULT_TTL)

    async def get_round_events(
        self, session_id: str, round_id: str
    ) -> list[dict[str, Any]]:
        """获取某轮已产生的所有事件（用于断线重放）"""
        events_key = _events_key(session_id, round_id)
        raw_list = await self.redis.lrange(events_key, 0, -1)
        return [json.loads(raw) for raw in raw_list]

    async def set_active_round(self, session_id: str, round_id: str) -> None:
        """设置当前活跃 round"""
        key = _active_round_key(session_id)
        await self.redis.set(key, round_id, ex=DEFAULT_TTL)

    async def clear_active_round(self, session_id: str) -> None:
        """清除活跃 round"""
        await self.redis.delete(_active_round_key(session_id))

    async def get_active_round(self, session_id: str) -> str | None:
        """获取当前活跃 round_id"""
        return await self.redis.get(_active_round_key(session_id))

    async def set_round_status(self, session_id: str, round_id: str, status: str) -> None:
        """设置 round 状态：running / completed / failed"""
        key = _status_key(session_id, round_id)
        await self.redis.set(key, status, ex=DEFAULT_TTL)

    async def get_round_status(self, session_id: str, round_id: str) -> str | None:
        """获取 round 状态"""
        return await self.redis.get(_status_key(session_id, round_id))

    def channel_name(self, session_id: str, round_id: str) -> str:
        """获取 Pub/Sub 频道名"""
        return _channel_name(session_id, round_id)
