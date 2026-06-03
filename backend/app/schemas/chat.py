"""
聊天相关 Pydantic 模型。
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """用户发送的聊天消息。"""

    message: str


class ChatResponse(BaseModel):
    """模型返回的聊天回复。"""

    answer: str
