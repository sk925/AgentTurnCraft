"""MinIO（S3 兼容）上传工具。连接信息从 backend/.env 的 MINIO_* 读取（见 app.config.Settings）。"""

from __future__ import annotations

import threading
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, NamedTuple
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import settings

_singleton_client: Minio | None = None
_singleton_lock = threading.Lock()


class MinioUploadResult(NamedTuple):
    object_name: str
    etag: str


def _endpoint_host_and_secure(endpoint: str) -> tuple[str, bool]:
    raw = endpoint.strip()
    if not raw:
        raise ValueError("MINIO_ENDPOINT is empty")
    if "://" not in raw:
        return raw, False
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise ValueError(f"invalid MINIO_ENDPOINT: {endpoint!r}")
    return parsed.netloc, parsed.scheme == "https"


def _build_minio(endpoint: str, access_key: str, secret_key: str) -> Minio:
    host, secure = _endpoint_host_and_secure(endpoint)
    return Minio(host, access_key=access_key, secret_key=secret_key, secure=secure)


def get_minio_client(
    *,
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
) -> Minio:
    """
    返回 MinIO 客户端。

    未传 endpoint/access_key/secret_key 时，使用全局单例（线程安全懒加载，配置来自 Settings）。
    传入任一覆盖参数时，每次新建客户端（不纳入单例），便于测试或临时连接。
    """
    if endpoint is not None or access_key is not None or secret_key is not None:
        return _build_minio(
            endpoint or settings.minio_endpoint,
            access_key or settings.minio_access_key,
            secret_key or settings.minio_secret_key,
        )

    global _singleton_client
    if _singleton_client is not None:
        return _singleton_client
    with _singleton_lock:
        if _singleton_client is None:
            _singleton_client = _build_minio(
                settings.minio_endpoint,
                settings.minio_access_key,
                settings.minio_secret_key,
            )
        return _singleton_client


def ensure_bucket_exists(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_file(
    bucket: str,
    object_name: str,
    file_path: str | Path,
    *,
    content_type: str | None = None,
    client: Minio | None = None,
    ensure_bucket: bool = True,
) -> MinioUploadResult:
    """从本地路径上传到 MinIO。"""
    c = client or get_minio_client()
    if ensure_bucket:
        ensure_bucket_exists(c, bucket)
    path = Path(file_path)
    try:
        result = c.fput_object(
            bucket,
            object_name,
            str(path),
            content_type=content_type,
        )
    except S3Error:
        raise
    return MinioUploadResult(object_name=result.object_name, etag=result.etag)


def upload_stream(
    bucket: str,
    object_name: str,
    data: BinaryIO,
    length: int,
    *,
    content_type: str | None = None,
    client: Minio | None = None,
    ensure_bucket: bool = True,
) -> MinioUploadResult:
    """从二进制流上传（需预先知道 length）。"""
    c = client or get_minio_client()
    if ensure_bucket:
        ensure_bucket_exists(c, bucket)
    try:
        result = c.put_object(
            bucket,
            object_name,
            data,
            length,
            content_type=content_type,
        )
    except S3Error:
        raise
    return MinioUploadResult(object_name=result.object_name, etag=result.etag)


def upload_bytes(
    bucket: str,
    object_name: str,
    data: bytes,
    *,
    content_type: str | None = None,
    client: Minio | None = None,
    ensure_bucket: bool = True,
) -> MinioUploadResult:
    """从内存中的 bytes 上传。"""
    buf = BytesIO(data)
    return upload_stream(
        bucket,
        object_name,
        buf,
        len(data),
        content_type=content_type,
        client=client,
        ensure_bucket=ensure_bucket,
    )


def download_bytes(
    bucket: str,
    object_name: str,
    *,
    client: Minio | None = None,
) -> bytes:
    """从 MinIO 读取对象为完整 bytes。"""
    c = client or get_minio_client()
    resp = c.get_object(bucket, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()
