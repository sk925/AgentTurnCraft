from __future__ import annotations

from app.knowledge.chunker.text_chunker import split_text_with_options
from app.knowledge.chunker.types import ChunkOptions, TextChunk
from app.knowledge.parser.types import DocumentSection, ParsedDocument


def chunk_section(section: DocumentSection, *, options: ChunkOptions | None = None) -> list[TextChunk]:
    """将单个解析片段继续切分为 Embedding 用文本块。"""
    opts = options or ChunkOptions()
    content = section.content.strip()
    if not content or len(content) < opts.min_chunk_chars:
        return []

    parts = split_text_with_options(content, opts)
    chunks: list[TextChunk] = []
    for local_index, part in enumerate(parts):
        if len(part.strip()) < opts.min_chunk_chars:
            continue
        chunks.append(
            TextChunk(
                index=local_index,
                content=part,
                metadata={
                    **section.metadata,
                    "section_index": section.index,
                    "chunk_index_in_section": local_index,
                },
            )
        )
    return chunks


def chunk_document(parsed: ParsedDocument, *, options: ChunkOptions | None = None) -> list[TextChunk]:
    """将解析后的文档切分为 Embedding 用文本块列表。"""
    opts = options or ChunkOptions()
    chunks: list[TextChunk] = []

    for section in parsed.sections:
        section_chunks = chunk_section(section, options=opts)
        for chunk in section_chunks:
            chunk.metadata = {
                **chunk.metadata,
                "file_name": parsed.file_name,
                "file_type": parsed.file_type.value,
            }
            chunks.append(chunk)

    for index, chunk in enumerate(chunks):
        chunk.index = index

    return chunks
