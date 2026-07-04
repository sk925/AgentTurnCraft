"""企业知识库：文档解析、切块、向量索引与检索。"""

from app.knowledge.constants import MAX_AGENT_KNOWLEDGE_BASES
from app.knowledge.chunker import (
    ChunkOptions,
    TextChunk,
    chunk_document,
    chunk_section,
    split_text_with_overlap,
)
from app.knowledge.parser import (
    DocumentParseError,
    DocumentSection,
    ParseOptions,
    ParsedDocument,
    parse_document,
    parse_document_from_minio,
    resolve_file_type,
)

__all__ = [
    "MAX_AGENT_KNOWLEDGE_BASES",
    "ChunkOptions",
    "DocumentParseError",
    "DocumentSection",
    "ParseOptions",
    "ParsedDocument",
    "TextChunk",
    "chunk_document",
    "chunk_section",
    "parse_document",
    "parse_document_from_minio",
    "resolve_file_type",
    "split_text_with_overlap",
]

def __getattr__(name: str):
    if name == "validate_agent_knowledge_base_binding":
        from app.knowledge.binding import validate_agent_knowledge_base_binding

        return validate_agent_knowledge_base_binding
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
