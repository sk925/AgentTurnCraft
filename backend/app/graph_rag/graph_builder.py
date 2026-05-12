from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from app.graph_rag.extract import summarize_community
from app.graph_rag.schemas import ChunkExtraction


def entity_key(name: str) -> str:
    n = "".join(name.strip().lower().split())
    if not n:
        return "e:_empty_"
    return "e:" + n[:180]


def merge_extraction(
    chunk_index: int,
    extraction: ChunkExtraction,
    entities: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    for em in extraction.entities:
        raw = em.name.strip()
        if not raw:
            continue
        eid = entity_key(raw)
        if eid not in entities:
            entities[eid] = {
                "name": raw,
                "type": em.entity_type or "unknown",
                "chunk_indices": [],
            }
        else:
            if em.entity_type and entities[eid].get("type") in ("unknown", "", None):
                entities[eid]["type"] = em.entity_type
        if chunk_index not in entities[eid]["chunk_indices"]:
            entities[eid]["chunk_indices"].append(chunk_index)

    for rel in extraction.relationships:
        s, t = rel.source.strip(), rel.target.strip()
        if not s or not t:
            continue
        sid, tid = entity_key(s), entity_key(t)
        if sid not in entities:
            entities[sid] = {"name": s, "type": "unknown", "chunk_indices": [chunk_index]}
        elif chunk_index not in entities[sid]["chunk_indices"]:
            entities[sid]["chunk_indices"].append(chunk_index)
        if tid not in entities:
            entities[tid] = {"name": t, "type": "unknown", "chunk_indices": [chunk_index]}
        elif chunk_index not in entities[tid]["chunk_indices"]:
            entities[tid]["chunk_indices"].append(chunk_index)
        edges.append(
            {
                "source": sid,
                "target": tid,
                "relation": rel.relation.strip() or "相关",
                "chunk_indices": [chunk_index],
            }
        )


def dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key_to: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in edges:
        k = (e["source"], e["target"], e["relation"])
        if k not in key_to:
            key_to[k] = {
                "source": e["source"],
                "target": e["target"],
                "relation": e["relation"],
                "chunk_indices": list(e.get("chunk_indices", [])),
            }
        else:
            for c in e.get("chunk_indices", []):
                if c not in key_to[k]["chunk_indices"]:
                    key_to[k]["chunk_indices"].append(c)
    return list(key_to.values())


def _connected_components(
    entities: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[set[str]]:
    """无向图连通分量，作为轻量「社区」划分（不引入 networkx）。"""
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in entities and t in entities:
            adj[s].add(t)
            adj[t].add(s)
    seen: set[str] = set()
    components: list[set[str]] = []
    for node in entities:
        if node in seen:
            continue
        comp: set[str] = set()
        stack = [node]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.add(n)
            for nb in adj.get(n, ()):
                if nb not in seen:
                    stack.append(nb)
        if comp:
            components.append(comp)
    return components


def build_communities(
    entities: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    chunks: list[str],
) -> list[dict[str, Any]]:
    """连通分量作社区 + 每社区调用 LLM 摘要。后续可替换为 Louvain/Leiden。"""
    if not entities:
        return []
    partition = _connected_components(entities, edges)
    communities: list[dict[str, Any]] = []
    for i, comm in enumerate(partition):
        members = sorted(comm)
        if not members:
            continue
        idx_set: set[int] = set()
        for mid in members:
            for ci in entities.get(mid, {}).get("chunk_indices", []):
                idx_set.add(int(ci))
        excerpt_parts: list[str] = []
        for ci in sorted(idx_set)[:8]:
            if 0 <= ci < len(chunks):
                excerpt_parts.append(f"[块 {ci}]\n{chunks[ci]}")
        excerpt = "\n\n".join(excerpt_parts)
        names = [entities[m]["name"] for m in members if m in entities]
        summary = summarize_community(names, excerpt) if excerpt else ""
        communities.append({"id": i, "members": members, "summary": summary})
    return communities


def match_seed_entities(
    query_names: list[str],
    entities: dict[str, dict[str, Any]],
) -> set[str]:
    """将问题中的实体名与图中节点做简单模糊匹配。"""
    matched: set[str] = set()
    if not query_names:
        return matched
    for qn in query_names:
        q = qn.strip().lower()
        if not q:
            continue
        q_compact = "".join(q.split())
        for eid, meta in entities.items():
            name = (meta.get("name") or "").strip().lower()
            if not name:
                continue
            name_compact = "".join(name.split())
            if q == name or q_compact == name_compact:
                matched.add(eid)
                continue
            if q in name or name in q or q_compact in name_compact or name_compact in q_compact:
                matched.add(eid)
    return matched


def collect_subgraph_chunk_indices(
    seeds: set[str],
    entities: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    depth: int,
) -> set[int]:
    if not seeds:
        return set()
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    visited: set[str] = set()
    q: deque[tuple[str, int]] = deque()
    for s in seeds:
        if s in entities:
            q.append((s, 0))
            visited.add(s)
    nodes_in: set[str] = set()
    while q:
        node, d = q.popleft()
        nodes_in.add(node)
        if d >= depth:
            continue
        for nb in adj.get(node, ()):
            if nb not in visited:
                visited.add(nb)
                q.append((nb, d + 1))
                nodes_in.add(nb)

    chunk_ids: set[int] = set()
    for nid in nodes_in:
        for ci in entities.get(nid, {}).get("chunk_indices", []):
            chunk_ids.add(int(ci))
    for e in edges:
        if e["source"] in nodes_in and e["target"] in nodes_in:
            for ci in e.get("chunk_indices", []):
                chunk_ids.add(int(ci))
    return chunk_ids


def build_context_from_chunks(
    chunks: list[str],
    chunk_indices: set[int],
    max_chars: int,
) -> str:
    parts: list[str] = []
    total = 0
    for i in sorted(chunk_indices):
        if i < 0 or i >= len(chunks):
            continue
        block = f"### 片段 {i}\n{chunks[i].strip()}\n"
        if total + len(block) > max_chars:
            remain = max_chars - total
            if remain > 200:
                parts.append(block[:remain] + "\n…(截断)")
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts).strip()


def build_global_context(communities: list[dict[str, Any]], max_chars: int) -> str:
    parts: list[str] = []
    total = 0
    for c in communities:
        line = f"### 主题社区 {c.get('id', 0)}\n{c.get('summary', '').strip()}\n"
        if total + len(line) > max_chars:
            break
        parts.append(line)
        total += len(line)
    return "\n".join(parts).strip()
