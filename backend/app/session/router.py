import json
from app.group_chat.chat_common import RoleType, SessionType
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.group_chat.chat_graph import get_window_graph
from app.schemas import ApiResponse, success_response
from app.session.schemas import ChatSessionMessageResponse, ChatSessionResponse
from app.session.service import get_session, list_sessions

router = APIRouter(prefix="/sessions")


@router.get("", response_model=ApiResponse[list[ChatSessionResponse]])
def get_session_list(
    member_id: int = Query(..., description="用户ID"),
    session_type: SessionType | None = Query(None, description="会话类型"),
    db: Session = Depends(get_db),
):
    sessions = list_sessions(
        db=db,
        member_id=member_id,
        session_type=session_type.value if session_type else None,
    )
    return success_response(sessions)


@router.get("/{session_id}/messages", response_model=ApiResponse[list[ChatSessionMessageResponse]])
async def get_session_messages(
    session_id: str,
    request: Request,
    member_id: int = Query(..., description="用户ID"),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.member_id != member_id:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    graph = get_window_graph(request.app.state.checkpointer)
    snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
    values = snapshot.values if snapshot else {}
    session_messages = values.get("session_messages", [])
    # 改动每条记录的 message_content 值
    filtered_messages = []
    for message in session_messages:
        if message['role_type'] == RoleType.AGENT_SELECTOR:
            continue
            # agent_selection = json.loads(message['message_content'])
            # if not agent_selection.get("selected_agent_ids"):
            #     message['message_content'] = agent_selection.get("answer", "")
            #     message['role_type'] = RoleType.ASSISTANT
            #     filtered_messages.append(message)
        else:
            filtered_messages.append(message)    
            
    return success_response(filtered_messages)    
