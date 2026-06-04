"""
会话与消息服务 — 会话 CRUD、消息持久化。
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ConversationResponse, MessageResponse


# ============================================================
# Conversation
# ============================================================


def create_conversation(
    db: Session, user_id: int, title: str | None = None
) -> ConversationResponse:
    """创建新会话。"""
    conversation = Conversation(
        user_id=user_id,
        title=title or "新对话",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


def list_conversations(db: Session, user_id: int) -> list[ConversationResponse]:
    """获取当前用户的所有会话，按更新时间倒序。"""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [ConversationResponse.model_validate(c) for c in conversations]


def get_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    """获取会话并校验归属。"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )
    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问该会话",
        )
    return conversation


def update_conversation_title(
    db: Session, conversation_id: int, user_id: int, title: str
) -> ConversationResponse:
    """更新会话标题。"""
    conversation = get_conversation(db, conversation_id, user_id)
    conversation.title = title[:100]
    db.commit()
    db.refresh(conversation)
    return ConversationResponse.model_validate(conversation)


def delete_conversation(db: Session, conversation_id: int, user_id: int) -> None:
    """删除会话及其所有消息。"""
    conversation = get_conversation(db, conversation_id, user_id)
    # 先删除关联消息
    db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).delete()
    db.delete(conversation)
    db.commit()


# ============================================================
# Message
# ============================================================


def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    extra_data: dict | None = None,
) -> MessageResponse:
    """保存一条消息到数据库。

    Args:
        extra_data: 扩展元数据，如 {"attachment_ids": [1, 2]}
    """
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        extra_data=extra_data,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)


def get_messages(
    db: Session, conversation_id: int, user_id: int
) -> list[MessageResponse]:
    """获取会话的所有消息（校验归属）。"""
    get_conversation(db, conversation_id, user_id)  # 校验归属
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [MessageResponse.model_validate(m) for m in messages]


def build_context_messages(
    db: Session, conversation_id: int, user_id: int
) -> list[dict]:
    """构建 LLM 上下文消息列表（包含 system prompt + 历史 + 当前身份信息）。"""
    conversation = get_conversation(db, conversation_id, user_id)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    result: list[dict] = []
    for m in messages:
        result.append({"role": m.role, "content": m.content})
    return result


def set_conversation_title_from_first_message(
    db: Session, conversation_id: int
) -> None:
    """将首条用户消息压缩成简短摘要作为会话标题。"""
    first = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
        .order_by(Message.created_at.asc())
        .first()
    )
    if first and first.content:
        title = _build_conversation_title(first.content)
        db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"title": title}
        )
        db.commit()


def _build_conversation_title(content: str) -> str:
    """基于用户首条消息生成简短标题，避免直接出现长文本或纯空白。"""
    normalized = " ".join(content.strip().split())
    if not normalized:
        return "新对话"

    for prefix in ("请帮我", "帮我", "请问", "我想", "我想要", "想问下"):
        if normalized.startswith(prefix) and len(normalized) > len(prefix):
            normalized = normalized[len(prefix):].strip()
            break

    if not normalized:
        return "新对话"

    preferred_separators = ("。", "！", "？", ".", "!", "?", "\n", ",", "，")
    for sep in preferred_separators:
        pos = normalized.find(sep)
        if 0 < pos <= 24:
            return normalized[:pos].strip()[:24]

    return (
        normalized[:24].rstrip() + "..."
        if len(normalized) > 24
        else normalized
    )
