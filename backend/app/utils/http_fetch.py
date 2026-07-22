"""HTTP URL 下载与 SSRF 校验（供 fetch_webpage / parse_file 共用）。"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import httpx

DEFAULT_TIMEOUT = 30.0
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)


@dataclass(frozen=True)
class UrlFetchResult:
    data: bytes
    content_type: str
    final_url: str
    filename_hint: str


def normalize_http_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise ValueError("URL 不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http:// 或 https:// 链接")
    if not parsed.netloc:
        raise ValueError("URL 格式无效，缺少域名")
    return url


def _hostname_blocked(hostname: str) -> bool:
    host = hostname.strip().lower().rstrip(".")
    if not host:
        return True
    if host in _BLOCKED_HOSTNAMES:
        return True
    if host.endswith(".localhost"):
        return True

    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolve_blocked(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def assert_url_allowed(url: str) -> None:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if _hostname_blocked(hostname):
        raise ValueError("不允许访问内网或本机地址")
    if _resolve_blocked(hostname):
        raise ValueError("不允许访问内网或本机地址")


def _filename_from_headers(url: str, content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    match = re.search(
        r"filename\*=utf-8''([^;]+)|filename=\"([^\"]+)\"|filename=([^;]+)",
        content_disposition,
        re.I,
    )
    if not match:
        return None
    name = next(group for group in match.groups() if group)
    return unquote(name.strip().strip("'"))


def _filename_from_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    name = path.rsplit("/", 1)[-1].strip()
    return name or "download"


def fetch_url_bytes(
    url: str,
    *,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    timeout: float = DEFAULT_TIMEOUT,
) -> UrlFetchResult:
    normalized = normalize_http_url(url)
    assert_url_allowed(normalized)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        trust_env=False,
    ) as client:
        with client.stream("GET", normalized, headers=headers) as response:
            response.raise_for_status()
            final_url = str(response.url)
            assert_url_allowed(final_url)

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(
                        f"文件过大（>{max_bytes // (1024 * 1024)}MB），请缩小范围或改用其他方式"
                    )
                chunks.append(chunk)

            data = b"".join(chunks)
            content_type = response.headers.get("content-type", "")
            filename = _filename_from_headers(
                final_url,
                response.headers.get("content-disposition"),
            ) or _filename_from_url(final_url)
            return UrlFetchResult(
                data=data,
                content_type=content_type,
                final_url=final_url,
                filename_hint=filename,
            )
