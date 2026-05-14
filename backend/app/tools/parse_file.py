from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO
from pathlib import Path

from minio.error import S3Error

from app.config import settings
from app.enums import FileType
from app.models.upload_file import UploadFileService
from app.utils.minio_storage import download_bytes
from langchain.tools import tool

_MAX_CHARS = 100_000

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


def _resolve_file_type(mime_or_ext: str, file_name: str) -> FileType | None:
    """结合数据库中的 MIME（或扩展名）与原始文件名推断 FileType。"""
    raw = (mime_or_ext or "").strip().lower()
    if raw in {e.value for e in FileType}:
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


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _truncate(text: str) -> str:
    if len(text) <= _MAX_CHARS:
        return text
    return (
        text[:_MAX_CHARS]
        + f"\n\n[内容过长已截断，共 {len(text)} 字符，仅保留前 {_MAX_CHARS} 字符]"
    )


def _parse_plain(data: bytes) -> str:
    return _decode_text(data)


def _parse_json_text(data: bytes) -> str:
    text = _decode_text(data)
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text


def _parse_csv(data: bytes) -> str:
    text = _decode_text(data)
    buf = StringIO(text)
    rows = list(csv.reader(buf))
    return "\n".join("\t".join(row) for row in rows)


def _parse_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _parse_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _parse_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        blocks: list[str] = []
        for sheet in wb.worksheets:
            blocks.append(f"## {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                line = "\t".join("" if c is None else str(c) for c in row)
                blocks.append(line)
        return "\n".join(blocks)
    finally:
        wb.close()


def _parse_pptx(data: bytes) -> str:
    """
    按文档结构抽取：分页、版式名、标题占位、组合形状递归、表格按行列、其余文本框按层级缩进。
    （不解析 SmartArt/图表内部数据；纯图无文字页可能为空。）
    """
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    prs = Presentation(BytesIO(data))
    parts: list[str] = []

    def _cell_text(s: str) -> str:
        return " ".join(s.replace("\r", "").split())

    def _collect_shape(shape, lines: list[str], indent: str, *, skip_shape: object | None) -> None:
        if skip_shape is not None and shape is skip_shape:
            return
        st = shape.shape_type
        if st == MSO_SHAPE_TYPE.GROUP:
            for child in shape.shapes:  # type: ignore[union-attr]
                _collect_shape(child, lines, indent + "  ", skip_shape=skip_shape)
            return
        if getattr(shape, "has_table", False):
            lines.append(f"{indent}### 表格")
            for row in shape.table.rows:  # type: ignore[union-attr]
                cells = [_cell_text(c.text) for c in row.cells]
                lines.append(f"{indent}" + "\t".join(cells))
            lines.append("")
            return
        if getattr(shape, "has_text_frame", False):
            t = shape.text_frame.text.strip()  # type: ignore[union-attr]
            if t:
                # 保留段落换行，便于区分列表与多段正文
                for block in t.split("\n"):
                    block = block.strip()
                    if block:
                        lines.append(f"{indent}{block}")
            return
        if st in (MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.DIAGRAM, MSO_SHAPE_TYPE.IGX_GRAPHIC):
            kind_labels = {
                MSO_SHAPE_TYPE.CHART: "图表",
                MSO_SHAPE_TYPE.DIAGRAM: "图示",
                MSO_SHAPE_TYPE.IGX_GRAPHIC: "SmartArt",
            }
            label = kind_labels.get(st, "嵌入图形")
            lines.append(f"{indent}[{label}：无法作为纯文本结构化抽取，已跳过]")

    for idx, slide in enumerate(prs.slides, start=1):
        parts.append(f"## 第 {idx} 页")
        try:
            layout = slide.slide_layout.name.strip()
            if layout:
                parts.append(f"- **版式**: {layout}")
        except (AttributeError, ValueError):
            pass

        title_ph = None
        try:
            title_ph = slide.shapes.title
        except (AttributeError, ValueError):
            pass
        if title_ph is not None and title_ph.text and title_ph.text.strip():
            parts.append(f"- **标题**: {title_ph.text.strip()}")
        parts.append("")

        slide_lines: list[str] = []
        for shape in slide.shapes:
            _collect_shape(shape, slide_lines, "", skip_shape=title_ph)

        chunk = "\n".join(slide_lines).strip()
        if chunk:
            parts.append(chunk)
        parts.append("")

    return "\n".join(parts).strip()


def _parse_by_type(kind: FileType, data: bytes) -> str:
    if kind in (FileType.TXT, FileType.MD, FileType.HTML, FileType.XML):
        return _parse_plain(data) 
    if kind == FileType.JSON:
        return _parse_json_text(data)
    if kind == FileType.CSV:
        return _parse_csv(data)
    if kind == FileType.PDF:
        return _parse_pdf(data)
    if kind == FileType.DOCX:
        return _parse_docx(data)
    if kind == FileType.XLSX:
        return _parse_xlsx(data)
    if kind == FileType.PPTX:
        return _parse_pptx(data)
    raise ValueError(f"未实现的类型: {kind}")


@tool("parse_file_by_id", description="根据文件ID解析文件内容")
def parse_file_by_id(file_id: int) -> str:
    """根据文件ID解析文件内容"""
    upload_file = UploadFileService.get_upload_file_by_id(file_id)
    if not upload_file:
        return "文件不存在"
    kind = _resolve_file_type(upload_file.file_type, upload_file.file_name)
    if kind is None:
        allowed = ", ".join(e.value for e in FileType)
        return (
            f"无法识别文件类型（file_type={upload_file.file_type!r}, "
            f"文件名={upload_file.file_name!r}）。支持的类型：{allowed}"
        )

    try:
        data = download_bytes(settings.minio_bucket, upload_file.file_path)
    except S3Error as e:
        return f"从对象存储读取文件失败: {e.message}"

    if not data:
        return "文件内容为空"

    try:
        text = _parse_by_type(kind, data).strip()
    except Exception as e:
        return f"解析失败: {e}"

    if not text:
        return "解析结果为空（可能为扫描版 PDF 或加密文档等）"

    return _truncate(text)
