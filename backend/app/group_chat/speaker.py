from codecs import StreamWriter
import json
import re
import threading
from typing import Any
from app.agent_log.service import RoleType, save_model_message
from app.group_chat.chat_common import ChatRecord, InnerNode, NoSpeakerError, SpearkerRecord, UserProfile, WindowState, llm
from app.models import Agent
from app.tools.ask_user import ask_user_question
from langchain.agents.middleware import ModelRequest
from langchain.agents.middleware.types import dynamic_prompt
from langgraph.graph.state import CompiledStateGraph
from deepagents.backends import LocalShellBackend

from deepagents import create_deep_agent
from app.config import _BACKEND_ROOT


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
- 编造未在上下文中出现的事实或经历

## 回复优先级（必须遵守）
1. 优先回答「用户原始问题」。
2. 群聊记录仅用于补充上下文；若与用户原始问题冲突，以用户原始问题为准。
3. 若信息不足，先使用 ask_user_question 向用户提问，不要自拟背景。
4. 输出保持简洁，避免重复历史表述（建议 3-6 句）。

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
    history_messages: list[ChatRecord]


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

    # 近期发言记录
    history_messages: list[ChatRecord] = ctx.get("history_messages", [])
    
    history_messages_text = ""
    if history_messages:
        history_messages_text += f"<history_messages>\n"
    for message in history_messages:
        role_type = message.get('role_type', '')
        if role_type == RoleType.USER.value:
            history_messages_text += f"[USER]\n {message.get('message_content', '')}\n[/USER]\n"
        elif role_type == RoleType.SPEAKER.value:
            if message.get("speaker_id") == ctx.get("speaker_id"):
                history_messages_text += f"[你的发言]\n"
                history_messages_text += f"<<<CONTENT>>>\n{message.get('message_content', '')}\n<<</CONTENT>>>\n"
                history_messages_text += f"[/你的发言]\n"
            else:
                history_messages_text += f"[{message.get('speaker_name', '')}]\n"
                history_messages_text += f"<<<CONTENT>>>\n{message.get('message_content', '')}\n<<</CONTENT>>>\n"
                history_messages_text += f"[/{message.get('speaker_name', '')}]\n"
        
    if history_messages_text:
        history_messages_text += f"</history_messages>\n"
        history_messages_text = history_messages_text.strip()    

    

    member_id = user_profile.get("member_id", "") if user_profile else ""
    output_dir = artifact_dir / f"{member_id}/{ctx.get('session_id', '')}/{ctx.get('rount_id', '')}"

    wrap_prompt_text = WRAP_PROMPT.format(user_message=ctx.get("user_message", ""), 
                                          transcript=history_messages_text, 
                                          user_profile=user_profile_text, 
                                          output_dir=output_dir.resolve().as_posix())

    print(f"wrap_prompt_text={wrap_prompt_text}")
    final_prompt = base_prompt + "\n" + wrap_prompt_text

    return final_prompt




# speak_agent_local = threading.local()

speaker_agent_map:dict[tuple[int, int], CompiledStateGraph] = {} # (speaker_id, checkpointer_id) 到图的映射
_speaker_agent_lock = threading.RLock()


def make_project_backend(_runtime: Any) -> LocalShellBackend:
    return LocalShellBackend(
        root_dir=_BACKEND_ROOT,
        virtual_mode=False,
        inherit_env=True,
    )

def speak_agent(window_state: WindowState, checkpointer: Any) -> CompiledStateGraph:
    """创建发言人智能体"""
    current_speaker = window_state.get("current_speaker", {})

    group_members = window_state.get("group_members", [])

    current_agent_info: Agent | None = next((member for member in group_members if member['id'] == current_speaker.get("id", "")), None)

    if current_agent_info is None:
        raise NoSpeakerError(f"发言人{current_speaker.get('id', '')}:{current_speaker.get('name', '')}不存在于群聊成员列表")

    cache_key = (current_agent_info['id'], id(checkpointer))
    compiled_graph = speaker_agent_map.get(cache_key)
    if compiled_graph is not None:
        return compiled_graph
        

    with _speaker_agent_lock:
        # 双重检查，避免其他线程已创建
        compiled_graph = speaker_agent_map.get(cache_key)
        if compiled_graph is None:
            compiled_graph = create_deep_agent(model=llm, 
                                           system_prompt=current_agent_info['prompt'], 
                                           tools=[ask_user_question],
                                           skills=[],
                                           middleware=[format_wrap_prompt],
                                           context_schema=SpeakContext,
                                           checkpointer=checkpointer,
                                           backend=make_project_backend)  
            speaker_agent_map[cache_key] = compiled_graph
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

async def stream_updates(data: Any, parent_stream_writer: StreamWriter, current_speaker: dict[str, Any],window_state: WindowState):
    """处理发言人发言的流式增量"""
    if "model" in data:
        final_msg = data["model"]["messages"]
        ai_msg = final_msg[0]
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
                    await save_model_message(window_state['user_profile']['member_id'], window_state['session_id'], window_state['round_id'], "interactive", current_speaker, json.dumps(tool_call["args"], ensure_ascii=False))
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
            await save_model_message(window_state['user_profile']['member_id'], window_state['session_id'], window_state['round_id'], "tool_call", current_speaker, ai_msg)
        else:
            print("--------------------------------")
            print(f"model={ai_msg}")
            print("--------------------------------")
            await save_model_message(window_state['user_profile']['member_id'], window_state['session_id'], window_state['round_id'], "model", current_speaker, ai_msg)  
    elif "tool" in data:

        tool_msg_list = data["tools"]["messages"]
        for tool_msg in tool_msg_list:
            if tool_msg.name == "write_todos":   
                await save_model_message(window_state['user_profile']['member_id'], window_state['session_id'], window_state['round_id'], "todo_list", current_speaker, tool_msg)         
                continue
            if tool_msg.name == "ask_user_question":
                continue
            # todo 统计token使用量
            await save_model_message(window_state['user_profile']['member_id'], window_state['session_id'], window_state['round_id'], "tool_out", current_speaker, tool_msg)
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
