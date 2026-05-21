import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile as FastAPIUploadFile
from minio.error import S3Error

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.chat.base.models.upload_file import UploadFile as UploadFileModel
from app.chat.base.models.upload_file import UploadFileService
from app.chat.base.schemas import ApiResponse, UploadFileResponse, success_response
from app.utils.minio_storage import upload_bytes
from app.utils.snowflake import get_snowflake_id

upload_file_router = APIRouter(prefix="/upload_file", tags=["upload_file"])

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MiB


def _safe_filename(name: str) -> str:
    base = re.sub(r"[/\\]", "", name).strip() or "file"
    base = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", base)
    return base[:200] if len(base) > 200 else base


@upload_file_router.post("", response_model=ApiResponse[UploadFileResponse])
async def upload_user_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: FastAPIUploadFile = File(...),
):
    """上传文件到 MinIO，并写入 upload_file 表。"""
    raw_name = file.filename or "unnamed"
    file_name = raw_name[:255] if len(raw_name) > 255 else raw_name
    content_type = (file.content_type or "application/octet-stream").strip()[:255]

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"文件过大，最大允许 {_MAX_UPLOAD_BYTES // (1024 * 1024)} MiB")

    file_id = get_snowflake_id()
    safe = _safe_filename(file_name)
    object_name = f"{current_user.id}/{file_id}_{safe}"

    try:
        upload_bytes(
            settings.minio_bucket,
            object_name,
            data,
            content_type=content_type or None,
        )
    except S3Error as e:
        raise HTTPException(status_code=502, detail=f"对象存储写入失败: {e.message}") from e

    row = UploadFileModel(
        id=file_id,
        user_id=current_user.id,
        file_name=file_name,
        file_path=object_name,
        file_type=content_type,
        file_size=len(data),
    )
    upload_file_response = UploadFileService.create_upload_file(row)


    return success_response(upload_file_response, message="上传成功")


 
