from typing import Annotated, List

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.model_manage.model_manage_service import ModelManageService
from app.model_manage.scheme import (
    ChatModelCreateRequest,
    ChatModelResponse,
    ChatModelUpdateRequest,
    ModelProviderCreateRequest,
    ModelProviderResponse,
    ModelProviderUpdateRequest,
)
from app.schemas import ApiResponse, success_response
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

model_manage_router = APIRouter(
    prefix="/model-manage",
    tags=["model-manage"],
)


def _svc(db: Session) -> ModelManageService:
    return ModelManageService(db)


@model_manage_router.post("/model-provider", response_model=ApiResponse[ModelProviderResponse])
def create_model_provider(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    body: ModelProviderCreateRequest,
    db: Session = Depends(get_db),
):
    """创建模型提供者"""
    return success_response(_svc(db).create_model_provider(body))


@model_manage_router.get("/model-providers", response_model=ApiResponse[List[ModelProviderResponse]])
def list_model_providers(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """列出全部模型提供者"""
    return success_response(_svc(db).get_all_model_providers())


@model_manage_router.get("/model-provider/{provider_id}", response_model=ApiResponse[ModelProviderResponse])
def get_model_provider(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    provider_id: str,
    db: Session = Depends(get_db),
):
    """按 ID 获取模型提供者"""
    return success_response(_svc(db).get_model_provider_by_id(ModelManageService._pid_int(provider_id)))


@model_manage_router.patch("/model-provider", response_model=ApiResponse[ModelProviderResponse])
def update_model_provider(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    body: ModelProviderUpdateRequest,
    db: Session = Depends(get_db),
):
    """更新模型提供者"""
    return success_response(_svc(db).update_model_provider(body))


@model_manage_router.delete("/model-provider/{provider_id}", response_model=ApiResponse[None])
def delete_model_provider(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    provider_id: str,
    db: Session = Depends(get_db),
):
    """删除模型提供者（级联删除其下聊天模型）"""
    _svc(db).delete_model_provider_by_id(ModelManageService._pid_int(provider_id))
    return success_response(None, message="deleted")


@model_manage_router.post("/chat-model", response_model=ApiResponse[ChatModelResponse])
def create_chat_model(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    body: ChatModelCreateRequest,
    db: Session = Depends(get_db),
):
    """创建聊天模型"""
    return success_response(_svc(db).create_chat_model(body))


@model_manage_router.get("/chat-models", response_model=ApiResponse[List[ChatModelResponse]])
def list_chat_models(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
    provider_id: str | None = Query(None, description="若提供则只返回该提供者的模型"),
):
    """列出聊天模型；可传 provider_id 过滤"""
    svc = _svc(db)
    if provider_id is not None and provider_id.strip() != "":
        return success_response(svc.list_chat_models_by_provider_id(ModelManageService._pid_int(provider_id)))
    return success_response(svc.get_all_chat_models())


@model_manage_router.get("/chat-model/{chat_model_id}", response_model=ApiResponse[ChatModelResponse])
def get_chat_model(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    chat_model_id: str,
    db: Session = Depends(get_db),
):
    """按 ID 获取聊天模型"""
    return success_response(_svc(db).get_chat_model_by_id(ModelManageService._pid_int(chat_model_id)))


@model_manage_router.patch("/chat-model", response_model=ApiResponse[ChatModelResponse])
def update_chat_model(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    body: ChatModelUpdateRequest,
    db: Session = Depends(get_db),
):
    """更新聊天模型"""
    return success_response(_svc(db).update_chat_model(body))


@model_manage_router.delete("/chat-model/{chat_model_id}", response_model=ApiResponse[None])
def delete_chat_model(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    chat_model_id: str,
    db: Session = Depends(get_db),
):
    """删除聊天模型"""
    _svc(db).delete_chat_model_by_id(ModelManageService._pid_int(chat_model_id))
    return success_response(None, message="deleted")
