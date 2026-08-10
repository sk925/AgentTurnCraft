"""阿里云百炼万相（wan2.7-image-pro 等）文生图 HTTP 客户端。"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)


def resolve_wan_generation_url(base_url: str) -> str:
    """将模型 provider 的 base_url 规范为 multimodal-generation 接口地址。"""
    raw = (base_url or "").strip().rstrip("/")
    if not raw:
        raise ValueError("模型 provider 的 base_url 未配置")

    if raw.endswith("/generation"):
        return raw

    for suffix in (
        "/compatible-mode/v1",
        "/compatible-mode",
        "/v1/chat/completions",
        "/chat/completions",
    ):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
            break

    path = urlparse(raw).path.rstrip("/")
    if path.endswith("/api/v1"):
        return f"{raw}/services/aigc/multimodal-generation/generation"
    if path.endswith("/api"):
        return f"{raw}/v1/services/aigc/multimodal-generation/generation"
    if "/services/aigc/" in path:
        return raw
    return f"{raw}/api/v1/services/aigc/multimodal-generation/generation"


def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
    output = payload.get("output") or {}
    choices = output.get("choices") or []
    urls: list[str] = []
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            continue
        content = message.get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image" or "image" in block:
                image_url = block.get("image")
                if isinstance(image_url, str) and image_url.strip():
                    urls.append(image_url.strip())
    return urls


async def generate_images_wan(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    prompt: str,
    size: str = "2K",
    n: int = 1,
    watermark: bool = False,
    thinking_mode: bool = False,
) -> list[str]:
    """调用万相同步文生图接口，返回临时图片 URL 列表（有效期约 24h）。"""
    url = resolve_wan_generation_url(base_url)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body: dict[str, Any] = {
        "model": model_name,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "size": size,
            "n": max(1, min(int(n), 4)),
            "watermark": bool(watermark),
            "thinking_mode": bool(thinking_mode),
        },
    }

    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=body)

    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"文生图接口返回非 JSON：HTTP {resp.status_code}") from exc

    if resp.status_code != 200:
        message = data.get("message") or data.get("msg") or resp.text
        code = data.get("code") or resp.status_code
        raise RuntimeError(f"文生图失败（{code}）：{message}")

    # 部分错误仍以 200 + code 字段返回
    err_code = data.get("code")
    if err_code and str(err_code).upper() not in {"", "SUCCESS", "OK", "200"}:
        message = data.get("message") or data.get("msg") or str(err_code)
        raise RuntimeError(f"文生图失败（{err_code}）：{message}")

    urls = _extract_image_urls(data)
    if not urls:
        logger.warning("文生图响应无图片 URL：%s", data)
        raise RuntimeError("文生图成功但未返回图片地址")
    return urls
