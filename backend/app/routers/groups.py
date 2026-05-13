from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.auth import CurrentUser, get_current_user, get_current_user_id
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.models import Agent, Group
from app.query_access import get_group_if_readable, list_groups
from app.schemas import (
    ApiResponse,
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    success_response,
)

router = APIRouter()


@router.get("/groups", response_model=ApiResponse[List[GroupResponse]])
def get_groups(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取群组列表（须登录：内置 + 当前用户自己的）"""
    groups = list_groups(db, current_user)
    return success_response(groups)


@router.post("/groups", response_model=ApiResponse[GroupResponse])
def create_group(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    group: GroupCreate,
    db: Session = Depends(get_db),
):
    """创建群组"""
    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_admin else RESOURCE_TYPE_CUSTOM
    db_group = Group(
        name=group.name,
        description=group.description,
        user_id=current_user.id,
        resource_type=resource_type,
    )
    db.add(db_group)
    db.flush()

    if group.agent_ids:
        agents = db.query(Agent).filter(
            Agent.id.in_(group.agent_ids),
            or_(
                Agent.user_id == current_user.id,
                Agent.resource_type == RESOURCE_TYPE_BUILTIN,
            ),
        ).all()
        db_group.agents = agents

    db.commit()
    db.refresh(db_group)
    return success_response(db_group)


@router.put("/groups/{group_id}", response_model=ApiResponse[GroupResponse])
def update_group(
    group_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
    group_data: GroupUpdate,
    db: Session = Depends(get_db),
):
    """编辑群组"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权编辑：仅创建人可修改该群组")

    update_data = group_data.model_dump(exclude_unset=True)
    agent_ids = update_data.pop("agent_ids", None)

    if "name" in update_data and not update_data["name"]:
        raise HTTPException(status_code=400, detail="群组名称不能为空")

    for field, value in update_data.items():
        setattr(group, field, value)

    if agent_ids is not None:
        agents = db.query(Agent).filter(
            Agent.id.in_(agent_ids),
            or_(Agent.user_id == user_id, Agent.resource_type == RESOURCE_TYPE_BUILTIN),
        ).all()
        group.agents = agents

    db.commit()
    db.refresh(group)
    return success_response(group)


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, user_id: Annotated[int, Depends(get_current_user_id)], db: Session = Depends(get_db)):
    """删除群组"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    if group.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该群组")

    db.delete(group)
    db.commit()

    return success_response({"deleted": True}, message="删除成功")


@router.get("/groups/{group_id}", response_model=ApiResponse[GroupResponse])
def get_group(
    group_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取群组详情（须登录：仅内置或本人数据）"""
    group = get_group_if_readable(db, group_id, current_user)
    if not group:
        raise HTTPException(status_code=404, detail="群组不存在")
    return success_response(group)
