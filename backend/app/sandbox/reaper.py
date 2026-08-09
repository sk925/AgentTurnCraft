"""沙箱容器后台定时探活清理（不占用工具调用热路径）。"""

from __future__ import annotations

import asyncio
import logging

from app.sandbox.config import DEFAULT_SANDBOX_CONFIG
from app.sandbox.manager import get_sandbox_manager

logger = logging.getLogger(__name__)

_reaper_task: asyncio.Task[None] | None = None


async def _idle_reaper_loop(interval_seconds: int) -> None:
    manager = get_sandbox_manager()
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            released = await asyncio.to_thread(manager.cleanup_idle)
            if released:
                logger.info("Docker sandbox idle reaper released %s container(s)", released)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Docker sandbox idle reaper failed")


async def start_sandbox_idle_reaper() -> None:
    """在应用 lifespan 中启动定时探活清理。"""
    global _reaper_task
    if _reaper_task is not None and not _reaper_task.done():
        return

    interval = max(0, int(DEFAULT_SANDBOX_CONFIG.idle_cleanup_interval_seconds))
    if interval <= 0:
        logger.info("Docker sandbox idle reaper disabled (interval=%s)", interval)
        return

    _reaper_task = asyncio.create_task(
        _idle_reaper_loop(interval),
        name="sandbox-idle-reaper",
    )
    logger.info("Docker sandbox idle reaper started interval=%ss", interval)


async def stop_sandbox_idle_reaper() -> None:
    """在应用 lifespan 关闭时停止定时探活清理。"""
    global _reaper_task
    task = _reaper_task
    _reaper_task = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Docker sandbox idle reaper stopped")
