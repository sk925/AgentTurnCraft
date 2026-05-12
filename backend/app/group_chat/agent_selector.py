from app.group_chat.chat_common import MsgType, RoleType, WindowState, save_token_usage
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from app.group_chat.chat_common import llm

"""
超级助手：
1. 根据用户意图从候选池中挑选进入群组的智能体。
2. 简单问题直接回复
"""

SELECTOR_PROMPT = """
## 核心定位
你是超级助手。
负责解析用户提问、历史上下文，完成两大核心决策：智能体准入筛选 / 通用对话直接应答，精准分流业务，控制群聊参与范围，避免无关智能体无效响应。
## 连续对话优先规则（高优先级）
- 若近期对话显示：上一条有效发言来自某个 STAFF，且其内容对用户提出了问题/确认，则用户当前消息默认视为对该 STAFF 的续答；
- 命中续答场景时，应优先让该 STAFF 继续对话，将其纳入 selected_agent_ids（通常仅该 STAFF 即可）；
- 即使用户回复很短（如“是/不是/我过得不好/你好大橘”），只要与上一条 STAFF 发言有承接关系，也不得转为超级助手直接接管；
- 仅当用户明确切换话题、明确要求超级助手回复、或与上一条 STAFF 发言无关时，才可进入“通用对话判定”。
## 能力规则
1.智能体筛选判定
- 解析当前用户问题语义、需求领域、任务类型；
- 匹配系统预设所有智能体的人设、能力范围、专业领域、职能标签；
- 仅筛选强相关、可解决当前问题的智能体加入群聊，禁止无关智能体入群；
- 多领域复合需求：同步拉入对应多领域智能体，明确分工适配；
- 特殊限制：高敏感、专属垂直需求，仅准入指定专属智能体。
- 用户指定人选（优先于自动筛选）：当用户明确点名、@、指定角色/称呼，或要求「只要某几位 / 别让其他人参与」等时，在「你的员工」候选中按 member_name、member_description 可辨识的指代匹配 member_code，将用户指定且存在于候选中的智能体全部纳入 selected_agent_ids；不得以「最小必要」或主观相关性为由删减用户已点名的在册成员。若指代无法唯一对应或所点人员不在候选列表，不得在 selected_agent_ids 中编造 ID，应在 answer 中礼貌说明并列出可选成员供用户确认。
2.通用对话判定 & 自主回复
- 识别无专业门槛、无需垂直智能体协作的纯闲聊类内容：日常寒暄、情绪倾诉、简单碎碎念、无指向闲聊、基础常识闲聊；
- 此类场景不拉起任何智能体，由你直接独立回复用户，语气自然贴合对话语境；
- 边界区分：简单知识问答、趣味互动算通用对话；专业咨询、任务协作、复杂问题 禁止自主回复，必须分配智能体。
- 若命中“连续对话优先规则”，禁止按通用对话处理。
## 禁止规则
- 禁止过度拉入智能体，遵循「最小必要原则」；
- 禁止复杂业务问题直接自主回复，严禁越权解答专业领域问题；
- 禁止遗漏复合需求下的关键职能智能体；
- 禁止在用户已明确指定在册人选时，擅自改选他人或漏选用户点名的成员；
- 禁止忽略近期对话中的问答承接关系（STAFF 问 -> 用户答）；
- 输出严格 JSON 格式，无额外多余文案、无 markdown、无解释性废话。
- 禁止猜测用户意图
- 禁止编造员工ID

## 你的员工
{agent_members}

## 会话级对话摘要(没有请忽略)
{session_summary}

## 近期对话记录
{recent_messages}
"""

class GroupSelection(BaseModel):
    """选择员工：根据用户意图从候选池中挑选进入群组的智能体。"""
    selected_agent_ids: list[int]|None = Field(description="应拉入群聊员工列表，不需要时可不选，只能从候选列表中选，不能选重复的员工；用户明确指定人选时须包含其点名的在册成员。")
    reason: str = Field(description="简要说明筛选依据")
    answer: str = Field(description="回复或者追问。不需要员工时，你给出的回复")


def select_agent(window_state: WindowState) -> GroupSelection:
    """根据用户意图筛选可用的智能体"""
    structured = llm.with_structured_output(GroupSelection, include_raw=True)
    #structured = llm.with_structured_output(GroupSelection)
    # 可用成员列表
    agent_members_text = ""
    for agent in window_state.get("all_agents", []):
        agent_members_text += f"- member_code: {agent['id']}, member_name: {agent['name']}, member_description: {agent['description']}\n"

    session_messages = window_state.get("session_messages", [])
  
    # 近期对话记录
    history_messages = [
        x for x in session_messages
        if x['role_type'] in [RoleType.USER, RoleType.SPEAKER, RoleType.ASSISTANT]
    ][-8:]
  
    history_messages_text = ""
    if history_messages:
        history_messages_text += f"<history_messages>\n"
    for message in history_messages:
        role_type = message.get('role_type', '')
        if role_type == RoleType.USER.value:
            history_messages_text += f"[USER]\n {message.get('message_content', '')}\n[/USER]\n"
        elif role_type == RoleType.SPEAKER.value:
            history_messages_text += f"[STAFF-{message.get('speaker_name', '')}]\n"
            history_messages_text += f"<<<CONTENT>>>\n{message.get('message_content', '')}\n<<</CONTENT>>>\n"
            history_messages_text += f"[/STAFF-{message.get('speaker_name', '')}]\n"
        elif role_type == RoleType.ASSISTANT.value:
            history_messages_text += f"[ASSISTANT]\n<<<CONTENT>>>\n{message.get('message_content', '')}\n<<</CONTENT>>>\n[/ASSISTANT]\n"
    if history_messages_text:
        history_messages_text += f"</history_messages>\n"
        history_messages_text = history_messages_text.strip()
    prompt = SELECTOR_PROMPT.format(agent_members=agent_members_text, session_summary='', recent_messages=history_messages_text)

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=window_state.get("user_message", "")),
    ]
    result = structured.invoke(messages,config={"response_format": GroupSelection})

    raw_data = result.get("raw", None)
    # 保存token使用量
    if raw_data:
        save_token_usage(raw_data, window_state)
    decision = result.get("parsed", None)
    return decision

