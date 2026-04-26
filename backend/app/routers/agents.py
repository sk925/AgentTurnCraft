from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Agent, Skill
from app.schemas import AgentResponse, AgentCreate, AgentUpdate, AgentWithSkills, SkillResponse

router = APIRouter()


@router.get("/agents", response_model=List[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    """获取智能体列表"""
    agents = db.query(Agent).all()
    return agents


@router.post("/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    """添加智能体"""
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """删除智能体"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    db.delete(agent)
    db.commit()

    return {"message": "删除成功"}


@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: int, agent_data: AgentUpdate, db: Session = Depends(get_db)):
    """编辑智能体"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    update_data = agent_data.model_dump(exclude_unset=True)
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(status_code=400, detail="智能体名称不能为空")

    for field, value in update_data.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return agent


@router.post("/agents/{agent_id}/skills/{skill_id}")
def add_skill_to_agent(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """关联技能到智能体"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if skill not in agent.skills:
        agent.skills.append(skill)
        db.commit()

    return {"message": "关联成功"}


@router.delete("/agents/{agent_id}/skills/{skill_id}")
def remove_skill_from_agent(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    """解除技能与智能体的关联"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if skill in agent.skills:
        agent.skills.remove(skill)
        db.commit()

    return {"message": "解除关联成功"}


@router.get("/agents/{agent_id}", response_model=AgentWithSkills)
def get_agent_with_skills(agent_id: int, db: Session = Depends(get_db)):
    """获取智能体及其关联的技能"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return agent
