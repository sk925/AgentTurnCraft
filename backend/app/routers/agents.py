from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, get_current_user_id
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.models import Agent, Skill
from app.query_access import get_agent_if_readable, get_skill_if_readable, list_agents
from app.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentWithSkills,
    ApiResponse,
    success_response,
)

router = APIRouter()


@router.get("/agents", response_model=ApiResponse[List[AgentResponse]])
def get_agents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取智能体列表（须登录：内置 + 当前用户自己的）"""
    agents = list_agents(db, current_user)
    return success_response(agents)


@router.post("/agents", response_model=ApiResponse[AgentResponse])
def create_agent(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    agent: AgentCreate,
    db: Session = Depends(get_db),
):
    """添加智能体"""
    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_admin else RESOURCE_TYPE_CUSTOM
    db_agent = Agent(**agent.model_dump(), user_id=current_user.id, resource_type=resource_type)
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return success_response(db_agent)


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, user_id: Annotated[int, Depends(get_current_user_id)], db: Session = Depends(get_db)):
    """删除智能体（仅创建人可删）"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if agent.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该智能体")

    db.delete(agent)
    db.commit()

    return success_response({"deleted": True}, message="删除成功")


@router.put("/agents/{agent_id}", response_model=ApiResponse[AgentResponse])
def update_agent(
    agent_id: int,
    user_id: Annotated[int, Depends(get_current_user_id)],
    agent_data: AgentUpdate,
    db: Session = Depends(get_db),
):
    """编辑智能体"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if agent.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权编辑：仅创建人可修改该智能体")

    update_data = agent_data.model_dump(exclude_unset=True)
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(status_code=400, detail="智能体名称不能为空")

    for field, value in update_data.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return success_response(agent)


@router.post("/agents/{agent_id}/skills/{skill_id}")
def add_skill_to_agent(
    agent_id: int,
    skill_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """关联技能到智能体"""
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    skill = get_skill_if_readable(db, skill_id, current_user)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if skill not in agent.skills:
        agent.skills.append(skill)
        db.commit()

    return success_response({"linked": True}, message="关联成功")


@router.delete("/agents/{agent_id}/skills/{skill_id}")
def remove_skill_from_agent(
    agent_id: int,
    skill_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """解除技能与智能体的关联"""
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.user_id == current_user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    skill = get_skill_if_readable(db, skill_id, current_user)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if skill in agent.skills:
        agent.skills.remove(skill)
        db.commit()

    return success_response({"unlinked": True}, message="解除关联成功")


@router.get("/agents/{agent_id}", response_model=ApiResponse[AgentWithSkills])
def get_agent_with_skills(
    agent_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取智能体及其关联的技能（须登录：仅可访问内置或本人数据）"""
    agent = get_agent_if_readable(db, agent_id, current_user)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return success_response(agent)
