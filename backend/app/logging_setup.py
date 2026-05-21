"""应用日志配置：开发环境可读文本，生产环境 JSON 输出到 stdout（便于容器/日志平台采集）。"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.config import settings

# 第三方库默认降噪，避免刷屏
_QUIET_LOGGERS = (
    "sqlalchemy.engine",
    "httpx",
    "httpcore",
    "openai",
    "langchain",
    "langgraph",
    "urllib3",
    "multipart",
)

_CONFIGURED = False


class JsonLogFormatter(logging.Formatter):
    """单行 JSON，便于 Loki / ELK / CloudWatch 等采集与检索。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        # 支持 logger.info("msg", extra={"key": "val"})
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
            ):
                continue
            if key not in payload:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def _resolve_level() -> int:
    name = (settings.log_level or "INFO").upper()
    return getattr(logging, name, logging.INFO)


def _build_formatter() -> logging.Formatter:
    if settings.app_env.lower() == "production":
        return JsonLogFormatter()
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def configure_logging() -> None:
    """配置 `app` 命名空间日志；幂等，可在 reload 时重复调用。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = _resolve_level()
    formatter = _build_formatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.setLevel(level)
    # 不向 root 传播，避免与 uvicorn 默认 root/lastResort 重复或级别不一致
    app_logger.propagate = False

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))

    _CONFIGURED = True
    app_logger.debug(
        "logging configured env=%s level=%s json=%s",
        settings.app_env,
        logging.getLevelName(level),
        settings.app_env.lower() == "production",
    )
