import json
from app.group_chat.chat_common import SpearkerRecord, WindowState
from app.group_chat.chat_graph import get_window_graph
from app.models import Agent
from app.session.service import get_or_create_session
from app.utils import snowflake
from fastapi import APIRouter, Depends
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse
from app.database import get_db



router = APIRouter(prefix="/chat_window")

class WindowChatRequest(BaseModel):
    user_message: str
    org_id: int
    member_id: int
    session_id: str | None
    round_id: str | None

    
window_graph: CompiledStateGraph = get_window_graph()

@router.post("/chat")
def window_chat(window_chat_request: WindowChatRequest, db: Session = Depends(get_db)) -> StreamingResponse:

    session_id = window_chat_request.session_id
    if not session_id:
        session_id = str(snowflake.get_snowflake_id())
    get_or_create_session(
        db=db,
        session_id=session_id,
        member_id=window_chat_request.member_id,
        user_message=window_chat_request.user_message,
        session_type="group_chat",
    )


    round_id = snowflake.get_snowflake_id()    

    

    #查询所有可用智能体
    all_agents = db.query(Agent).all()
    all_agents_data = [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "prompt": agent.prompt
        } for agent in all_agents
    ]

    config = {"configurable": {"thread_id": session_id}}
    window_state: WindowState = {"session_id": session_id, 
                  "round_id": round_id, 
                  "user_message": window_chat_request.user_message, 
                  "member_id": window_chat_request.member_id,
                  "all_agents": all_agents_data,
                  "user_profile":{"member_id": window_chat_request.member_id, "org_id": window_chat_request.org_id, "member_role": "STUDENT"}
                  }
    
    return StreamingResponse(event_stream(window_state, config), media_type="text/event-stream")


def event_stream(window_state:dict, config:dict):

    yield send_messages("start",{"session_id": str(window_state.get("session_id")), "round_id": str(window_state.get("round_id"))})

    for chunk in window_graph.stream(
        window_state, config=config, stream_mode=["messages", "updates", "custom"]
    ):
        # 兼容 (mode, data) 与 (namespace, mode, data)
        if isinstance(chunk, tuple) and len(chunk) == 2:
            mode, data = chunk
        elif isinstance(chunk, tuple) and len(chunk) == 3:
            _, mode, data = chunk
        else:
            continue

        if mode == "updates":
            if data.get("select_agents_node"):
                msg = send_selected_agent_node(data.get("select_agents_node"))
                if msg:
                    yield msg
            if data.get("select_speaker_node"):
                msg = send_select_speaker_node(data.get("select_speaker_node"))
                if msg:
                    yield msg
        elif mode == "custom":
            # speak_node 内通过 get_stream_writer 转发的发言流式增量
            yield send_messages(data=data)
        elif mode == "messages":
            # 外层图在 select_* 节点上的 LLM messages（若有）；speak_node 内层流式见 mode == "custom"
            if not isinstance(data, tuple) or len(data) < 2:
                continue
            meta = data[1]
            if not isinstance(meta, dict):
                continue
            langgraph_node = meta.get("langgraph_node", "")
            if langgraph_node in ["select_agents_node", "select_speaker_node"]:
                continue




def send_selected_agent_node(data: dict):
    """发送选择智能体节点的信息"""
    if data.get("finished",False):
        return send_messages("finished",{"answer": data.get("answer", ""),"finish_reason": data.get("finish_reason", "")})
    else:
        return send_messages("create_group",{"group_members":[{"id": agent['id'], "name": agent['name']} for agent in data.get("group_members", [])],"select_reason": data.get("select_reason", "")})


def send_select_speaker_node(data: dict):
    """发送选择发言人节点的信息"""
    if data.get("finished",False):
        return send_messages("finished",{"answer": data.get("answer", ""),"finish_reason": data.get("finish_reason", "")})
    else:
        payload = dict(data)
        payload.pop("session_messages", None)
        return send_messages("select_speaker",payload)


def send_speaker_node(data:dict):
    """发送发言人的信息"""
    transcript: list[SpearkerRecord] = data.get("transcript", [])
    if transcript:
        return send_messages("speaker",transcript[-1])
    



def send_messages(event:str|None=None,data:dict=None) -> str:
    """发送消息"""
    if event:
        data["event"] = event
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n" 