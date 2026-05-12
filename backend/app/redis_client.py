import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def init_redis() -> Redis:
    """初始化 Redis 连接池"""
    global _redis
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    await _redis.ping()
    return _redis


async def close_redis() -> None:
    """关闭 Redis 连接"""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def get_redis() -> Redis:
    """获取 Redis 实例（同步调用，确保 init_redis 已执行）"""
    if _redis is None:
        raise RuntimeError("Redis 未初始化，请先调用 init_redis()")
    return _redis
