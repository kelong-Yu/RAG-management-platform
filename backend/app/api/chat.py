"""
聊天接口 — POST /api/chat
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user_id: int = Depends(get_current_user_id),
):
    """发送聊天消息，返回 AI 回复。

    需要 JWT 认证（Authorization: Bearer <token>）。
    """
    answer = await chat_service(body.message)
    return ChatResponse(answer=answer)
