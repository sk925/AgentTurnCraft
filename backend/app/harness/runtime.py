from __future__ import annotations

import logging

from deepagents import create_deep_agent
from langgraph.graph.state import CompiledStateGraph

from app.chat.deepseek_chat_openai import DeepSeekChatOpenAI
from app.database import transactional_session
from app.harness.backend import make_project_backend
from app.harness.cache import (
    _single_chat_agent_lock,
    _speaker_agent_lock,
    get_cached_graph,
    put_cached_graph,
)
from app.harness.config import AgentRuntimeMode
from app.harness.config import AgentBuildConfig
from app.harness.tools import get_agent_tools
from app.model_manage.model_manage_service import ModelManageService

logger = logging.getLogger(__name__)


class AgentRuntime:
    """统一 Deep Agent 编译图工厂。"""

    @staticmethod
    def build(config: AgentBuildConfig) -> CompiledStateGraph:
        from app.chat.base.skill_materializer import (
            build_skill_virtual_paths_for_agent,
            ensure_agent_skills_materialized,
            get_agent_skill_ids,
        )

        ensure_agent_skills_materialized(config.agent_id)
        skill_ids = get_agent_skill_ids(config.agent_id)

        cached = get_cached_graph(config, skill_ids)
        if cached is not None:
            return cached

        build_lock = _single_chat_agent_lock if config.mode is AgentRuntimeMode.SINGLE else _speaker_agent_lock
        with build_lock:
            cached = get_cached_graph(config, skill_ids)
            if cached is not None:
                return cached

            with transactional_session() as session:
                model_info_service = ModelManageService(session)
                model_info = model_info_service.get_chat_model_info_by_model_id(int(config.chat_model_id))

            llm_model = DeepSeekChatOpenAI(
                model=model_info.model_name,
                base_url=model_info.base_url,
                api_key=model_info.api_key,
                stream_usage=True,
            )
            skill_sources = build_skill_virtual_paths_for_agent(config.agent_id)

            compiled_graph = create_deep_agent(
                model=llm_model,
                system_prompt="",
                tools=get_agent_tools(config.agent_id),
                skills=skill_sources or None,
                middleware=list(config.middleware),
                context_schema=config.context_schema,
                checkpointer=config.checkpointer,
                backend=make_project_backend,
            )
            put_cached_graph(config, skill_ids, compiled_graph)
            logger.info(
                "AgentRuntime.build agent_id=%s mode=%s skill_ids=%s",
                config.agent_id,
                config.mode.value,
                skill_ids,
            )
            return compiled_graph
