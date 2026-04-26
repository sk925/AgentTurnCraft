from app.group_chat.chat_common import MsgType, RoleType, WindowState, llm
from langchain_core.messages import ChatMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field


SYSTEM_PROMPT = """
## 你的角色
你是多智能体群聊的主持人（speaker selector）。
你的唯一任务：在候选成员中选择“下一位发言人”，或结束本轮讨论。

## 选择规则（按顺序执行）
1) 合法性检查  
   - `next_speaker_id` 必须来自候选列表；结束时只能为 `-1`。  
   - `next_speaker_name` 必须与 id 对应；结束时必须为 `""`。
2) 连贯性与去重  
   - 默认避免同一成员连续发言。  
   - 仅当该成员能提供“明显新增信息”时允许连发。
3) 结束判定（满足任一条件则 `decision="end"`）  
   - 覆盖度：用户问题核心点已覆盖，且无关键未决问题。  
   - 增益：最近 2 次发言没有实质新增（主要是复述/改写）。  
4) 若不结束  
   - 选择“最能补齐当前缺口”的成员，而不是重复已有观点的成员。
## 关键定义
- “实质新增”= 新事实 / 新推理 / 新可执行建议 / 明确纠错。
- “关键未决问题”= 影响回答正确性或可执行性的缺口。

## 可选发言人列表
{agent_members}

## 会话级摘要(没有请忽略)
{session_summary}

## 发言记录
{transcript}

## 当前轮次
{turn}

## 上一轮发言人(第一轮时没有)
{previous_speaker}

## 用户原始问题
{user_message}
"""


class SpeakerSelection(BaseModel):
    """总控：结合用户意图与当前发言记录，决定下一位发言人或结束"""

    next_speaker_id: int = Field(
        ...,
        description=(
            '下一位发言人 id；若讨论可结束则填 -1。'
        ),
    )
    next_speaker_name: str = Field(
        ...,
        description="下一位发言人名称；若讨论可结束则填空字符串",
    )
    reason: str = Field(
        default="",
        description="简要说明为何选该发言人或结束。",
    )

def select_speaker(window_state: WindowState,current_turn:int) -> SpeakerSelection:
    """根据用户意图与当前发言记录，决定下一位发言人或结束"""
    group_members = window_state.get("group_members", [])
    
    # 可用发言人列表
    group_members_text = ""
    for member in group_members:
        group_members_text += f"- {member['id']} | {member['name']} | {member['description']}\n"
    group_members_text = group_members_text.strip()
    
    # 会话级摘要,暂时不填充 todo
    


    # 近两轮发言记录
    transcript = window_state.get("transcript", [])
    transcript_text = ""
    for index, message in enumerate(transcript):
        transcript_text += f"[MSG]\n turn={index}\n speaker_id={message['speaker_id']}\n speaker_name={message['speaker_name']}\n"
        transcript_text += f"content:\n <<<CONTENT>>>\n{message['content']}\n <<</CONTENT>>>\n"
        transcript_text += '[/MSG]\n'
    if transcript_text:
        transcript_text = f"<transcript>\n{transcript_text}\n</transcript>"
    
    
    # 上一轮发言人
    previous_speaker_ = window_state.get("current_speaker", None)
    if previous_speaker_:
        previous_speaker_text = f"- {previous_speaker_.get("id", "")}: {previous_speaker_.get("name", "")}\n"
    else:
        previous_speaker_text = ""

    # 调用模型筛选
    structured = llm.with_structured_output(SpeakerSelection)
    current_system_prompt = SYSTEM_PROMPT.format(agent_members=group_members_text, session_summary='', transcript=transcript_text, turn=current_turn, previous_speaker=previous_speaker_text, user_message=window_state.get("user_message", ""))
    messages = [
        SystemMessage(content=current_system_prompt),
        HumanMessage(content="挑选本轮发言人"),
    ]
    decision = structured.invoke(messages)
    return decision
