"""
聊天相关 Pydantic 模型。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    """用户发送的聊天消息。"""

    message: str
    conversation_id: int | None = None
    use_rag: bool = False
    attachment_ids: list[int] = []


class ChatResponse(BaseModel):
    """模型返回的聊天回复（含会话 ID 和可选引用）。"""

    answer: str
    conversation_id: int
    citations: list["CitationSchema"] = []
    attachment_ids: list[int] = []


class ChatCapabilitiesResponse(BaseModel):
    """聊天能力查询响应。"""

    vision_capable: bool


# ============================================================
# Citation
# ============================================================


class CitationSchema(BaseModel):
    """引用来源信息。"""

    document_name: str
    page_number: int | None
    chunk_index: int
    content_snippet: str  # 截取前 200 字符
    similarity: float


# ============================================================
# Conversation
# ============================================================


class ConversationCreate(BaseModel):
    """创建新会话。"""

    title: str | None = None


class ConversationUpdate(BaseModel):
    """更新会话标题。"""

    title: str


class ConversationResponse(BaseModel):
    """会话概要（列表用）。"""

    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Message
# ============================================================


class MessageResponse(BaseModel):
    """消息响应。"""

    id: int
    conversation_id: int
    role: str
    content: str
    extra_data: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
