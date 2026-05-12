import time
from app.group_chat.agent_selector import GroupSelection, select_agent
from app.group_chat.chat_common import ChatRecord, MsgType, RoleType, WindowState
from app.group_chat.event_publisher import EventPublisher
from app.group_chat.speaker import speak_agent, stream_messages, stream_updates
from app.group_chat.speaker_selector import SpeakerSelection, select_speaker
from langgraph.constants import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.types import Command




def build_graph(checkpointer) -> CompiledStateGraph:
    """创建群聊工作流"""

    def select_agents_node(window_state: WindowState):
        """筛选可用员工"""
        group_selection: GroupSelection = select_agent(window_state)

        
        # 会话级别记录，包括用户消息、筛选可用智能体消息，筛选发言人消息，发言人发言消息，总结消息
        chat_messages: list[ChatRecord] = window_state.get("session_messages", [])
        # 用户本次提问
        chat_messages.append(
            ChatRecord(
                role_type=RoleType.USER.value,
                message_type=MsgType.USER.value,
                message_content=window_state.get("user_message", ""),
                speaker_id=None,
                speaker_name=None,
            )
        )
        # 追加筛选可用智能体消息
        chat_messages.append(
            ChatRecord(
                role_type=RoleType.AGENT_SELECTOR.value,
                message_type=MsgType.MODEL.value,
                message_content=group_selection.model_dump_json(ensure_ascii=False),
                speaker_id=None,
                speaker_name=None,
            )
        )


        selected_agent_ids = group_selection.selected_agent_ids
        if not selected_agent_ids:
            chat_messages.append(
                ChatRecord(
                    role_type=RoleType.ASSISTANT.value,
                    message_type=MsgType.MODEL.value,
                    message_content=group_selection.answer,
                    speaker_id=None,
                    speaker_name=None,
                )
            )
            return Command(
                goto=END, update={"answer": group_selection.answer, "finished": True, "session_messages": chat_messages,"finish_reason": group_selection.reason}
            )

        agent_list = window_state.get("all_agents", [])
        # 筛选出需要的员工，创建群组
        group_members = [
            agent for agent in agent_list if agent['id'] in selected_agent_ids
        ]

        # 如果只需要一个员工，直接进入speak_node
        if len(selected_agent_ids) == 1:
            current_speaker = {
                "id": selected_agent_ids[0],
                "name": group_members[0].get("name", ""),
            }
            return Command(
                goto="speak_node",
                update={
                    "current_speaker": current_speaker,
                    "group_members": group_members,
                    "select_reason": group_selection.reason,
                    "session_messages": chat_messages,
                },
            )

        return Command(
            goto="select_speaker_node",
            update={
                "group_members": group_members,
                "select_reason": group_selection.reason,
                "session_messages": chat_messages,
            },
        )

    def select_speaker_node(window_state: WindowState):
        """筛选发言人"""
        current_turn = window_state.get("current_turn", 0) + 1
        speaker_selection: SpeakerSelection = select_speaker(window_state, current_turn)

        chat_messages: list[ChatRecord] = window_state.get("session_messages", [])
        chat_messages.append(
            ChatRecord(
                role_type=RoleType.SPEAKER_SELECTOR.value,
                message_type=MsgType.MODEL.value,
                message_content=speaker_selection.model_dump_json(ensure_ascii=False),
                speaker_id=None,
                speaker_name=None,
            )
        )

        next_speaker_id = speaker_selection.next_speaker_id
        if next_speaker_id == -1:
            return Command(
                goto=END, update={"finished": True, "answer": "处理完成", "session_messages": chat_messages, "finish_reason": speaker_selection.reason}
            )  # 讨论结束，让总结节点生成回复

        # 筛选出发言人 todo
        current_speaker = {
            "id": next_speaker_id,
            "name": speaker_selection.next_speaker_name,
        }

        return Command(
            goto="speak_node",
            update={
                "current_speaker": current_speaker,
                "current_turn": current_turn,
                "speaker_reason": speaker_selection.reason,
                "session_messages": chat_messages,
            },
        )

    async def speak_node(window_state: WindowState):
        """发言人发言"""
        current_speaker = window_state.get("current_speaker", {})
        session_id = str(window_state.get("session_id", ""))
        round_id = str(window_state.get("round_id", ""))
        publisher = EventPublisher()

        compiled_graph, speaker_prompt = speak_agent(window_state, checkpointer)
        stream_input = {"messages": [{"role": "user", "content": "根据上下文回答用户问题或执行任务或进行讨论"}]}
        config = {
            "configurable": {
                "thread_id": f"{window_state.get('session_id', 0)}_{current_speaker.get('id', 0)}"
            }
        }
        # 先按角色过滤（仅用户/发言人），再取最近 6 条
        history_messages = window_state.get("session_messages", [])
        history_messages = [
            m
            for m in history_messages
            if m.get("role_type") in {RoleType.USER.value, RoleType.SPEAKER.value, RoleType.USER, RoleType.SPEAKER}
        ][-6:]
        context = {
            "user_message": window_state.get("user_message", ""),
            "session_id": window_state.get("session_id"),
            "round_id": window_state.get("round_id"),
            "user_profile": window_state.get("user_profile", {}),
            "transcript": window_state.get("transcript", []),
            "speaker_id": current_speaker.get("id"),
            "history_messages": history_messages,
            "group_members": window_state.get("group_members", []),
            "speaker_prompt": speaker_prompt
        }

        last_updates = None

        async for mode, data in compiled_graph.astream(
            stream_input,
            config=config,
            stream_mode=["messages", "updates"],
            context=context,
        ):

            if mode == "updates":
                if data.get("model"):
                    last_updates = data
                await stream_updates(data, publisher, session_id, round_id, current_speaker, window_state)
            elif mode == "messages":
                await stream_messages(data, publisher, session_id, round_id, current_speaker)

                

        transcript = window_state.get("transcript", [])
        transcript.append(
            {
                "speaker_id": current_speaker.get("id", ""),
                "speaker_name": current_speaker.get("name", ""),
                "content": last_updates.get("model").get("messages")[0].content,
                "timestamp": time.time(),
            }
        )

        chat_messages: list[ChatRecord] = window_state.get("session_messages", [])
        chat_messages.append(
            ChatRecord(
                role_type=RoleType.SPEAKER.value,
                message_type=MsgType.MODEL.value,
                message_content=last_updates.get("model").get("messages")[0].content,
                speaker_id=current_speaker.get("id"),
                speaker_name=current_speaker.get("name"),
            )
        )
        group_members = window_state.get("group_members", [])
        if len(group_members) == 1:
            return Command(
                goto=END, update={"finished": True, "answer": "处理完成", "session_messages": chat_messages, "finish_reason": "处理完成"}
            )
        else:
            return Command(goto="select_speaker_node", update={"transcript": transcript, "session_messages": chat_messages})
        

    state_graph = StateGraph(WindowState)
    state_graph.add_node("select_agents_node", select_agents_node)
    state_graph.add_node("select_speaker_node", select_speaker_node)
    state_graph.add_node("speak_node", speak_node)
    state_graph.add_edge(START, "select_agents_node")
    return state_graph.compile(checkpointer=checkpointer)


_WINDOW_GRAPH: CompiledStateGraph | None = None
_WINDOW_GRAPH_CHECKPOINTER_ID: int | None = None


def get_window_graph(checkpointer) -> CompiledStateGraph:
    global _WINDOW_GRAPH, _WINDOW_GRAPH_CHECKPOINTER_ID
    checkpointer_id = id(checkpointer)
    if _WINDOW_GRAPH is None or _WINDOW_GRAPH_CHECKPOINTER_ID != checkpointer_id:
        _WINDOW_GRAPH = build_graph(checkpointer)
        _WINDOW_GRAPH_CHECKPOINTER_ID = checkpointer_id
    return _WINDOW_GRAPH


# WebSocket handler 通过模块变量访问 checkpointer，避免 websocket.app.state 兼容问题
_CHECKPOINTER = None


def set_checkpointer(checkpointer) -> None:
    global _CHECKPOINTER
    _CHECKPOINTER = checkpointer


def get_checkpointer():
    if _CHECKPOINTER is None:
        raise RuntimeError("checkpointer 未初始化")
    return _CHECKPOINTER
