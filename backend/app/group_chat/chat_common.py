from enum import Enum
from typing import Any, TypedDict
from app.config import settings
from app.models import Agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class SessionType(str, Enum):
    """会话类型"""
    GROUP_CHAT = "group"
    PPT = "ppt"
    CHAT = "chat"


class RoleType(str, Enum):
    """角色类型"""
    USER = "user"
    AGENT_SELECTOR = "agent_selector"
    SPEAKER_SELECTOR = "speaker_selector"
    SPEAKER = "speaker"
    ASSISTANT = "assistant"

class MsgType(str, Enum):
    """消息类型"""
    USER = "user"
    MODEL = "model"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class InnerNode(str, Enum):
    """deep agent 内层节点"""
    MODEL = "model"
    TOOL = "tool"
    
    

class ChatRecord(TypedDict):
    """对话消息"""
    role_type: str
    message_type: str | None
    message_content: str
    speaker_id: int | None
    speaker_name: str | None

    

class SpearkerRecord(TypedDict):
    """发言记录"""
    speaker_id: str = Field(description="发言人ID")
    speaker_name: str = Field(description="发言人名称")
    content: str = Field(description="发言内容")
    timestamp: int = Field(description="发言时间")


class UserProfile(TypedDict):
    """用户基础画像"""
    member_id: int = Field(description="当前用户id")
    org_id: str = Field(description="当前用户所属组织id")
    member_role: str = Field(description="当前用户角色.TEACHER/STUDENT")



class WindowState(TypedDict, total=False):
    """本轮对话窗口状态"""
    user_message: str
    all_agents: list[dict[str, Any]]
    group_members: list[dict[str, Any]]
    select_reason: str # 筛选依据
    transcript: list[SpearkerRecord] #讨论级别，发言人发言记录
    current_turn: int = 0
    max_turns: int
    current_speaker:dict[str, Any]
    speaker_reason: str
    finished: bool = False
    session_messages: list[ChatRecord] #会话级别记录，包括用户消息、筛选可用智能体消息，筛选发言人消息，发言人发言消息，总结消息
    session_id: int
    round_id: int
    user_profile: UserProfile # 用户基础画像
    answer: str # 最终回复
    finish_reason: str # 结束原因


def get_llm() -> ChatOpenAI:
    print(settings)
    return ChatOpenAI(
        model=settings.model_router_name,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        temperature=0.2,
    )

llm: ChatOpenAI = get_llm()


class NoSpeakerError(Exception):
    """无可用发言人异常"""
    def __init__(self, message: str):
        super().__init__(self.message)