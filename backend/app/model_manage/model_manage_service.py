from app.exceptions import AppException
from app.model_manage.model_cat import ChatModel, ModelProvider
from app.model_manage.scheme import (
    AgentChatModelInfo,
    ChatModelCreateRequest,
    ChatModelResponse,
    ChatModelUpdateRequest,
    ModelProviderCreateRequest,
    ModelProviderResponse,
    ModelProviderUpdateRequest,
)
from app.chat.base.models import Agent
from fastapi import status
from sqlalchemy.orm import Session


class ModelManageService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _pid_int(provider_id: str | int) -> int:
        if isinstance(provider_id, int):
            return provider_id
        return int(str(provider_id).strip())

    def _provider_row(self, provider_id: int) -> ModelProvider | None:
        return self.db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()

    def _provider_resp(self, row: ModelProvider) -> ModelProviderResponse:
        return ModelProviderResponse.model_validate(row)

    def _chat_resp(self, row: ChatModel) -> ChatModelResponse:
        prov = self._provider_row(int(row.provider_id))
        pn = prov.name if prov else ""
        return ChatModelResponse(
            id=str(row.id),
            name=row.name,
            provider_id=str(row.provider_id),
            provider_name=pn,
            model_type=row.model_type,
            description=row.description,
        )

    def _agent_ids_bound_to_chat_models(self, chat_model_ids: list[int]) -> list[int]:
        """当前仍绑定到给定聊天模型 id 的智能体 id（用于按 agent 淘汰发言人图缓存）。"""
        if not chat_model_ids:
            return []
        rows = (
            self.db.query(Agent.id)
            .filter(Agent.chat_model_id.in_(chat_model_ids))
            .distinct()
            .all()
        )
        return [int(r[0]) for r in rows]

    def _evict_speaker_graph_cache_for_chat_models(self, chat_model_ids: list[int]) -> None:
        agent_ids = self._agent_ids_bound_to_chat_models(chat_model_ids)
        if not agent_ids:
            return
        from app.harness import evict_agent_runtime_cache_for_agent_ids

        evict_agent_runtime_cache_for_agent_ids(agent_ids)

    def create_model_provider(self, model_provider: ModelProviderCreateRequest) -> ModelProviderResponse:
        row = ModelProvider(
            name=model_provider.name,
            base_url=model_provider.base_url,
            api_key=model_provider.api_key,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._provider_resp(row)

    def update_model_provider(self, model_provider: ModelProviderUpdateRequest) -> ModelProviderResponse:
        pid = self._pid_int(model_provider.id)
        row = self._provider_row(pid)
        if row is None:
            raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
        if model_provider.name is not None:
            row.name = model_provider.name
        if model_provider.base_url is not None:
            row.base_url = model_provider.base_url
        if model_provider.api_key is not None:
            row.api_key = model_provider.api_key
        self.db.commit()
        self.db.refresh(row)
        chat_ids = [cm.id for cm in self.db.query(ChatModel).filter(ChatModel.provider_id == pid).all()]
        self._evict_speaker_graph_cache_for_chat_models(chat_ids)
        return self._provider_resp(row)

    def get_model_provider_by_id(self, provider_id: int) -> ModelProviderResponse:
        row = self._provider_row(provider_id)
        if row is None:
            raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
        return self._provider_resp(row)

    def get_all_model_providers(self) -> list[ModelProviderResponse]:
        rows = self.db.query(ModelProvider).order_by(ModelProvider.create_time.desc()).all()
        return [self._provider_resp(r) for r in rows]

    def delete_model_provider_by_id(self, provider_id: int) -> None:
        """根据ID删除模型提供者"""
        row = self._provider_row(provider_id)
        if row is None:
            raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
        chat_ids = [
            cm.id
            for cm in self.db.query(ChatModel).filter(ChatModel.provider_id == provider_id).all()
        ]
        if chat_ids:
            bound = self.db.query(Agent).filter(Agent.chat_model_id.in_(chat_ids)).first()
            if bound is not None:
                raise AppException(
                    message="该提供者下的聊天模型已被智能体使用，请先解除智能体中的模型关联后再删除",
                    code=status.HTTP_400_BAD_REQUEST,
                )
        self.db.delete(row)
        self.db.commit()

    def create_chat_model(self, chat_model: ChatModelCreateRequest) -> ChatModelResponse:
        pid = self._pid_int(chat_model.provider_id)
        if self._provider_row(pid) is None:
            raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
        row = ChatModel(
            name=chat_model.name,
            provider_id=pid,
            model_type=chat_model.model_type,
            description=chat_model.description,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._chat_resp(row)

    def update_chat_model(self, chat_model: ChatModelUpdateRequest) -> ChatModelResponse:
        mid = self._pid_int(chat_model.id)
        row = self.db.query(ChatModel).filter(ChatModel.id == mid).first()
        if row is None:
            raise AppException(message="Chat model not found", code=status.HTTP_404_NOT_FOUND)
        if chat_model.name is not None:
            row.name = chat_model.name
        if chat_model.provider_id is not None:
            new_pid = self._pid_int(chat_model.provider_id)
            if self._provider_row(new_pid) is None:
                raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
            row.provider_id = new_pid
        if chat_model.model_type is not None:
            row.model_type = chat_model.model_type
        if chat_model.description is not None:
            row.description = chat_model.description
        self.db.commit()
        self.db.refresh(row)
        self._evict_speaker_graph_cache_for_chat_models([mid])
        return self._chat_resp(row)

    def get_chat_model_by_id(self, chat_model_id: int) -> ChatModelResponse:
        row = self.db.query(ChatModel).filter(ChatModel.id == chat_model_id).first()
        if row is None:
            raise AppException(message="Chat model not found", code=status.HTTP_404_NOT_FOUND)
        return self._chat_resp(row)

    def get_all_chat_models(self) -> list[ChatModelResponse]:
        """获取所有聊天模型"""
        rows = self.db.query(ChatModel).order_by(ChatModel.create_time.desc()).all()
        return [self._chat_resp(r) for r in rows]


    def delete_chat_model_by_id(self, chat_model_id: int) -> None:
        """根据ID删除聊天模型"""
        row = self.db.query(ChatModel).filter(ChatModel.id == chat_model_id).first()
        if row is None:
            raise AppException(message="Chat model not found", code=status.HTTP_404_NOT_FOUND)
        agents = self.db.query(Agent).filter(Agent.chat_model_id == chat_model_id).all()
        if agents:
            raise AppException(message="Chat model is used by agents", code=status.HTTP_400_BAD_REQUEST)
        self.db.delete(row)
        self.db.commit()

    def list_chat_models_by_provider_id(self, provider_id: int) -> list[ChatModelResponse]:
        """根据提供者ID获取聊天模型"""
        if self._provider_row(provider_id) is None:
            raise AppException(message="Model provider not found", code=status.HTTP_404_NOT_FOUND)
        rows = (
            self.db.query(ChatModel)
            .filter(ChatModel.provider_id == provider_id)
            .order_by(ChatModel.create_time.desc())
            .all()
        )
        return [self._chat_resp(r) for r in rows]


    def get_chat_model_info_by_model_id(self, model_id: int) -> AgentChatModelInfo:
        """根据模型ID获取模型信息"""

        row = self.db.query(ModelProvider,ChatModel).filter(ChatModel.id == model_id).join(ModelProvider,ModelProvider.id == ChatModel.provider_id).first()
        if row is None:
            raise AppException(message="Chat model not found", code=status.HTTP_404_NOT_FOUND)
        return AgentChatModelInfo(
            model_name=row.ChatModel.name,
            base_url=row.ModelProvider.base_url,
            api_key=row.ModelProvider.api_key,
        )

