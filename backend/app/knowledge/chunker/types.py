from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TextChunk:
    """面向 Embedding 的最终文本块。"""

    index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class ChunkOptions:
    """切块参数。"""

    chunk_size: int = 800
    chunk_overlap: int = 120
    min_chunk_chars: int = 20

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap 不能为负数")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        if self.min_chunk_chars < 0:
            raise ValueError("min_chunk_chars 不能为负数")
