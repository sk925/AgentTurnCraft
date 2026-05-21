from enum import Enum
from typing import Any, TypedDict
from app.chat.base.models.agent_log import AgentLog, AgentLogService
from app.config import settings
from app.chat.base.models import Agent
from langchain_core.callbacks import usage
from langchain_core.messages import AIMessage
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
    TOOL_OUT = "tool_out"
    INTERACTIVE = "interactive"
    TODO_LIST = "todo_list"


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
    """本轮用户原始文案（与请求一致；发言人侧可另拼 attachment_context）。"""
    file_ids: list[int]
    """本轮用户上传的文件 id，仅用于状态传递与工具。"""
    attachment_context: str
    """本轮附件元数据说明，仅注入发言人上下文。"""
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
    single_agent_id: int # 单个智能体id
    interrupt_data: dict[str, Any] # 打断数据


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_router_name,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        temperature=0.2,
        stream_usage=True
    )


class NoSpeakerError(Exception):
    """无可用发言人异常"""
    def __init__(self, message: str):
        super().__init__(self.message)


def save_token_usage(
    ai_message: AIMessage,
    window_state: WindowState,
    *,
    role_type: str = RoleType.AGENT_SELECTOR.value,
):
    """保存 token 用量（结构化输出调用返回的 raw AIMessage）"""

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    model_name = ""

    usage_metadata = ai_message.usage_metadata
    if usage_metadata:
        input_tokens = usage_metadata.get("input_tokens", 0)
        output_tokens = usage_metadata.get("output_tokens", 0)
        total_tokens = usage_metadata.get("total_tokens", 0)

    response_metadata = ai_message.response_metadata
    if response_metadata:
        token_usage = response_metadata.get("token_usage", {})
        model_name = response_metadata.get("model_name", "")

    row = AgentLog(
        user_id=window_state["user_profile"]["member_id"],
        session_id=window_state["session_id"],
        round_id=window_state["round_id"],
        content=ai_message.content,
        role_type=role_type,
        message_type=MsgType.MODEL.value,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_name=model_name,
    )    
    AgentLogService.save_agent_log(row)

        