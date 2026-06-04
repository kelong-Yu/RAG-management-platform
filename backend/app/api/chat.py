"""
聊天接口 — 消息发送、SSE 流式、会话管理（含 RAG 检索增强）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.chat import (
    ChatCapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    CitationSchema,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.services.chat_service import send_message, send_message_stream
from app.services.llm_service import is_vision_capable
from app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_messages,
    list_conversations,
    update_conversation_title,
)

router = APIRouter(prefix="/chat", tags=["chat"])


# ============================================================
# 消息发送
# ============================================================


@router.get("/capabilities", response_model=ChatCapabilitiesResponse)
async def chat_capabilities():
    """返回当前聊天能力开关。"""
    return ChatCapabilitiesResponse(vision_capable=is_vision_capable())


@router.post("/", response_model=ChatResponse)
async def chat_send(
    body: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """非流式发送聊天消息，返回 AI 回复。

    首次对话不传 conversation_id，后端自动创建新会话。
    设置 use_rag=true 启用知识库检索增强。
    传入 attachment_ids 可关联已上传的图片附件。
    """
    answer, conv_id, citations, image_meta = await send_message(
        db,
        user_id,
        body.message,
        body.conversation_id,
        use_rag=body.use_rag,
        attachment_ids=body.attachment_ids,
    )
    return ChatResponse(
        answer=answer,
        conversation_id=conv_id,
        citations=[CitationSchema(**c) for c in citations],
        attachment_ids=[img["attachment_id"] for img in image_meta],
    )


@router.get("/stream")
async def chat_stream(
    message: str = Query(..., description="用户输入的消息"),
    conversation_id: int | None = Query(None, description="会话 ID，不传则自动创建"),
    use_rag: bool = Query(False, description="是否启用知识库检索增强"),
    attachment_ids: list[int] = Query([], description="关联的图片附件 ID 列表"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """流式发送聊天消息（SSE），逐 Token 返回。

    返回格式：``data: <token>``。
    末尾发送：
    - ``data: __IMAGES__:<json>`` 包含图片附件元数据
    - ``data: __CITATIONS__:<json>`` 包含知识库引用
    - ``data: __CONV_ID__:<id>`` 告知前端会话 ID。
    兼容浏览器 EventSource API。
    """

    async def event_generator():
        try:
            async for token in send_message_stream(
                db,
                user_id,
                message,
                conversation_id,
                use_rag=use_rag,
                attachment_ids=attachment_ids,
            ):
                yield {"data": token}
        except Exception as e:
            yield {"data": f"[错误] {str(e)}"}

    return EventSourceResponse(event_generator())


# ============================================================
# 会话管理
# ============================================================


@router.get("/conversations", response_model=list[ConversationResponse])
async def chat_conversations(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取当前用户的会话列表，按更新时间倒序。"""
    return list_conversations(db, user_id)


@router.post("/conversations", response_model=ConversationResponse)
async def chat_create_conversation(
    body: ConversationCreate | None = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """创建新会话。"""
    return create_conversation(db, user_id, body.title if body else None)


@router.delete("/conversations/{conversation_id}")
async def chat_delete_conversation(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """删除会话及其所有消息。"""
    delete_conversation(db, conversation_id, user_id)
    return {"message": "deleted"}


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def chat_update_conversation(
    conversation_id: int,
    body: ConversationUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """手动更新会话标题。"""
    return update_conversation_title(db, conversation_id, user_id, body.title)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def chat_messages(
    conversation_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取指定会话的历史消息。"""
    return get_messages(db, conversation_id, user_id)
