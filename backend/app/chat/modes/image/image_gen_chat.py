"""文生图会话：解析智能体绑定的 image_generation 模型，调用万相并落盘 MinIO。"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, TypedDict

import httpx
from fastapi import status

from app.chat.base.models import AgentService
from app.chat.base.models.agent_log import AgentLog, AgentLogService
from app.chat.modes.image.wan_client import generate_images_wan
from app.chat.shared.chat_common import MsgType, RoleType
from app.chat.shared.event_publisher import EventPublisher
from app.config import settings
from app.database import transactional_session
from app.exceptions import AppException
from app.model_manage.model_cat import ChatModel, ModelProvider, ModelType
from app.utils.minio_storage import upload_bytes

logger = logging.getLogger(__name__)


class ImageGenRoundInfo(TypedDict, total=False):
    user_id: int
    session_id: str
    round_id: str
    user_message: str
    agent_id: int | None


def _resolve_agent_id(agent_id: int | None) -> int:
    if agent_id is not None:
        return int(agent_id)
    if settings.default_image_agent_id is not None:
        return int(settings.default_image_agent_id)
    raise AppException(
        message="请选择文生图智能体，或在配置中设置 DEFAULT_IMAGE_AGENT_ID",
        code=status.HTTP_400_BAD_REQUEST,
    )


def _load_image_model(chat_model_id: int) -> tuple[str, str, str]:
    """返回 (model_name, base_url, api_key)，并校验 model_type。"""
    with transactional_session() as db:
        row = (
            db.query(ChatModel, ModelProvider)
            .join(ModelProvider, ModelProvider.id == ChatModel.provider_id)
            .filter(ChatModel.id == chat_model_id)
            .first()
        )
        if row is None:
            raise AppException(message="智能体绑定的模型不存在", code=status.HTTP_404_NOT_FOUND)
        chat_model, provider = row
        model_type = (chat_model.model_type or "").strip().lower()
        if model_type != ModelType.IMAGE_GENERATION.value:
            raise AppException(
                message="该智能体未绑定文生图模型（model_type 须为 image_generation）",
                code=status.HTTP_400_BAD_REQUEST,
            )
        api_key = (provider.api_key or "").strip()
        if not api_key:
            raise AppException(message="文生图模型未配置 API Key", code=status.HTTP_400_BAD_REQUEST)
        base_url = (provider.base_url or "").strip()
        if not base_url:
            raise AppException(message="文生图模型未配置 base_url", code=status.HTTP_400_BAD_REQUEST)
        return str(chat_model.name), base_url, api_key


def _compose_prompt(user_message: str, agent_prompt: str | None) -> str:
    user_text = (user_message or "").strip()
    style = (agent_prompt or "").strip()
    if style and user_text:
        return f"{style}\n\n用户需求：{user_text}"
    return user_text or style


async def _download_image_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), follow_redirects=True) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise RuntimeError(f"下载生成图片失败：HTTP {resp.status_code}")
    data = resp.content
    if not data:
        raise RuntimeError("下载生成图片失败：空内容")
    return data


def _persist_images(
    *,
    user_id: int,
    session_id: str,
    remote_urls: list[str],
    image_bytes_list: list[bytes],
) -> list[dict[str, str]]:
    saved: list[dict[str, str]] = []
    for idx, raw in enumerate(image_bytes_list):
        object_key = f"generated-images/{user_id}/{session_id}/{uuid.uuid4().hex}.png"
        upload_bytes(
            settings.minio_bucket,
            object_key,
            raw,
            content_type="image/png",
        )
        public_url = f"{settings.minio_endpoint.rstrip('/')}/{settings.minio_bucket}/{object_key}"
        saved.append(
            {
                "url": public_url,
                "object_key": object_key,
                "file_name": f"generated_{idx + 1}.png",
                "source_url": remote_urls[idx] if idx < len(remote_urls) else "",
            }
        )
    return saved


def _save_image_log(
    *,
    user_id: int,
    session_id: str,
    round_id: str,
    speaker: dict[str, Any],
    prompt: str,
    images: list[dict[str, str]],
    model_name: str,
) -> None:
    content = json.dumps(
        {"prompt": prompt, "images": [{"url": i["url"], "object_key": i["object_key"], "file_name": i["file_name"]} for i in images]},
        ensure_ascii=False,
    )
    row = AgentLog(
        user_id=user_id,
        session_id=session_id,
        round_id=round_id,
        role_type=RoleType.SPEAKER.value,
        message_type=MsgType.IMAGE.value,
        content=content,
        speaker_id=speaker.get("id"),
        speaker_name=speaker.get("name"),
        model_name=model_name,
    )
    AgentLogService.save_agent_log(row)


async def chat_with_image_agent(round_info: ImageGenRoundInfo, publisher: EventPublisher) -> None:
    agent_id = _resolve_agent_id(round_info.get("agent_id"))
    agent_info = AgentService.get_agent_info_by_id(agent_id)
    if agent_info is None:
        raise AppException(message="Agent not found", code=status.HTTP_404_NOT_FOUND)
    if agent_info.get("chat_model_id") is None:
        raise AppException(message="智能体未绑定文生图模型", code=status.HTTP_400_BAD_REQUEST)

    model_name, base_url, api_key = _load_image_model(int(agent_info["chat_model_id"]))
    session_id = str(round_info["session_id"])
    round_id = str(round_info["round_id"])
    user_id = int(round_info["user_id"])
    user_message = round_info.get("user_message") or ""
    prompt = _compose_prompt(user_message, agent_info.get("prompt"))
    if not prompt.strip():
        raise AppException(message="请输入图片描述", code=status.HTTP_400_BAD_REQUEST)

    speaker = {"id": agent_info["id"], "name": agent_info["name"]}

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "select_speaker",
            "current_speaker": {"id": speaker["id"], "name": speaker["name"]},
        },
    )
    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "image_generating",
            "speaker_id": speaker["id"],
            "speaker_name": speaker["name"],
            "prompt": prompt,
        },
    )

    remote_urls = await generate_images_wan(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        prompt=prompt,
        size="2K",
        n=1,
        watermark=False,
        thinking_mode=False,
    )

    image_bytes_list: list[bytes] = []
    for url in remote_urls:
        image_bytes_list.append(await _download_image_bytes(url))

    saved = _persist_images(
        user_id=user_id,
        session_id=session_id,
        remote_urls=remote_urls,
        image_bytes_list=image_bytes_list,
    )
    _save_image_log(
        user_id=user_id,
        session_id=session_id,
        round_id=round_id,
        speaker=speaker,
        prompt=prompt,
        images=saved,
        model_name=model_name,
    )

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "image_generated",
            "speaker_id": speaker["id"],
            "speaker_name": speaker["name"],
            "prompt": prompt,
            "images": [
                {"url": i["url"], "file_name": i["file_name"], "file_type": "image/png"}
                for i in saved
            ],
        },
    )
    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "speaker_finished",
            "answer": "",
            "finish_reason": "stop",
        },
    )
