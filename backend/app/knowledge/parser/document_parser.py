from __future__ import annotations

from dataclasses import dataclass

from minio.error import S3Error

from app.config import settings
from app.enums import FileType
from app.knowledge.parser.file_type import resolve_file_type
from app.knowledge.parser.format_parsers import (
    parse_docx_sections,
    parse_pdf_sections,
    parse_plain_sections,
    parse_pptx_sections,
    parse_xlsx_sections,
)
from app.knowledge.parser.text_utils import parse_csv_text, parse_json_text, split_text_blocks
from app.knowledge.parser.types import DocumentParseError, DocumentSection, ParsedDocument
from app.utils.minio_storage import download_bytes


@dataclass(frozen=True, slots=True)
class ParseOptions:
    """知识库解析参数：控制分段粒度，不截断全文。"""

    max_text_block_chars: int = 8_000
    xlsx_rows_per_section: int = 200


def parse_document(
    *,
    data: bytes,
    file_name: str,
    mime_or_ext: str = "",
    options: ParseOptions | None = None,
) -> ParsedDocument:
    """解析文档字节流，返回结构化片段列表。"""
    opts = options or ParseOptions()
    file_type = resolve_file_type(mime_or_ext, file_name)
    if file_type is None:
        allowed = ", ".join(item.value for item in FileType)
        raise DocumentParseError(
            f"无法识别文件类型（mime_or_ext={mime_or_ext!r}, file_name={file_name!r}）。"
            f"支持的类型：{allowed}",
            file_name=file_name,
        )
    if not data:
        raise DocumentParseError("文件内容为空", file_name=file_name)

    try:
        sections = _parse_sections(data, file_type, opts)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(f"解析失败: {exc}", file_name=file_name) from exc

    for index, section in enumerate(sections):
        section.index = index

    return ParsedDocument(file_name=file_name, file_type=file_type, sections=sections)


def parse_document_from_minio(
    *,
    object_key: str,
    file_name: str,
    mime_or_ext: str = "",
    bucket: str | None = None,
    options: ParseOptions | None = None,
) -> ParsedDocument:
    """从 MinIO 读取并解析文档。"""
    try:
        data = download_bytes(bucket or settings.minio_bucket, object_key)
    except S3Error as exc:
        raise DocumentParseError(f"从对象存储读取文件失败: {exc.message}", file_name=file_name) from exc
    return parse_document(
        data=data,
        file_name=file_name,
        mime_or_ext=mime_or_ext,
        options=options,
    )


def _parse_sections(data: bytes, file_type: FileType, opts: ParseOptions) -> list[DocumentSection]:
    if file_type in (FileType.TXT, FileType.MD, FileType.HTML, FileType.XML):
        return parse_plain_sections(data, max_block_chars=opts.max_text_block_chars)
    if file_type == FileType.JSON:
        text = parse_json_text(data)
        return _sections_from_text(text, file_type=file_type, max_block_chars=opts.max_text_block_chars)
    if file_type == FileType.CSV:
        text = parse_csv_text(data)
        return _sections_from_text(text, file_type=file_type, max_block_chars=opts.max_text_block_chars)
    if file_type == FileType.PDF:
        return parse_pdf_sections(data)
    if file_type == FileType.DOCX:
        return parse_docx_sections(data, max_block_chars=opts.max_text_block_chars)
    if file_type == FileType.XLSX:
        return parse_xlsx_sections(data, rows_per_section=opts.xlsx_rows_per_section)
    if file_type == FileType.PPTX:
        return parse_pptx_sections(data)
    raise DocumentParseError(f"未实现的类型: {file_type.value}")


def _sections_from_text(text: str, *, file_type: FileType, max_block_chars: int) -> list[DocumentSection]:
    blocks = split_text_blocks(text, max_chars=max_block_chars)
    return [
        DocumentSection(
            index=index,
            content=block,
            metadata={"file_type": file_type.value, "block_index": index},
        )
        for index, block in enumerate(blocks)
    ]
