from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Iterable

from langgraph.graph.state import CompiledStateGraph

from app.harness.config import AgentBuildConfig, AgentRuntimeMode

_SPEAKER_AGENT_CACHE_MAX = 128

_single_chat_agent_map: dict[str, CompiledStateGraph] = {}
_single_chat_agent_lock = threading.RLock()

_speaker_agent_map: OrderedDict[tuple[int, int, tuple[int, ...]], CompiledStateGraph] = OrderedDict()
_speaker_agent_lock = threading.RLock()


def single_chat_cache_key(agent_id: int, skill_ids: tuple[int, ...]) -> str:
    skill_part = "-".join(str(sid) for sid in skill_ids) if skill_ids else "none"
    return f"{agent_id}_single_chat_{skill_part}"


def speaker_cache_key(config: AgentBuildConfig, skill_ids: tuple[int, ...]) -> tuple[int, int, tuple[int, ...]]:
    return (config.agent_id, id(config.checkpointer), skill_ids)


def get_cached_graph(config: AgentBuildConfig, skill_ids: tuple[int, ...]) -> CompiledStateGraph | None:
    if config.mode is AgentRuntimeMode.SINGLE:
        key = single_chat_cache_key(config.agent_id, skill_ids)
        with _single_chat_agent_lock:
            return _single_chat_agent_map.get(key)

    key = speaker_cache_key(config, skill_ids)
    with _speaker_agent_lock:
        graph = _speaker_agent_map.get(key)
        if graph is not None:
            _speaker_agent_map.move_to_end(key)
        return graph


def put_cached_graph(
    config: AgentBuildConfig,
    skill_ids: tuple[int, ...],
    graph: CompiledStateGraph,
) -> None:
    if config.mode is AgentRuntimeMode.SINGLE:
        key = single_chat_cache_key(config.agent_id, skill_ids)
        with _single_chat_agent_lock:
            _single_chat_agent_map[key] = graph
        return

    key = speaker_cache_key(config, skill_ids)
    with _speaker_agent_lock:
        if key in _speaker_agent_map:
            del _speaker_agent_map[key]
        elif _SPEAKER_AGENT_CACHE_MAX > 0 and len(_speaker_agent_map) >= _SPEAKER_AGENT_CACHE_MAX:
            _speaker_agent_map.popitem(last=False)
        _speaker_agent_map[key] = graph


def evict_single_chat_agent_cache_for_agent_ids(agent_ids: Iterable[int]) -> None:
    affected = {int(aid) for aid in agent_ids}
    if not affected:
        return
    with _single_chat_agent_lock:
        stale = [k for k in _single_chat_agent_map if any(k.startswith(f"{aid}_single_chat") for aid in affected)]
        for key in stale:
            _single_chat_agent_map.pop(key, None)


def evict_speaker_agent_graph_cache_for_agent_ids(agent_ids: Iterable[int]) -> None:
    affected = {int(aid) for aid in agent_ids}
    if not affected:
        return
    with _speaker_agent_lock:
        stale_keys = [k for k in _speaker_agent_map if k[0] in affected]
        for key in stale_keys:
            del _speaker_agent_map[key]


def evict_agent_runtime_cache_for_agent_ids(agent_ids: Iterable[int]) -> None:
    """按智能体 id 淘汰单聊与群聊发言人的编译图缓存。"""
    evict_speaker_agent_graph_cache_for_agent_ids(agent_ids)
    evict_single_chat_agent_cache_for_agent_ids(agent_ids)


def clear_speaker_agent_graph_cache() -> None:
    with _speaker_agent_lock:
        _speaker_agent_map.clear()
