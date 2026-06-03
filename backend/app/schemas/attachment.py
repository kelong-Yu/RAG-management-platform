"""
Attachment 请求/响应 Schema — Pydantic v2。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AttachmentResponse(BaseModel):
    """附件对外响应。"""

    id: int
    user_id: int
    file_name: str
    stored_name: str
    file_path: str
    mime_type: str
    file_size: int
    source_type: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentListResponse(BaseModel):
    """附件列表响应。"""

    items: list[AttachmentResponse]
    total: int


class UploadStatus(BaseModel):
    """上传状态（可用于轮询）。"""

    file_id: int | None = None
    status: str = Field(
        default="idle", description="idle / uploading / success / error"
    )
    error_message: str | None = None
