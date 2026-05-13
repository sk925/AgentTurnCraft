from enum import Enum


class FileType(str, Enum):
    """文件类型"""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    HTML = "html"
    MD = "md"
