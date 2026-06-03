"""
聊天服务 — 编排用户消息到 LLM 的完整流程，含会话持久化。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.services.conversation_service import (
    build_context_messages,
    create_conversation,
    get_conversation,
    save_message,
    set_conversation_title_from_first_message,
)
from app.services.llm_service import (
    chat_with_context,
    chat_stream_with_context,
)


async def send_message(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
) -> tuple[str, int]:
    """非流式发送消息。

    Returns:
        (answer, conversation_id)
    """
    # 1. 获取或创建会话
    if conversation_id:
        conv = get_conversation(db, conversation_id, user_id)
        conv_id = conv.id
        is_new = False
    else:
        conv = create_conversation(db, user_id)
        conv_id = conv.id
        is_new = True

    # 2. 保存用户消息
    save_message(db, conv_id, "user", message)

    # 3. 新会话自动生成标题
    if is_new:
        set_conversation_title_from_first_message(db, conv_id)

    # 4. 构建 LLM 上下文
    history = build_context_messages(db, conv_id, user_id)

    # 5. 调用 LLM
    answer = await chat_with_context(history)

    # 6. 保存助手消息
    save_message(db, conv_id, "assistant", answer)

    return answer, conv_id


async def send_message_stream(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
) -> AsyncGenerator[str, None]:
    """流式发送消息，逐 Token 返回。

    Yields:
        每个文本 Token。完成时 yield 特殊标记 ``__CONV_ID__:{id}``。
    """
    # 1. 获取或创建会话
    if conversation_id:
        conv = get_conversation(db, conversation_id, user_id)
        conv_id = conv.id
        is_new = False
    else:
        conv = create_conversation(db, user_id)
        conv_id = conv.id
        is_new = True

    # 2. 保存用户消息
    save_message(db, conv_id, "user", message)

    # 3. 新会话自动生成标题
    if is_new:
        set_conversation_title_from_first_message(db, conv_id)

    # 4. 构建 LLM 上下文
    history = build_context_messages(db, conv_id, user_id)

    # 5. 流式调用 LLM，同时累积完整回复
    full_answer = ""
    async for token in chat_stream_with_context(history):
        full_answer += token
        yield token

    # 6. 流结束后保存助手消息
    save_message(db, conv_id, "assistant", full_answer)

    # 7. 告知前端 conversation_id（新的或用已有的）
    yield f"__CONV_ID__:{conv_id}"
