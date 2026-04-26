from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import zipfile
import shutil

from app.database import get_db
from app.models import Skill
from app.schemas import SkillResponse

router = APIRouter()


@router.get("/skills", response_model=List[SkillResponse])
def get_skills(db: Session = Depends(get_db)):
    """获取技能列表"""
    skills = db.query(Skill).all()
    return skills


@router.post("/skills", response_model=SkillResponse)
async def upload_skill(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传技能压缩包"""
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
    description = ""

    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('# '):
                    name = line[2:].strip()
                elif line and not line.startswith('#'):
                    description = line
                    break

    skill = Skill(
        name=name,
        description=description,
        file_path=extract_dir
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    return skill


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: int, db: Session = Depends(get_db)):
    """删除技能"""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if skill.agents:
        raise HTTPException(status_code=400, detail="该技能有关联的智能体，请先解关联")

    if skill.file_path and os.path.exists(skill.file_path):
        shutil.rmtree(skill.file_path)

    db.delete(skill)
    db.commit()

    return {"message": "删除成功"}
