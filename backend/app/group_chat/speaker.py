from codecs import StreamWriter
import re
import threading
from typing import Any
from app.group_chat.chat_common import InnerNode, NoSpeakerError, SpearkerRecord, UserProfile, WindowState, llm
from app.models import Agent
from app.tools.ask_user import ask_user_question
from langchain.agents.middleware import ModelRequest
from langchain.agents.middleware.types import dynamic_prompt
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from deepagents.backends import LocalShellBackend

from deepagents import create_deep_agent
from app.config import _BACKEND_ROOT, checkpointer


WRAP_PROMPT = """
## 环境介绍
你现在群聊中的一员，请根据用户意图与群聊记录发言或执行任务。

## 询问规则
下列情况时必须 ask_user_question工具：
- 需要用户审核
- 用户意图不明确，需要向用户收集信息
- 询问用户问题
## 禁止
- 扩展不存在的事件

## 用户原始问题
{user_message}

## 群聊记录
{transcript}

## 用户画像
{user_profile}

## 文件产出目录(需要生成文件时，请将文件产出到该目录下.规则：workspace/member_id/session_id/round_id)
{output_dir}
"""
class SpeakContext:
    session_id: int
    rount_id: int
    user_profile: UserProfile
    transcript: list[SpearkerRecord] | None
    user_message: str
    speaker_id: int


artifact_dir = _BACKEND_ROOT / "workspace" # 产物目录

@dynamic_prompt
def format_wrap_prompt(request: ModelRequest[SpeakContext]) -> str:
    """动态更改提示词"""
    base_prompt = request.system_prompt

    ctx = request.runtime.context
    # 用户画像信息
    user_profile: UserProfile = ctx.get("user_profile", None)
    user_profile_text = ""
    if user_profile:
        user_profile_text = (
            f"-member_id:{user_profile.get('member_id')}\n"
            f"-org_id:{user_profile.get('org_id')}\n"
            f"-member_role:{user_profile.get('member_role')}"
        )

    # 本次讨论发言记录   
    # 近两轮发言记录
    transcript = ctx.get("transcript", [])
    transcript_parts: list[str] = []
    for index, message in enumerate(transcript):
        transcript_parts.append(f"[MSG]\n turn={index + 1}\n")
        if message.get("speaker_id") == ctx.get("speaker_id"):
            transcript_parts.append(
                f" 你的发言: \n<<<CONTENT>>>\n{message.get('content', '')}\n<<</CONTENT>>>\n"
            )
        else:
            transcript_parts.append(f" speaker_name={message.get('speaker_name', '')}\n")
            transcript_parts.append(
                f" content:\n<<<CONTENT>>>\n{message.get('content', '')}\n<<</CONTENT>>>\n"
            )
        transcript_parts.append("[/MSG]\n")
    transcript_text = "".join(transcript_parts)

    if transcript_text:
        transcript_text = f"<transcript>\n{transcript_text}\n</transcript>" 

    member_id = user_profile.get("member_id", "") if user_profile else ""
    output_dir = artifact_dir / f"{member_id}/{ctx.get('session_id', '')}/{ctx.get('rount_id', '')}"

    wrap_prompt_text = WRAP_PROMPT.format(user_message=ctx.get("user_message", ""), 
                                          transcript=transcript_text, 
                                          user_profile=user_profile_text, 
                                          output_dir=output_dir.resolve().as_posix())

    print("--------------------------------")
    print(f"wrap_prompt_text={wrap_prompt_text}")
    print("--------------------------------")

    final_prompt = base_prompt + "\n" + wrap_prompt_text

    return final_prompt




# speak_agent_local = threading.local()

speaker_agent_map:dict[int, CompiledStateGraph] = {} #发言人id到create_deep_agent的映射
_speaker_agent_lock = threading.RLock()


def make_project_backend(_runtime: Any) -> LocalShellBackend:
    return LocalShellBackend(
        root_dir=_BACKEND_ROOT,
        virtual_mode=False,
        inherit_env=True,
    )

def speak_agent(window_state: WindowState) -> CompiledStateGraph:
    """创建发言人智能体"""
    current_speaker = window_state.get("current_speaker", {})

    group_members = window_state.get("group_members", [])

    current_agent_info: Agent | None = next((member for member in group_members if member['id'] == current_speaker.get("id", "")), None)

    if current_agent_info is None:
        raise NoSpeakerError(f"发言人{current_speaker.get('id', '')}:{current_speaker.get('name', '')}不存在于群聊成员列表")

    compiled_graph = speaker_agent_map.get(current_agent_info['id'])
    if compiled_graph is not None:
        return compiled_graph
        

    with _speaker_agent_lock:
        # 双重检查，避免其他线程已创建
        compiled_graph = speaker_agent_map.get(current_agent_info['id'])
        if compiled_graph is None:
            compiled_graph = create_deep_agent(model=llm, 
                                           system_prompt=current_agent_info['prompt'], 
                                           tools=[ask_user_question],
                                           skills=[],
                                           middleware=[format_wrap_prompt],
                                           context_schema=SpeakContext,
                                           checkpointer=checkpointer,
                                           backend=make_project_backend)  
            speaker_agent_map[current_agent_info['id']] = compiled_graph
        return compiled_graph



def stream_messages(data: Any, parent_stream_writer: StreamWriter, current_speaker: dict[str, Any]):
    """处理发言人发言的流式增量"""
    if isinstance(data, tuple) and len(data) >= 2:
        message, meta = data[0], data[1]
        delta = _message_chunk_text(message)
        if delta:
            inner_node = meta.get("langgraph_node", "") if isinstance(meta, dict) else ""
            # 如果是通用输出
            if inner_node == InnerNode.MODEL.value:
                parent_stream_writer(
                {
                    "event": "speaker_model_stream",
                    "speaker_id": current_speaker.get("id"),
                    "speaker_name": current_speaker.get("name"),
                    "delta": delta,
                    "inner_node": inner_node,
                })
            elif inner_node == InnerNode.TOOL.value:
                print(f"tool_output={message}")

def stream_updates(data: Any, parent_stream_writer: StreamWriter, current_speaker: dict[str, Any]):
    """处理发言人发言的流式增量"""
    if "model" in data:
        final_msg = data["model"]["messages"]
        ai_msg = final_msg[0]
        if ai_msg.tool_calls:
            if ai_msg.tool_calls:
                tool_calls: list[dict] = []
                for tool_call in ai_msg.tool_calls:
                    if tool_call["name"] == "write_todos":
                        continue
                    if tool_call["name"] == "ask_user_question":
                        parent_stream_writer(
                            {
                                "event": "speaker_interrupt",
                                "args": tool_call["args"],
                                "tool_id": tool_call.get("id") or "",
                            }
                        )
                        continue

                    tool_calls.append(
                        {
                            "tool_name": tool_call["name"],
                            "tool_args": tool_call["args"],
                            "tool_id": tool_call["id"],
                        }
                    )  
                if len(tool_calls) > 0:
                    parent_stream_writer(
                        {
                            "event": "speaker_tool_call",
                            "tool_calls": tool_calls,
                        }
                    )  
    elif "tool" in data:
        print("--------------------------------")
        print(f"tool={data['tool']}")
        print("--------------------------------")
        tool_msg_list = data["tools"]["messages"]
        for tool_msg in tool_msg_list:
            if tool_msg.name == "write_todos":            
                continue
            if tool_msg.name == "ask_user_question":
                continue
            # todo 统计token使用量
            parent_stream_writer(
                {
                    "event": "speaker_tool_out",
                    "tool_name": tool_msg.name,
                    "content": tool_msg.content,
                    "tool_id": tool_msg.tool_call_id,
                }              
            )
        # TodoListMiddleware 的 write_todos 会把 todos 写入状态；不同运行时下
        # todos 可能出现在 tools 更新里或单独的 updates 字段里。这里做兼容且避免 KeyError。
        todos = None
        if isinstance(data.get("tools"), dict):
            todos = data["tools"].get("todos")
        if todos:
            parent_stream_writer({
                "event": "speaker_todo_list",
                "todos": todos,
            })
    elif "todos" in data and data.get("todos"):
        parent_stream_writer({
            "event": "speaker_todo_list",
            "todos": data["todos"],
        })



def _message_chunk_text(message: object) -> str:
    """从 LangChain 消息 / 分片中取出可下发的文本增量。"""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    if content is not None:
        return str(content)
    return ""                
