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


class PermissionMenu(str, Enum):
    """侧边栏菜单权限：成员名为接口/库中的 permission.code，值为展示用名称。"""

    agent_management = "智能体"
    skill_management = "技能"
    group_management = "群组"
    chat = "对话"
    group_chat = "群聊"
