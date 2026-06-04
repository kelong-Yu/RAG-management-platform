"""
聊天服务 — 编排用户消息到 LLM 的完整流程，含会话持久化、RAG、图片附件。
"""

import json
from collections.abc import AsyncGenerator, Sequence

from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.services.conversation_service import (
    build_context_messages,
    create_conversation,
    get_conversation,
    save_message,
    set_conversation_title_from_first_message,
)
from app.services.llm_service import (
    chat_stream_with_context,
    chat_stream_with_multimodal_context,
    chat_with_context,
    chat_with_multimodal_context,
    is_vision_capable,
)

# RAG 增强的 system prompt 前缀
RAG_SYSTEM_PREFIX = """你是一个知识库问答助手。请根据以下从知识库中检索到的文档片段来回答用户的问题。

要求：
1. 优先使用提供的文档片段来回答问题
2. 如果文档片段不足以回答问题，可以结合你的知识补充，但要明确说明哪些来自文档、哪些来自你的知识
3. 在回答中引用具体文档时，使用 [来源: 文档名] 的格式标注
4. 如果文档片段与问题完全无关，请忽略它们，直接基于你的知识回答

--- 检索到的文档片段 ---

"""


async def send_message(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    use_rag: bool = False,
    attachment_ids: Sequence[int] = (),
) -> tuple[str, int, list[dict], list[dict]]:
    """非流式发送消息。

    Returns:
        (answer, conversation_id, citations, image_meta)
        - image_meta: 图片附件元数据，用于前端展示
    """
    citations: list[dict] = []
    image_meta: list[dict] = []

    # 1. 获取或创建会话
    if conversation_id:
        conv = get_conversation(db, conversation_id, user_id)
        conv_id = conv.id
        is_new = False
    else:
        conv = create_conversation(db, user_id)
        conv_id = conv.id
        is_new = True

    # 2. 校验图片附件归属
    image_paths, image_meta = await _validate_and_collect_images(
        db, user_id, attachment_ids
    )

    # 3. 保存用户消息
    extra = {"attachment_ids": list(attachment_ids)} if attachment_ids else None
    save_message(db, conv_id, "user", message, extra_data=extra)

    # 4. 新会话自动生成标题
    if is_new:
        set_conversation_title_from_first_message(db, conv_id)

    # 5. 构建 LLM 上下文（含 RAG 增强）
    history = build_context_messages(db, conv_id, user_id)

    if use_rag:
        citations, rag_prefix = await _build_rag_prompt(message, user_id, db)
        if rag_prefix:
            history.insert(0, {"role": "system", "content": rag_prefix})

    # 6. 调用 LLM（视觉 vs 纯文本）
    if is_vision_capable() and image_paths:
        answer = await chat_with_multimodal_context(history, image_paths)
    else:
        answer = await chat_with_context(history)

    # 7. 保存助手消息
    save_message(db, conv_id, "assistant", answer)

    return answer, conv_id, citations, image_meta


async def send_message_stream(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    use_rag: bool = False,
    attachment_ids: Sequence[int] = (),
) -> AsyncGenerator[str, None]:
    """流式发送消息，逐 Token 返回。

    Yields:
        每个文本 Token。完成时 yield 特殊标记：
        - ``__IMAGES__:<json>`` 包含图片附件元数据（文件名、MIME 等）
        - ``__CITATIONS__:<json>`` 包含引用数据
        - ``__CONV_ID__:{id}`` 包含会话 ID
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

    # 2. 校验图片附件归属
    image_paths, image_meta = await _validate_and_collect_images(
        db, user_id, attachment_ids
    )

    # 3. 保存用户消息（含 attachment_ids 元数据）
    extra = {"attachment_ids": list(attachment_ids)} if attachment_ids else None
    save_message(db, conv_id, "user", message, extra_data=extra)

    # 4. 新会话自动生成标题
    if is_new:
        set_conversation_title_from_first_message(db, conv_id)

    # 5. 构建 LLM 上下文（含 RAG 增强）
    history = build_context_messages(db, conv_id, user_id)
    citations: list[dict] = []

    if use_rag:
        citations, rag_prefix = await _build_rag_prompt(message, user_id, db)
        if rag_prefix:
            history.insert(0, {"role": "system", "content": rag_prefix})

    # 6. 流式调用 LLM（视觉 vs 纯文本）
    full_answer = ""
    if is_vision_capable() and image_paths:
        async for token in chat_stream_with_multimodal_context(history, image_paths):
            full_answer += token
            yield token
    else:
        async for token in chat_stream_with_context(history):
            full_answer += token
            yield token

    # 7. 流结束后保存助手消息
    assistant_message = save_message(db, conv_id, "assistant", full_answer)

    # 8. 告知前端持久化后的 assistant message id
    yield f"__ASSISTANT_ID__:{assistant_message.id}"

    # 9. 发送图片元数据（前端用于渲染图片 + 降级提示）
    if image_meta:
        payload = {
            "images": image_meta,
            "vision_capable": is_vision_capable(),
        }
        yield f"__IMAGES__:{json.dumps(payload, ensure_ascii=False)}"

    # 10. 发送引用数据
    if citations:
        yield f"__CITATIONS__:{json.dumps(citations, ensure_ascii=False)}"

    # 11. 告知前端 conversation_id
    yield f"__CONV_ID__:{conv_id}"


# ── 图片附件辅助 ────────────────────────────────────────────────────────


async def _validate_and_collect_images(
    db: Session,
    user_id: int,
    attachment_ids: Sequence[int],
) -> tuple[list[str], list[dict]]:
    """校验图片附件归属并收集元数据。

    Args:
        db: 数据库会话
        user_id: 当前用户 ID
        attachment_ids: 前端传入的附件 ID 列表

    Returns:
        (image_paths, image_meta)
        - image_paths: 本地文件路径列表（仅图片类型）
        - image_meta: 图片元数据列表，用于前端渲染
    """
    if not attachment_ids:
        return [], []

    attachments = (
        db.query(Attachment)
        .filter(
            Attachment.id.in_(list(attachment_ids)),
            Attachment.user_id == user_id,
        )
        .all()
    )

    # 校验数量一致（防止越权访问不存在的附件）
    if len(attachments) != len(set(attachment_ids)):
        raise ValueError("部分附件不存在或无权访问")

    image_paths: list[str] = []
    image_meta: list[dict] = []

    for att in sorted(attachments, key=lambda a: list(attachment_ids).index(a.id)):
        is_image = att.mime_type and att.mime_type.startswith("image/")
        image_meta.append({
            "attachment_id": att.id,
            "file_name": att.file_name,
            "mime_type": att.mime_type,
            "file_size": att.file_size,
            "is_image": is_image,
        })
        if is_image:
            image_paths.append(att.file_path)

    return image_paths, image_meta


# ── RAG 辅助 ───────────────────────────────────────────────────────────


async def _build_rag_prompt(
    query: str, user_id: int, db: Session
) -> tuple[list[dict], str]:
    """
    检索相关 chunks 并构建 RAG 增强的 system prompt。

    Returns:
        (citations, rag_prefix)
        - citations: 引用数据列表，用于返回给前端
        - rag_prefix: 拼入 LLM 上下文的 system prompt 前缀
    """
    from app.services.retriever_service import retrieve

    citations_raw = await retrieve(query, user_id, db)

    if not citations_raw:
        return [], ""

    citations: list[dict] = []
    context_parts: list[str] = []

    for i, c in enumerate(citations_raw):
        citations.append({
            "document_name": c.document_name,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "content_snippet": c.content[:200],
            "similarity": c.similarity,
        })

        page_info = f"第{c.page_number}页" if c.page_number else "未知页码"
        context_parts.append(
            f"[片段 {i + 1}] "
            f"来源: 《{c.document_name}》({page_info}), "
            f"相关度: {c.similarity:.2f}\n"
            f"{c.content}"
        )

    rag_prefix = RAG_SYSTEM_PREFIX + "\n\n---\n\n".join(context_parts)
    return citations, rag_prefix
