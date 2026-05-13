from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, get_current_user_id
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.query_access import list_skills
import os
import zipfile
import shutil

from app.database import get_db
from app.models import Skill
from app.schemas import ApiResponse, SkillResponse, success_response

router = APIRouter()


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
    """上传技能压缩包（须同时提交技能描述）"""
    desc = (description or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="请填写技能描述")
    if len(desc) > 2000:
        raise HTTPException(status_code=400, detail="技能描述过长，请控制在 2000 字以内")

    upload_dir = ".uploads/skills"
    os.makedirs(upload_dir, exist_ok=True)

    zip_path = os.path.join(upload_dir, file.filename)
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    skill_name = file.filename.replace(".zip", "")
    extract_dir = os.path.join(upload_dir, skill_name)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    os.remove(zip_path)

    skill_md_path = os.path.join(extract_dir, "skill.md")
    name = skill_name

    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    name = line[2:].strip()
                    break

    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_admin else RESOURCE_TYPE_CUSTOM
    skill = Skill(
        user_id=current_user.id,
        name=name,
        description=desc,
        file_path=extract_dir,
        resource_type=resource_type,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    return success_response(skill)


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, user_id: Annotated[int, Depends(get_current_user_id)], db: Session = Depends(get_db)):
    """删除技能（仅创建人可删）"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    if skill.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该技能")

    if skill.agents:
        raise HTTPException(status_code=400, detail="该技能有关联的智能体，请先解关联")

    if skill.file_path and os.path.exists(skill.file_path):
        shutil.rmtree(skill.file_path)

    db.delete(skill)
    db.commit()

    return success_response({"deleted": True}, message="删除成功")
