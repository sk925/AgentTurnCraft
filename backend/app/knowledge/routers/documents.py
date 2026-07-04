from __future__ import annotations

from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile as FastAPIUploadFile
from fastapi.responses import StreamingResponse
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.config import settings
from app.database import get_db
from app.exceptions import AppException
from app.knowledge.constants import MAX_KNOWLEDGE_UPLOAD_BYTES
from app.knowledge.indexer import KnowledgeIndexService, build_knowledge_object_key
from app.knowledge.models import KnowledgeDocument
from app.knowledge.schemas import KnowledgeDocumentResponse
from app.knowledge.tasks import run_index_document_task
from app.manage.deps import require_manage_roles
from app.chat.base.schemas import ApiResponse, success_response
from app.query_access import get_knowledge_base_if_readable
from app.utils.minio_storage import download_bytes, upload_bytes

router = APIRouter()


def _optional_embedding_model_id(raw: str | None) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    return int(str(raw).strip())


@router.get(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=ApiResponse[list[KnowledgeDocumentResponse]],
)
def list_knowledge_documents(
    knowledge_base_id: int,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    knowledge_base = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    rows = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.knowledge_base_id == knowledge_base_id)
        .order_by(KnowledgeDocument.create_time.desc())
        .all()
    )
    return success_response(rows)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=ApiResponse[KnowledgeDocumentResponse],
)
async def upload_knowledge_document(
    knowledge_base_id: int,
    background_tasks: BackgroundTasks,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
    file: FastAPIUploadFile = File(...),
    embedding_model_id: Annotated[str | None, Form()] = None,
):
    knowledge_base = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if knowledge_base.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权上传：仅创建人可向该知识库上传文档")

    raw_name = file.filename or "unnamed"
    file_name = raw_name[:255] if len(raw_name) > 255 else raw_name
    content_type = (file.content_type or "application/octet-stream").strip()[:255]
    data = await file.read()
    if len(data) > MAX_KNOWLEDGE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大允许 {MAX_KNOWLEDGE_UPLOAD_BYTES // (1024 * 1024)} MiB",
        )

    service = KnowledgeIndexService(db)
    try:
        service.resolve_embedding_model_id(
            knowledge_base,
            _optional_embedding_model_id(embedding_model_id),
        )
    except AppException as exc:
        raise HTTPException(status_code=exc.code, detail=exc.message) from exc

    document = service.create_document_record(
        knowledge_base=knowledge_base,
        user_id=current_user.id,
        file_name=file_name,
        file_path="pending",
        file_type=content_type,
        file_size=len(data),
    )
    object_key = build_knowledge_object_key(
        user_id=current_user.id,
        knowledge_base_id=knowledge_base.id,
        document_id=document.id,
        file_name=file_name,
    )

    try:
        upload_bytes(settings.minio_bucket, object_key, data, content_type=content_type or None)
    except S3Error as exc:
        db.delete(document)
        db.commit()
        raise HTTPException(status_code=502, detail=f"对象存储写入失败: {exc.message}") from exc

    document.file_path = object_key
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_index_document_task, document.id)
    return success_response(document, message="上传成功，正在索引")


@router.get("/knowledge-bases/{knowledge_base_id}/documents/{document_id}/download")
def download_knowledge_document(
    knowledge_base_id: int,
    document_id: int,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    knowledge_base = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    if not document.file_path or document.file_path == "pending":
        raise HTTPException(status_code=404, detail="文件尚未上传完成")

    try:
        data = download_bytes(settings.minio_bucket, document.file_path)
    except S3Error as exc:
        raise HTTPException(status_code=502, detail=f"对象存储读取失败: {exc.message}") from exc

    media_type = (document.file_type or "application/octet-stream").strip() or "application/octet-stream"
    encoded_name = quote(document.file_name)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
    }
    return StreamingResponse(BytesIO(data), media_type=media_type, headers=headers)


@router.delete("/knowledge-bases/{knowledge_base_id}/documents/{document_id}")
def delete_knowledge_document(
    knowledge_base_id: int,
    document_id: int,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    knowledge_base = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if knowledge_base.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除文档")

    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    KnowledgeIndexService(db).delete_document(document)
    return success_response({"deleted": True}, message="删除成功")


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents/{document_id}/reindex",
    response_model=ApiResponse[KnowledgeDocumentResponse],
)
def reindex_knowledge_document(
    knowledge_base_id: int,
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    knowledge_base = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if knowledge_base.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：仅创建人可重新索引文档")

    document = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    service = KnowledgeIndexService(db)
    try:
        service.prepare_reindex(document)
    except AppException as exc:
        raise HTTPException(status_code=exc.code, detail=exc.message) from exc

    db.commit()
    db.refresh(document)
    background_tasks.add_task(run_index_document_task, document.id)
    return success_response(document, message="已开始重新索引")
