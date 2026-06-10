import logging
import re
from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, get_current_user_id
from app.chat.base.skill_materializer import (
    build_skill_object_key,
    parse_skill_info_from_zip,
    remove_skill_cache,
)
from app.config import settings
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.chat.base.models import Skill
from app.chat.base.schemas import ApiResponse, SkillResponse, success_response
from app.query_access import list_skills
from app.utils.minio_storage import remove_object, upload_bytes

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_SKILL_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB


@router.get("/skills", response_model=ApiResponse[List[SkillResponse]])
def get_skills(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取技能列表（须登录：内置 + 当前用户自己的自定义）"""
    skills = list_skills(db, current_user)
    return success_response(skills)


@router.post("/skills", response_model=ApiResponse[SkillResponse])
async def upload_skill(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    description: str = Form(..., description="技能描述，必填"),
    db: Session = Depends(get_db),
):
    """上传技能压缩包到 MinIO（须同时提交技能描述）。"""
    desc = (description or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="请填写技能描述")
    if len(desc) > 2000:
        raise HTTPException(status_code=400, detail="技能描述过长，请控制在 2000 字以内")

    raw_name = file.filename or "skill.zip"
    if not raw_name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的技能包")

    content = await file.read()
    if len(content) > _MAX_SKILL_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"技能包过大，最大允许 {_MAX_SKILL_UPLOAD_BYTES // (1024 * 1024)} MiB",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="技能包为空")

    fallback_name = re.sub(r"\.zip$", "", raw_name, flags=re.IGNORECASE)
    name, skill_desc = parse_skill_info_from_zip(content, fallback_name)

    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_admin else RESOURCE_TYPE_CUSTOM
    skill = Skill(
        user_id=current_user.id,
        name=name,
        description=desc,
        file_path="",
        resource_type=resource_type,
        skill_desc=skill_desc,
    )
    db.add(skill)
    db.flush()

    object_key = build_skill_object_key(current_user.id, skill.id, raw_name)
    try:
        upload_bytes(
            settings.minio_bucket,
            object_key,
            content,
            content_type="application/zip",
        )
    except S3Error as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"对象存储写入失败: {e.message}") from e

    skill.file_path = object_key
    db.commit()
    db.refresh(skill)

    return success_response(skill)


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, user_id: Annotated[int, Depends(get_current_user_id)], db: Session = Depends(get_db)):
    """删除技能（仅创建人可删）。"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    if skill.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该技能")

    if skill.agents:
        raise HTTPException(status_code=400, detail="该技能有关联的智能体，请先解关联")

    if skill.file_path:
        try:
            remove_object(settings.minio_bucket, skill.file_path)
        except S3Error as e:
            logger.warning("delete skill object %s failed: %s", skill.file_path, e.message)

    remove_skill_cache(skill_id)

    db.delete(skill)
    db.commit()

    from app.chat.base.skill_cache_broadcast import broadcast_skill_deleted

    broadcast_skill_deleted(skill_id)

    return success_response({"deleted": True}, message="删除成功")
