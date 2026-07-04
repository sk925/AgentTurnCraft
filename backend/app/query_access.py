"""资源可见性：内置对任意登录用户；自定义仅创建者。

`/api/skills`、`/api/agents`、`/api/groups` 的列表与详情已依赖 `get_current_user`，未登录不会进入本层逻辑；
`user is None` 分支仍保留，供内部或其它调用方复用。
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.constants import RESOURCE_TYPE_BUILTIN
from app.chat.base.models import Agent, Group, Skill
from app.knowledge.models import KnowledgeBase


def _skills_readable_query(session: Session, user: CurrentUser | None):
    q = session.query(Skill)
    if user is None:
        return q.filter(Skill.resource_type == RESOURCE_TYPE_BUILTIN)
    return q.filter(or_(Skill.user_id == user.id, Skill.resource_type == RESOURCE_TYPE_BUILTIN))


def list_skills(session: Session, user: CurrentUser | None) -> list[Skill]:
    return _skills_readable_query(session, user).order_by(Skill.create_time.desc()).all()


def list_skills_page(
    session: Session,
    user: CurrentUser | None,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    resource_type: int | None = None,
) -> tuple[list[Skill], int]:
    query = _skills_readable_query(session, user)

    keyword = (q or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Skill.name.ilike(pattern),
                Skill.description.ilike(pattern),
                Skill.skill_desc.ilike(pattern),
            )
        )

    if resource_type is not None:
        query = query.filter(Skill.resource_type == resource_type)

    total = query.count()
    items = (
        query.order_by(Skill.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


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


def list_knowledge_bases(session: Session, user: CurrentUser | None) -> list[KnowledgeBase]:
    return _knowledge_bases_readable_query(session, user).order_by(KnowledgeBase.create_time.desc()).all()


def list_knowledge_bases_page(
    session: Session,
    user: CurrentUser | None,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    resource_type: int | None = None,
) -> tuple[list[KnowledgeBase], int]:
    query = _knowledge_bases_readable_query(session, user)

    keyword = (q or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                KnowledgeBase.name.ilike(pattern),
                KnowledgeBase.description.ilike(pattern),
            )
        )

    if resource_type is not None:
        query = query.filter(KnowledgeBase.resource_type == resource_type)

    total = query.count()
    items = (
        query.order_by(KnowledgeBase.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def _knowledge_bases_readable_query(session: Session, user: CurrentUser | None):
    q = session.query(KnowledgeBase)
    if user is None:
        return q.filter(KnowledgeBase.resource_type == RESOURCE_TYPE_BUILTIN)
    return q.filter(
        or_(KnowledgeBase.user_id == user.id, KnowledgeBase.resource_type == RESOURCE_TYPE_BUILTIN)
    )


def get_knowledge_base_if_readable(
    session: Session,
    knowledge_base_id: int,
    user: CurrentUser | None,
) -> KnowledgeBase | None:
    row = session.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()
    if row is None:
        return None
    if row.resource_type == RESOURCE_TYPE_BUILTIN:
        return row
    if user is not None and row.user_id == user.id:
        return row
    return None
