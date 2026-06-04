"""
Document 请求/响应 Schema — Pydantic v2。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Document ──────────────────────────────────────────────────────────


class DocumentResponse(BaseModel):
    """文档对外响应。"""

    id: int
    user_id: int
    attachment_id: int | None
    name: str
    doc_type: str
    status: str
    error_message: str | None
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """文档列表响应。"""

    items: list[DocumentResponse]
    total: int


class DocumentCreateRequest(BaseModel):
    """从已有附件创建文档的请求。"""

    attachment_id: int


class DocumentProcessRequest(BaseModel):
    """触发/重试文档处理的请求（当前无需额外参数）。"""
    pass


# ── DocumentChunk ─────────────────────────────────────────────────────


class DocumentChunkResponse(BaseModel):
    """切片对外响应。"""

    id: int
    document_id: int
    chunk_index: int
    page_number: int | None
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkListResponse(BaseModel):
    """切片列表响应。"""

    items: list[DocumentChunkResponse]
    total: int


# ── 文档详情（含切片数量摘要）─────────────────────────────────────────


class DocumentDetailResponse(DocumentResponse):
    """文档详情（比列表多一个切片数量统计）。"""

    chunk_count: int
