from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.group_chat.chat_graph import get_window_graph
from app.session.schemas import ChatSessionMessageResponse, ChatSessionResponse
from app.session.service import get_session, list_sessions

router = APIRouter(prefix="/sessions")


@router.get("", response_model=list[ChatSessionResponse])
def get_session_list(
    member_id: int = Query(..., description="用户ID"),
    session_type: str | None = Query(None, description="会话类型"),
    db: Session = Depends(get_db),
):
    return list_sessions(db=db, member_id=member_id, session_type=session_type)


@router.get("/{session_id}/messages", response_model=list[ChatSessionMessageResponse])
def get_session_messages(
    session_id: str,
    member_id: int = Query(..., description="用户ID"),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.member_id != member_id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    graph = get_window_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": session_id}})
    values = snapshot.values if snapshot else {}
    session_messages = values.get("session_messages", [])
    return session_messages
