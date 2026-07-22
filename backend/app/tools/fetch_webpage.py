"""抓取网页正文内容的工具。"""

from __future__ import annotations

import json
import re
from html import unescape

from bs4 import BeautifulSoup
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.utils.http_fetch import fetch_url_bytes, normalize_http_url

_MAX_CHARS = 100_000


class FetchWebpageInput(BaseModel):
    """fetch_webpage 工具的入参。"""

    url: str = Field(description="要抓取的网页 URL，必须以 http:// 或 https:// 开头")
    max_chars: int = Field(
        default=50_000,
        description="返回正文的最大字符数",
        ge=1_000,
        le=_MAX_CHARS,
    )


def _decode_bytes(data: bytes, content_type: str | None) -> str:
    charset = "utf-8"
    if content_type:
        match = re.search(r"charset=([\w-]+)", content_type, re.I)
        if match:
            charset = match.group(1)
    for enc in (charset, "utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            return data.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _extract_html_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    text = unescape(re.sub(r"\n{3,}", "\n\n", text))
    return title, text


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + f"\n\n[内容过长已截断，共 {len(text)} 字符，仅保留前 {max_chars} 字符]"
    )


def _format_result(url: str, title: str, body: str, max_chars: int) -> str:
    parts: list[str] = [f"URL: {url}"]
    if title:
        parts.append(f"标题: {title}")
    parts.append("")
    parts.append(_truncate(body.strip(), max_chars))
    return "\n".join(parts)


def fetch_webpage_content(url: str, max_chars: int = 50_000) -> str:
    """抓取网页并提取可读正文。"""
    try:
        normalized = normalize_http_url(url)
        fetched = fetch_url_bytes(normalized)
    except ValueError as exc:
        return f"无效请求: {exc}"
    except Exception as exc:
        return f"请求失败: {exc}"

    final_url = fetched.final_url
    content_type = fetched.content_type
    data = fetched.data
    if not data:
        return f"页面内容为空: {final_url}"

    if "application/json" in content_type.lower():
        text = _decode_bytes(data, content_type)
        try:
            body = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            body = text
        return _format_result(final_url, "", body, max_chars)

    if "text/" not in content_type.lower() and "html" not in content_type.lower():
        return (
            f"不支持的内容类型: {content_type or 'unknown'}\n"
            f"URL: {final_url}\n"
            "提示：该链接可能指向 PDF、Word 等文件，请改用 parse_file 并传入 url 参数。"
        )

    html = _decode_bytes(data, content_type)
    title, body = _extract_html_text(html)
    if not body:
        return (
            f"未能从页面提取正文（可能是纯 JS 渲染页面）\n"
            f"URL: {final_url}\n"
            f"原始 HTML 长度: {len(html)} 字符"
        )
    return _format_result(final_url, title, body, max_chars)


@tool(
    "fetch_webpage",
    args_schema=FetchWebpageInput,
    description=(
        "抓取指定 URL 的网页内容并提取正文文本。"
        "当用户提供了 http/https 链接、要求查看网页/公告/文档页面内容时使用；"
        "不要凭记忆猜测网页内容。"
        "注意：纯 JavaScript 动态渲染的页面可能无法完整提取；"
        "PDF/Word/Excel 等文件链接请改用 parse_file（传入 url）。"
    ),
)
def fetch_webpage(url: str, max_chars: int = 50_000) -> str:
    """抓取网页正文。"""
    return fetch_webpage_content(url, max_chars=max_chars)
