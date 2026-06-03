"""
聊天接口 — POST /api/chat, GET /api/chat/stream
"""

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat as chat_service
from app.services.chat_service import chat_stream as chat_stream_service

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


@router.get("/stream")
async def send_message_stream(
    message: str = Query(..., description="用户输入的消息"),
    user_id: int = Depends(get_current_user_id),
):
    """发送聊天消息，通过 SSE 流式返回 AI 回复。

    需要 JWT 认证（Authorization: Bearer <token>）。
    返回格式：data: <token>
    兼容浏览器 EventSource API。
    """

    async def event_generator():
        async for token in chat_stream_service(message):
            yield {"data": token}

    return EventSourceResponse(event_generator())
