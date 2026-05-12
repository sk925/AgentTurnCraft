from typing import Literal

from pydantic import BaseModel, Field


class EntityMention(BaseModel):
    name: str = Field(description="实体名称，与原文一致或规范简称")
    entity_type: str = Field(default="unknown", description="如人物/组织/地点/概念/事件等")


class ExtractedTriple(BaseModel):
    source: str = Field(description="关系主语实体名")
    relation: str = Field(description="关系谓词，简短动词短语")
    target: str = Field(description="关系宾语实体名")


class ChunkExtraction(BaseModel):
    entities: list[EntityMention] = Field(default_factory=list)
    relationships: list[ExtractedTriple] = Field(default_factory=list)


class QueryEntityParse(BaseModel):
    entity_names: list[str] = Field(default_factory=list, description="问题涉及的核心实体名")
    is_global_query: bool = Field(
        default=False,
        description="是否为整体概括类问题（如全文主题、总结、大纲）",
    )


class IndexRequest(BaseModel):
    text: str = Field(..., description="待索引全文")
    source_key: str = Field(..., description="业务侧标识，如 file_id")
    title: str | None = Field(default=None)
    chunk_size: int = Field(default=1200, ge=400, le=8000)
    chunk_overlap: int = Field(default=150, ge=0, le=2000)
    skip_communities: bool = Field(default=False, description="为 True 时跳过社区发现与摘要，加快索引")
    max_chunks: int | None = Field(
        default=None,
        ge=1,
        description="限制参与抽取的块数，超大文档可先抽样",
    )


class QueryRequest(BaseModel):
    corpus_id: int
    question: str
    mode: Literal["auto", "local", "global"] = "auto"
    subgraph_depth: int = Field(default=2, ge=1, le=4)
    max_context_chars: int = Field(default=14000, ge=2000, le=100000)


class CorpusSummary(BaseModel):
    id: int
    source_key: str
    title: str | None
    chunk_count: int
    entity_count: int
    edge_count: int
    community_count: int
