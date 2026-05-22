"""
Custom ChatOpenAI subclass that handles DeepSeek's reasoning_content field.

DeepSeek's thinking mode (deepseek-reasoner) returns `reasoning_content` alongside
`content` in streaming deltas. This field MUST be passed back to the API in subsequent
requests for the same conversation. Without this, the API rejects with:
"The `reasoning_content` in the thinking mode must be passed back to the API."

The OpenAI SDK (v2.32.0) captures extra fields via Pydantic's model_extra, but
langchain_openai's _convert_delta_to_message_chunk() does not extract reasoning_content
from the delta dict. This class fixes that by:

1. Capturing reasoning_content from stream deltas into additional_kwargs
2. Adding reasoning_content back to assistant message dicts in API requests
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_core.messages.ai import AIMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI


class DeepSeekChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that preserves DeepSeek reasoning_content across turns."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        """Extract reasoning_content from stream delta and store in additional_kwargs."""
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )

        if generation_chunk is not None:
            choices = (
                chunk.get("choices", [])
                or chunk.get("chunk", {}).get("choices", [])
            )
            if choices:
                delta = choices[0].get("delta", {})
                reasoning_content = delta.get("reasoning_content")
                if reasoning_content is not None:
                    msg = generation_chunk.message
                    if isinstance(msg, AIMessageChunk):
                        existing = msg.additional_kwargs.get("reasoning_content", "")
                        msg.additional_kwargs["reasoning_content"] = (
                            existing + reasoning_content
                        )

        return generation_chunk

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        """Extract reasoning_content from non-streaming response message."""
        result = super()._create_chat_result(response, generation_info)

        response_dict = (
            response if isinstance(response, dict) else response.model_dump()
        )
        choices = response_dict.get("choices", [])
        for i, choice in enumerate(choices):
            message = choice.get("message", {})
            reasoning_content = message.get("reasoning_content")
            if reasoning_content and i < len(result.generations):
                gen_msg = result.generations[i].message
                if isinstance(gen_msg, AIMessage):
                    gen_msg.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Inject reasoning_content into assistant message dicts."""
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        if "messages" not in payload:
            return payload

        messages = self._convert_input(input_).to_messages()

        for msg, msg_dict in zip(messages, payload["messages"]):
            reasoning_content = msg.additional_kwargs.get("reasoning_content")
            if reasoning_content and msg_dict.get("role") == "assistant":
                msg_dict["reasoning_content"] = reasoning_content

        return payload