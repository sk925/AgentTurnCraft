from __future__ import annotations

from pathlib import Path

from app.enums import FileType

_MIME_TO_TYPE: dict[str, FileType] = {
    "application/pdf": FileType.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.XLSX,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": FileType.PPTX,
    "text/plain": FileType.TXT,
    "text/csv": FileType.CSV,
    "application/csv": FileType.CSV,
    "application/json": FileType.JSON,
    "application/xml": FileType.XML,
    "text/xml": FileType.XML,
    "text/html": FileType.HTML,
    "text/markdown": FileType.MD,
}


def resolve_file_type(mime_or_ext: str, file_name: str) -> FileType | None:
    """结合 MIME 与文件名扩展名推断文档类型。"""
    raw = (mime_or_ext or "").strip().lower()
    if raw in {item.value for item in FileType}:
        return FileType(raw)

    base = raw.split(";", 1)[0].strip()
    if base in _MIME_TO_TYPE:
        return _MIME_TO_TYPE[base]
    if raw in _MIME_TO_TYPE:
        return _MIME_TO_TYPE[raw]
    if base == "application/x-pdf":
        return FileType.PDF

    ext = Path(file_name).suffix.lower().lstrip(".")
    if not ext:
        return None
    try:
        return FileType(ext)
    except ValueError:
        return None
