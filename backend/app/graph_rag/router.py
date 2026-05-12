from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user_id
from app.database import get_db
from app.graph_rag.pipeline import build_payload, list_corpora_summaries, run_query, save_corpus
from app.graph_rag.schemas import CorpusSummary, IndexRequest, QueryRequest
from app.schemas import ApiResponse, success_response

router = APIRouter(prefix="/graph_rag")


@router.post("/index", response_model=ApiResponse[dict[str, Any]])
def index_document(
    body: IndexRequest,
    member_id: Annotated[int, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    """对原始文本建图并入库（分块 → 抽取 → 图连通分量作社区并摘要）。"""
    payload = build_payload(body)
    row = save_corpus(
        db,
        user_id=member_id,
        source_key=body.source_key,
        title=body.title,
        payload=payload,
    )
    meta = payload.get("meta") or {}
    return success_response(
        {
            "corpus_id": row.id,
            "chunk_count": meta.get("chunk_count", 0),
            "entity_count": len(payload.get("entities") or {}),
            "edge_count": len(payload.get("edges") or []),
            "community_count": len(payload.get("communities") or []),
        },
        message="索引完成",
    )


@router.post("/query", response_model=ApiResponse[dict[str, Any]])
def query_corpus(
    body: QueryRequest,
    member_id: Annotated[int, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    """基于已索引语料问答（local=子图块；global=社区摘要；auto 自动判定）。"""
    result = run_query(db, member_id, body)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return success_response(result)


@router.get("/corpora", response_model=ApiResponse[list[CorpusSummary]])
def list_corpora(
    member_id: Annotated[int, Depends(get_current_user_id)],
    db: Session = Depends(get_db),
):
    return success_response(list_corpora_summaries(db, member_id))
