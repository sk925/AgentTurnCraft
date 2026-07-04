from __future__ import annotations

import csv
import json
from io import StringIO


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def split_text_blocks(text: str, *, max_chars: int) -> list[str]:
    """将长文本按字符上限切分为多个块，优先在换行处断开。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    blocks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            break_at = normalized.rfind("\n", start, end)
            if break_at > start + max_chars // 2:
                end = break_at + 1
        block = normalized[start:end].strip()
        if block:
            blocks.append(block)
        if end <= start:
            end = min(start + max_chars, length)
        start = end
    return blocks


def parse_json_text(data: bytes) -> str:
    text = decode_text(data)
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text


def parse_csv_text(data: bytes) -> str:
    text = decode_text(data)
    rows = list(csv.reader(StringIO(text)))
    return "\n".join("\t".join(row) for row in rows)
