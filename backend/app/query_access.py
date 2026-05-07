"""可选登录下的资源可见性：内置(type=1)对所有人；自定义仅创建者（需登录且匹配 user_id）。"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.constants import RESOURCE_TYPE_BUILTIN
from app.models import Agent, Group, Skill


def list_skills(session: Session, user: CurrentUser | None) -> list[Skill]:
    q = session.query(Skill)
    if user is None:
        return q.filter(Skill.resource_type == RESOURCE_TYPE_BUILTIN).all()
    return q.filter(
        or_(Skill.user_id == user.id, Skill.resource_type == RESOURCE_TYPE_BUILTIN)
    ).all()


def get_skill_if_readable(session: Session, skill_id: int, user: CurrentUser | None) -> Skill | None:
    s = session.query(Skill).filter(Skill.id == skill_id).first()
    if s is None:
        return None
    if s.resource_type == RESOURCE_TYPE_BUILTIN:
        return s
    if user is not None and s.user_id == user.id:
        return s
    return None


def list_agents(session: Session, user: CurrentUser | None) -> list[Agent]:
    q = session.query(Agent)
    if user is None:
        return q.filter(Agent.resource_type == RESOURCE_TYPE_BUILTIN).all()
    return q.filter(
        or_(Agent.user_id == user.id, Agent.resource_type == RESOURCE_TYPE_BUILTIN)
    ).all()


def get_agent_if_readable(session: Session, agent_id: int, user: CurrentUser | None) -> Agent | None:
    a = session.query(Agent).filter(Agent.id == agent_id).first()
    if a is None:
        return None
    if a.resource_type == RESOURCE_TYPE_BUILTIN:
        return a
    if user is not None and a.user_id == user.id:
        return a
    return None


def list_groups(session: Session, user: CurrentUser | None) -> list[Group]:
    q = session.query(Group)
    if user is None:
        return q.filter(Group.resource_type == RESOURCE_TYPE_BUILTIN).all()
    return q.filter(
        or_(Group.user_id == user.id, Group.resource_type == RESOURCE_TYPE_BUILTIN)
    ).all()


def get_group_if_readable(session: Session, group_id: int, user: CurrentUser | None) -> Group | None:
    g = session.query(Group).filter(Group.id == group_id).first()
    if g is None:
        return None
    if g.resource_type == RESOURCE_TYPE_BUILTIN:
        return g
    if user is not None and g.user_id == user.id:
        return g
    return None
