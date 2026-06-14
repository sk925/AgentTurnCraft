"""LangGraph Checkpointer 全局访问（WebSocket / AgentRuntime 共用）。"""

_CHECKPOINTER = None
_SUB_CHECKPOINTER = None


def set_checkpointer(checkpointer) -> None:
    global _CHECKPOINTER
    _CHECKPOINTER = checkpointer


def set_sub_checkpointer(checkpointer) -> None:
    global _SUB_CHECKPOINTER
    _SUB_CHECKPOINTER = checkpointer


def get_checkpointer():
    if _CHECKPOINTER is None:
        raise RuntimeError("checkpointer 未初始化")
    return _CHECKPOINTER


def get_sub_checkpointer():
    return _SUB_CHECKPOINTER
