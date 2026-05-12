def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    """按字符滑动窗口分块（不引入额外依赖）。overlap 避免实体描述被切断。"""
    text = text.strip()
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    overlap = max(0, min(overlap, chunk_size - 1)) if chunk_size > 1 else 0
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks
