from __future__ import annotations

from app.knowledge.chunker.types import ChunkOptions


def split_text_with_overlap(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    """将文本切分为带重叠的块，优先在换行处断开。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            break_at = normalized.rfind("\n", start, end)
            if break_at > start + chunk_size // 2:
                end = break_at + 1

        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break

        next_start = end - chunk_overlap
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def split_text_with_options(text: str, options: ChunkOptions) -> list[str]:
    return split_text_with_overlap(
        text,
        chunk_size=options.chunk_size,
        chunk_overlap=options.chunk_overlap,
    )
