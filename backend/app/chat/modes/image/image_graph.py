"""文生图会话 LangGraph：chat_agent（对话）→ 按需 generate_image（生图）。"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.chat.base.models.agent_log import AgentLogService
from app.chat.modes.image.image_gen_chat import (
    _compose_prompt,
    _download_image_bytes,
    _load_image_model,
    _persist_images,
    _save_image_log,
)
from app.chat.modes.image.wan_client import generate_images_wan
from app.chat.shared.chat_common import MsgType, RoleType
from app.chat.shared.event_publisher import EventPublisher
from app.chat.shared.streaming import message_chunk_text
from app.config import settings

logger = logging.getLogger(__name__)
publisher = EventPublisher()

CHAT_AGENT_SYSTEM = """你是文生图助手「{name}」。
你的职责是与用户自然对话，并在真正需要出图时调用 generate_image 工具。

{style_block}

## 规则（必须遵守）
1. 普通闲聊、问候、讨论想法、澄清需求、询问风格/尺寸 → **只文字回复**，禁止调用工具。
2. 仅当用户明确要求生成/画/出图/做一张图，且画面描述已足够清晰时，才调用 generate_image。
3. 调用 generate_image 时：
   - prompt 必须是完整、可直接送给文生图模型的提示词（可在用户原话基础上润色、补全细节）；
   - 不要在 prompt 里写「请生成图片」这类指令套话；
   - 可先用一两句简短确认，再调用工具。
4. 禁止假装已经生成了图片；真正出图由系统生图节点完成。
5. 若描述含糊（如「画个好看的」），先追问主题、风格、构图等，不要急着调用工具。
"""


class GenerateImageArgs(BaseModel):
    prompt: str = Field(description="完整的文生图提示词，可直接用于图像生成模型")


@tool("generate_image", args_schema=GenerateImageArgs)
def generate_image_tool(prompt: str) -> str:
    """当用户需要生成图片且提示词已明确时调用。传入完整生图提示词。"""
    return prompt


class ImageChatState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_message: str
    session_id: str
    round_id: str
    member_id: int
    user_profile: dict[str, Any]
    current_speaker: dict[str, Any]
    agent_style_prompt: str
    image_model_id: int
    image_prompt: str | None
    answer: str
    finished: bool
    finish_reason: str


def _chat_llm() -> ChatOpenAI:
    """对话节点使用文本模型（复用群聊 speaker 配置）。"""
    return ChatOpenAI(
        model=settings.speaker_model_name,
        base_url=settings.speaker_model_base_url,
        api_key=settings.speaker_model_api_key,
        temperature=0.4,
        stream_usage=True,
    )


def _system_prompt(state: ImageChatState) -> str:
    speaker = state.get("current_speaker") or {}
    name = str(speaker.get("name") or "文生图助手")
    style = (state.get("agent_style_prompt") or "").strip()
    style_block = f"## 人设 / 风格偏好\n{style}" if style else "## 人设 / 风格偏好\n（无额外设定）"
    return CHAT_AGENT_SYSTEM.format(name=name, style_block=style_block)


def _extract_image_prompt(message: AIMessage) -> str | None:
    tool_calls = getattr(message, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
        if name != "generate_image":
            continue
        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None) or {}
        if not isinstance(args, dict):
            continue
        prompt = args.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
    return None


async def chat_agent_node(state: ImageChatState) -> Command[Literal["generate_image_node", "__end__"]]:
    """LangChain 对话 Agent：普通回复直接结束；需要出图则进入生图节点。"""
    session_id = str(state["session_id"])
    round_id = str(state["round_id"])
    speaker = state.get("current_speaker") or {}
    member_id = int(state.get("member_id") or (state.get("user_profile") or {}).get("member_id") or 0)

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "select_speaker",
            "current_speaker": {"id": speaker.get("id"), "name": speaker.get("name")},
        },
    )

    history = list(state.get("messages") or [])
    user_text = (state.get("user_message") or "").strip()
    if user_text and (
        not history
        or not isinstance(history[-1], HumanMessage)
        or str(history[-1].content).strip() != user_text
    ):
        history = history + [HumanMessage(content=user_text)]

    llm = _chat_llm().bind_tools([generate_image_tool])
    msgs: list[BaseMessage] = [SystemMessage(content=_system_prompt(state)), *history]

    assembled: AIMessage | None = None
    async for chunk in llm.astream(msgs):
        delta = message_chunk_text(chunk)
        if delta:
            await publisher.publish(
                session_id,
                round_id,
                {
                    "event": "speaker_model_stream",
                    "speaker_id": speaker.get("id"),
                    "speaker_name": speaker.get("name"),
                    "delta": delta,
                    "inner_node": "model",
                },
            )
        if assembled is None:
            assembled = chunk  # type: ignore[assignment]
        else:
            assembled = assembled + chunk  # type: ignore[operator]

    if assembled is None:
        assembled = AIMessage(content="抱歉，我暂时没有生成有效回复，请再试一次。")

    # astream 合并后可能是 AIMessageChunk；规范为 AIMessage
    tool_calls = list(getattr(assembled, "tool_calls", None) or [])
    if not isinstance(assembled, AIMessage) or type(assembled).__name__ == "AIMessageChunk":
        assembled = AIMessage(
            content=getattr(assembled, "content", "") or "",
            tool_calls=tool_calls,
            id=getattr(assembled, "id", None),
        )

    text = message_chunk_text(assembled).strip()
    image_prompt = _extract_image_prompt(assembled)

    # HumanMessage 已由本轮 stream_input / checkpointer 写入，节点只追加模型输出
    out_messages: list[BaseMessage] = [assembled]

    if text:
        await publisher.publish(
            session_id,
            round_id,
            {
                "event": "speaker",
                "speaker_id": speaker.get("id"),
                "speaker_name": speaker.get("name"),
                "content": text,
            },
        )
        await AgentLogService.save_model_message(
            user_id=member_id,
            session_id=session_id,
            round_id=round_id,
            type=MsgType.MODEL.value,
            current_speaker=speaker,
            role_type=RoleType.SPEAKER.value,
            message=text,
        )

    if image_prompt:
        # 工具调用落一条占位 ToolMessage，保持 messages 合法
        tool_call_id = ""
        tool_calls = assembled.tool_calls or []
        if tool_calls:
            tool_call_id = str(tool_calls[0].get("id") or tool_calls[0].get("tool_id") or "")
        out_messages.append(
            ToolMessage(
                content="已受理生图请求，交由生图节点处理。",
                tool_call_id=tool_call_id or "generate_image",
            )
        )
        return Command(
            goto="generate_image_node",
            update={
                "messages": out_messages,
                "image_prompt": image_prompt,
            },
        )

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "speaker_finished",
            "answer": text,
            "finish_reason": "stop",
        },
    )
    return Command(
        goto=END,
        update={
            "messages": out_messages,
            "image_prompt": None,
            "finished": True,
            "answer": text,
            "finish_reason": "stop",
        },
    )


async def generate_image_node(state: ImageChatState) -> dict[str, Any]:
    """生图节点：仅在对话 Agent 给出 image_prompt 后执行。"""
    session_id = str(state["session_id"])
    round_id = str(state["round_id"])
    speaker = state.get("current_speaker") or {}
    member_id = int(state.get("member_id") or (state.get("user_profile") or {}).get("member_id") or 0)
    raw_prompt = (state.get("image_prompt") or "").strip()
    if not raw_prompt:
        msg = "未收到有效的生图提示词"
        await publisher.publish(session_id, round_id, {"event": "error", "message": msg})
        return {"finished": True, "answer": msg, "finish_reason": "error"}

    style = state.get("agent_style_prompt")
    prompt = _compose_prompt(raw_prompt, style)
    model_id = int(state["image_model_id"])
    model_name, base_url, api_key = _load_image_model(model_id)

    await publisher.publish(
        session_id,
        round_id,
        {
            "event": "image_generating",
            "speaker_id": speaker.get("id"),
            "speaker_name": speaker.get("name"),
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
    image_bytes_list = [await _download_image_bytes(url) for url in remote_urls]
    saved = _persist_images(
        user_id=member_id,
        session_id=session_id,
        remote_urls=remote_urls,
        image_bytes_list=image_bytes_list,
    )
    _save_image_log(
        user_id=member_id,
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
            "speaker_id": speaker.get("id"),
            "speaker_name": speaker.get("name"),
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
    return {
        "finished": True,
        "answer": "",
        "finish_reason": "stop",
        "image_prompt": None,
    }


def build_image_chat_graph(checkpointer) -> CompiledStateGraph:
    graph = StateGraph(ImageChatState)
    graph.add_node("chat_agent_node", chat_agent_node)
    graph.add_node("generate_image_node", generate_image_node)
    graph.add_edge(START, "chat_agent_node")
    graph.add_edge("generate_image_node", END)
    return graph.compile(checkpointer=checkpointer)


_IMAGE_GRAPH: CompiledStateGraph | None = None
_IMAGE_GRAPH_CHECKPOINTER_ID: int | None = None


def get_image_chat_graph(checkpointer) -> CompiledStateGraph:
    global _IMAGE_GRAPH, _IMAGE_GRAPH_CHECKPOINTER_ID
    checkpointer_id = id(checkpointer)
    if _IMAGE_GRAPH is None or _IMAGE_GRAPH_CHECKPOINTER_ID != checkpointer_id:
        _IMAGE_GRAPH = build_image_chat_graph(checkpointer)
        _IMAGE_GRAPH_CHECKPOINTER_ID = checkpointer_id
    return _IMAGE_GRAPH
