"""
聊天相关 Pydantic 模型。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    """用户发送的聊天消息。"""

    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    """模型返回的聊天回复（含会话 ID）。"""

    answer: str
    conversation_id: int


# ============================================================
# Conversation
# ============================================================


class ConversationCreate(BaseModel):
    """创建新会话。"""

    title: str | None = None


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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
