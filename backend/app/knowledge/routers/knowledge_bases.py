from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.constants import RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM
from app.database import get_db
from app.knowledge.models import KnowledgeBase
from app.knowledge.schemas import KnowledgeBaseCreate, KnowledgeBaseResponse, KnowledgeBaseUpdate
from app.manage.deps import require_manage_roles
from app.model_manage.model_cat import ChatModel, ModelType
from app.chat.base.schemas import ApiResponse, PaginatedData, success_response
from app.query_access import get_knowledge_base_if_readable, list_knowledge_bases_page

router = APIRouter()


def _ensure_embedding_model_exists(db: Session, embedding_model_id: int | None) -> None:
    if embedding_model_id is None:
        return
    row = (
        db.query(ChatModel)
        .filter(
            ChatModel.id == embedding_model_id,
            ChatModel.model_type == ModelType.EMBEDDING.value,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=400, detail="所选 Embedding 模型不存在或类型不正确")


@router.get("/knowledge-bases", response_model=ApiResponse[PaginatedData[KnowledgeBaseResponse]])
def get_knowledge_bases(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
    q: Annotated[str | None, Query(max_length=200)] = None,
    type: Annotated[int | None, Query(ge=1, le=2, description="1 内置 2 自定义")] = None,
):
    """分页获取知识库列表（须登录：内置 + 当前用户自己的自定义）。"""
    if type is not None and type not in (RESOURCE_TYPE_BUILTIN, RESOURCE_TYPE_CUSTOM):
        raise HTTPException(status_code=400, detail="无效的知识库类型筛选")

    items, total = list_knowledge_bases_page(
        db,
        current_user,
        page=page,
        page_size=page_size,
        q=q,
        resource_type=type,
    )
    return success_response(
        PaginatedData[KnowledgeBaseResponse](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/knowledge-bases/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBaseResponse])
def get_knowledge_base(
    knowledge_base_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取单个知识库详情（须登录且对该库可见）。"""
    row = get_knowledge_base_if_readable(db, knowledge_base_id, current_user)
    if row is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return success_response(row)


@router.post("/knowledge-bases", response_model=ApiResponse[KnowledgeBaseResponse])
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    _ensure_embedding_model_exists(db, payload.embedding_model_id)
    resource_type = RESOURCE_TYPE_BUILTIN if current_user.is_superuser else RESOURCE_TYPE_CUSTOM
    row = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        embedding_model_id=payload.embedding_model_id,
        user_id=current_user.id,
        resource_type=resource_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success_response(row)


@router.put("/knowledge-bases/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBaseResponse])
def update_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdate,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    row = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权编辑：仅创建人可修改该知识库")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")
    for field, value in update_data.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    return success_response(row)


@router.delete("/knowledge-bases/{knowledge_base_id}")
def delete_knowledge_base(
    knowledge_base_id: int,
    current_user: Annotated[CurrentUser, Depends(require_manage_roles("agent_manager"))],
    db: Session = Depends(get_db),
):
    row = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除：仅创建人可删除该知识库")

    db.delete(row)
    db.commit()
    return success_response({"deleted": True}, message="删除成功")
