"""
聊天服务 — 编排用户消息到 LLM 的完整流程，含会话持久化和 RAG。
"""

import json
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
) -> tuple[str, int, list[dict]]:
    """非流式发送消息。

    Returns:
        (answer, conversation_id, citations)
    """
    citations: list[dict] = []

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

    # 4. 构建 LLM 上下文（含 RAG 增强）
    history = build_context_messages(db, conv_id, user_id)

    if use_rag:
        citations, rag_prefix = await _build_rag_prompt(message, user_id, db)
        if rag_prefix:
            # 将 RAG 上下文插入为 system message
            history.insert(0, {"role": "system", "content": rag_prefix})

    # 5. 调用 LLM
    answer = await chat_with_context(history)

    # 6. 保存助手消息
    save_message(db, conv_id, "assistant", answer)

    return answer, conv_id, citations


async def send_message_stream(
    db: Session,
    user_id: int,
    message: str,
    conversation_id: int | None = None,
    use_rag: bool = False,
) -> AsyncGenerator[str, None]:
    """流式发送消息，逐 Token 返回。

    Yields:
        每个文本 Token。完成时 yield 特殊标记：
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

    # 2. 保存用户消息
    save_message(db, conv_id, "user", message)

    # 3. 新会话自动生成标题
    if is_new:
        set_conversation_title_from_first_message(db, conv_id)

    # 4. 构建 LLM 上下文（含 RAG 增强）
    history = build_context_messages(db, conv_id, user_id)
    citations: list[dict] = []

    if use_rag:
        citations, rag_prefix = await _build_rag_prompt(message, user_id, db)
        if rag_prefix:
            history.insert(0, {"role": "system", "content": rag_prefix})

    # 5. 流式调用 LLM，同时累积完整回复
    full_answer = ""
    async for token in chat_stream_with_context(history):
        full_answer += token
        yield token

    # 6. 流结束后保存助手消息
    assistant_message = save_message(db, conv_id, "assistant", full_answer)

    # 7. 告知前端持久化后的 assistant message id，便于引用缓存复用
    yield f"__ASSISTANT_ID__:{assistant_message.id}"

    # 8. 发送引用数据
    if citations:
        yield f"__CITATIONS__:{json.dumps(citations, ensure_ascii=False)}"

    # 9. 告知前端 conversation_id（新的或用已有的）
    yield f"__CONV_ID__:{conv_id}"


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
