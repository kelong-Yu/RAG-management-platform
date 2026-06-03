"""
Document 请求/响应 Schema — Pydantic v2。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """文档对外响应。"""

    id: int
    user_id: int
    attachment_id: int | None
    name: str
    doc_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """文档列表响应。"""

    items: list[DocumentResponse]
    total: int
