from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from app.config import settings

logger = logging.getLogger(__name__)

PdfTextSource = Literal["text_layer", "ocr"]

_ocr_engine: object | None = None


@dataclass(frozen=True, slots=True)
class PdfPageText:
    page_number: int
    text: str
    source: PdfTextSource
    page_count: int


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _extract_text_layer_pages(data: bytes) -> tuple[list[str], int]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    page_count = len(reader.pages)
    texts: list[str] = []
    for page in reader.pages:
        texts.append((page.extract_text() or "").strip())
    return texts, page_count


def _ocr_page_image(page) -> str:
    import fitz
    import numpy as np

    matrix = fitz.Matrix(settings.pdf_ocr_render_scale, settings.pdf_ocr_render_scale)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    channels = pix.n
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, channels)
    if channels == 4:
        img = img[:, :, :3]

    engine = _get_ocr_engine()
    result, _ = engine(img)
    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        if len(item) >= 2 and item[1]:
            lines.append(str(item[1]).strip())
    return "\n".join(line for line in lines if line)


def _ocr_pdf_pages(data: bytes, *, page_numbers: list[int]) -> dict[int, str]:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        texts: dict[int, str] = {}
        for page_number in page_numbers:
            if page_number < 1 or page_number > len(doc):
                continue
            page = doc[page_number - 1]
            text = _ocr_page_image(page).strip()
            if text:
                texts[page_number] = text
        return texts
    finally:
        doc.close()


def extract_pdf_pages(data: bytes, *, ocr_if_empty: bool | None = None) -> list[PdfPageText]:
    """提取 PDF 每页文本；文字层为空时可 OCR 扫描页。"""
    text_layer_pages, page_count = _extract_text_layer_pages(data)
    if page_count == 0:
        return []

    use_ocr = settings.pdf_ocr_enabled if ocr_if_empty is None else ocr_if_empty
    max_pages = settings.pdf_ocr_max_pages
    if page_count > max_pages:
        logger.warning("PDF page count %s exceeds pdf_ocr_max_pages=%s", page_count, max_pages)

    effective_page_count = min(page_count, max_pages)
    empty_page_numbers = [
        page_number
        for page_number, text in enumerate(text_layer_pages[:effective_page_count], start=1)
        if not text
    ]

    ocr_texts: dict[int, str] = {}
    if use_ocr and empty_page_numbers:
        try:
            ocr_texts = _ocr_pdf_pages(data, page_numbers=empty_page_numbers)
            if ocr_texts:
                logger.info("PDF OCR extracted text from %s/%s empty pages", len(ocr_texts), len(empty_page_numbers))
        except Exception:
            logger.exception("PDF OCR failed")

    pages: list[PdfPageText] = []
    for page_number in range(1, effective_page_count + 1):
        text_layer = text_layer_pages[page_number - 1]
        if text_layer:
            pages.append(
                PdfPageText(
                    page_number=page_number,
                    text=text_layer,
                    source="text_layer",
                    page_count=page_count,
                )
            )
            continue

        ocr_text = ocr_texts.get(page_number, "")
        if ocr_text:
            pages.append(
                PdfPageText(
                    page_number=page_number,
                    text=ocr_text,
                    source="ocr",
                    page_count=page_count,
                )
            )

    return pages


def extract_pdf_full_text(data: bytes) -> str:
    pages = extract_pdf_pages(data)
    return "\n\n".join(page.text for page in pages if page.text.strip())
