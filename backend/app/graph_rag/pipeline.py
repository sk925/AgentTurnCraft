from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.graph_rag.chunking import chunk_text
from app.graph_rag.db_models import GraphRagCorpus
from app.graph_rag.extract import answer_with_context, extract_from_chunk, parse_question
from app.graph_rag.graph_builder import (
    build_communities,
    build_context_from_chunks,
    build_global_context,
    collect_subgraph_chunk_indices,
    dedupe_edges,
    match_seed_entities,
    merge_extraction,
)
from app.graph_rag.schemas import CorpusSummary, IndexRequest, QueryRequest


def build_payload(req: IndexRequest) -> dict[str, Any]:
    chunks = chunk_text(req.text, chunk_size=req.chunk_size, overlap=req.chunk_overlap)
    if req.max_chunks is not None:
        chunks = chunks[: req.max_chunks]
    entities: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for i, ch in enumerate(chunks):
        ext = extract_from_chunk(ch)
        merge_extraction(i, ext, entities, edges)
    edges = dedupe_edges(edges)
    communities: list[dict[str, Any]] = []
    if not req.skip_communities and chunks:
        communities = build_communities(entities, edges, chunks)
    return {
        "chunks": chunks,
        "entities": entities,
        "edges": edges,
        "communities": communities,
        "meta": {
            "chunk_size": req.chunk_size,
            "chunk_overlap": req.chunk_overlap,
            "chunk_count": len(chunks),
        },
    }


def save_corpus(
    db: Session,
    *,
    user_id: int,
    source_key: str,
    title: str | None,
    payload: dict[str, Any],
) -> GraphRagCorpus:
    row = GraphRagCorpus(
        user_id=user_id,
        source_key=source_key,
        title=title,
        payload=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_corpus(db: Session, corpus_id: int, user_id: int) -> GraphRagCorpus | None:
    return (
        db.query(GraphRagCorpus)
        .filter(GraphRagCorpus.id == corpus_id, GraphRagCorpus.user_id == user_id)
        .first()
    )


def list_corpora_summaries(db: Session, user_id: int) -> list[CorpusSummary]:
    rows = (
        db.query(GraphRagCorpus)
        .filter(GraphRagCorpus.user_id == user_id)
        .order_by(GraphRagCorpus.id.desc())
        .all()
    )
    out: list[CorpusSummary] = []
    for r in rows:
        p = r.payload or {}
        chunks = p.get("chunks") or []
        entities = p.get("entities") or {}
        edges = p.get("edges") or []
        comms = p.get("communities") or []
        out.append(
            CorpusSummary(
                id=r.id,
                source_key=r.source_key,
                title=r.title,
                chunk_count=len(chunks) if isinstance(chunks, list) else 0,
                entity_count=len(entities) if isinstance(entities, dict) else 0,
                edge_count=len(edges) if isinstance(edges, list) else 0,
                community_count=len(comms) if isinstance(comms, list) else 0,
            )
        )
    return out


def run_query(db: Session, user_id: int, req: QueryRequest) -> dict[str, Any]:
    row = get_corpus(db, req.corpus_id, user_id)
    if row is None:
        return {"error": "语料不存在或无权访问"}
    payload = row.payload or {}
    chunks = payload.get("chunks") or []
    entities = payload.get("entities") or {}
    edges = payload.get("edges") or []
    communities = payload.get("communities") or []
    if not isinstance(chunks, list) or not chunks:
        return {"error": "语料无有效分块"}

    qparse = parse_question(req.question)
    mode = req.mode
    if mode == "auto":
        mode = "global" if qparse.is_global_query else "local"

    debug: dict[str, Any] = {
        "mode": mode,
        "parsed_entities": qparse.entity_names,
        "is_global_query": qparse.is_global_query,
    }

    if mode == "global":
        ctx = build_global_context(communities, req.max_context_chars)
        if not ctx.strip():
            # 无社区摘要时退回：取前几块作弱全局上下文
            ctx = build_context_from_chunks(chunks, set(range(min(5, len(chunks)))), req.max_context_chars)
        debug["context_kind"] = "communities"
        answer = answer_with_context(req.question, ctx)
        return {"answer": answer, "debug": debug}

    seeds = match_seed_entities(qparse.entity_names, entities)
    debug["matched_entity_ids"] = list(seeds)
    chunk_ids = collect_subgraph_chunk_indices(seeds, entities, edges, req.subgraph_depth)
    if not chunk_ids:
        # 未命中实体：退回向量式朴素检索 — 此处用「前若干块 + 社区摘要」避免无结果
        chunk_ids = set(range(min(3, len(chunks))))
        debug["fallback"] = "no_seed_match_use_head_chunks"
    ctx = build_context_from_chunks(chunks, chunk_ids, req.max_context_chars)
    debug["chunk_indices_used"] = sorted(chunk_ids)
    debug["context_kind"] = "subgraph_chunks"
    answer = answer_with_context(req.question, ctx)
    return {"answer": answer, "debug": debug}
