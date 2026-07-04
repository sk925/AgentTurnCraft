from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.enums import FileType


class DocumentParseError(Exception):
    """知识库文档解析失败。"""

    def __init__(self, message: str, *, file_name: str | None = None) -> None:
        self.file_name = file_name
        super().__init__(message)


@dataclass(slots=True)
class DocumentSection:
    """解析后的文档片段（页、sheet、文本块等），供后续切块与向量化。"""

    index: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass(slots=True)
class ParsedDocument:
    """完整解析结果，保留全部片段，不做对话侧 10 万字符截断。"""

    file_name: str
    file_type: FileType
    sections: list[DocumentSection]

    @property
    def total_chars(self) -> int:
        return sum(section.char_count for section in self.sections)

    @property
    def is_empty(self) -> bool:
        return not self.sections or all(not section.content.strip() for section in self.sections)

    @property
    def full_text(self) -> str:
        return "\n\n".join(section.content for section in self.sections if section.content.strip())
