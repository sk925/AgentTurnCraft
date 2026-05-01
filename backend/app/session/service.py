from sqlalchemy.orm import Session

from app.group_chat.chat_common import SessionType
from app.session.models import ChatSession


def build_session_title(user_message: str) -> str:
    compact = " ".join((user_message or "").strip().split())
    if not compact:
        return "新会话"
    return compact[:24]


def get_session(db: Session, session_id: str) -> ChatSession | None:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_or_create_session(
    db: Session,
    session_id: str,
    member_id: int,
    user_message: str,
    session_type: str = SessionType.CHAT.value,
) -> ChatSession:
    existing = get_session(db, session_id)
    if existing:
        return existing

    session = ChatSession(
        id=session_id,
        title=build_session_title(user_message),
        member_id=member_id,
        session_type=session_type,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, member_id: int, session_type: str | None = None) -> list[ChatSession]:
    query = db.query(ChatSession).filter(ChatSession.member_id == member_id)
    if session_type:
        normalized = session_type
        if session_type == SessionType.GROUP_CHAT.value:
            # 兼容历史写入值 group_chat
            query = query.filter(ChatSession.session_type.in_([SessionType.GROUP_CHAT.value, "group_chat"]))
            return query.order_by(ChatSession.create_at.desc()).all()
        query = query.filter(ChatSession.session_type == normalized)
    return query.order_by(ChatSession.create_at.desc()).all()
