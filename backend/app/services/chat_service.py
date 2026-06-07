"""
聊天服务 — 编排用户消息到 LLM 的完整流程，含会话持久化、RAG、图片附件。
"""

import json
import re
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
RAG_SYSTEM_PREFIX = """你是一个严格依据知识库回答的助手。请仅根据以下从知识库中检索到的文档片段回答用户问题。

要求：
1. 只能依据提供的文档片段回答，不要使用你自己的知识补充
2. 如果文档片段不足以回答问题，直接回答：知识库中未检索到相关内容
3. 回答中引用具体文档时，使用 [来源: 文档名] 的格式标注
4. 不要编造文档中不存在的信息
5. 如果文档片段中包含 HTML 表格（如 <table>、<tr>、<td>），优先原样保留并输出完整表格，不要改写成普通段落
6. 如果文档片段中包含 LaTeX 公式或剂量写法（如 $150\\mathrm{mg}$、$300\\mathrm{mg}$），必须原样保留，不要删掉美元符、反斜杠或公式命令
7. 涉及规格、剂量、表格数据时，优先直接引用原文结构化内容，再补充必要说明

--- 检索到的文档片段 ---

"""

RAG_NO_HIT_ANSWER = "知识库中未检索到相关内容。"
STRUCTURED_QUERY_TERMS = (
    "剂量",
    "用法",
    "用量",
    "规格",
    "给药",
    "治疗",
    "方案",
    "表",
    "数据",
    "疗效",
    "mg",
    "pasi",
    "trtd",
)


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
        if not rag_prefix:
            answer = RAG_NO_HIT_ANSWER
            save_message(db, conv_id, "assistant", answer)
            return answer, conv_id, citations, image_meta
        history.insert(0, {"role": "system", "content": rag_prefix})

    # 6. 调用 LLM（视觉 vs 纯文本）
    if is_vision_capable() and image_paths:
        answer = await chat_with_multimodal_context(history, image_paths)
    else:
        answer = await chat_with_context(history)

    answer = _merge_answer_with_structured_citations(answer, message, citations)

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
        if not rag_prefix:
            full_answer = RAG_NO_HIT_ANSWER
            assistant_message = save_message(db, conv_id, "assistant", full_answer)
            yield full_answer
            yield f"__ASSISTANT_ID__:{assistant_message.id}"
            if image_meta:
                payload = {
                    "images": image_meta,
                    "vision_capable": is_vision_capable(),
                }
                yield f"__IMAGES__:{json.dumps(payload, ensure_ascii=False)}"
            yield f"__CONV_ID__:{conv_id}"
            return
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

    appendix = _build_structured_citation_appendix(message, citations)
    if appendix:
        suffix = f"\n\n---\n\n{appendix}"
        full_answer += suffix
        yield suffix

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
            "content": c.content,
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


def _citation_has_structured_content(citation: dict) -> bool:
    """判断引用是否包含应直接展示给用户的结构化内容。"""
    content = citation.get("content", "")
    if not content:
        return False

    lowered = content.lower()
    if "<table" in lowered or "<tr" in lowered or "<td" in lowered:
        return True
    if "\\mathrm" in content or "\\frac" in content or "\\times" in content:
        return True
    if re.search(r"\$[^$\n]+\$", content):
        return True
    if re.search(r"^\s*\|.+\|\s*$", content, flags=re.MULTILINE):
        return True
    return False


def _query_prefers_structured_answer(query: str) -> bool:
    """判断用户问题是否更适合直接展示结构化原文。"""
    normalized = query.lower()
    return any(term in normalized for term in STRUCTURED_QUERY_TERMS)


def _build_structured_citation_appendix(
    query: str,
    citations: list[dict],
) -> str:
    """根据结构化引用构造应直接展示在主回答中的原文片段。"""
    if not citations:
        return ""

    structured = [c for c in citations if _citation_has_structured_content(c)]
    if not structured:
        return ""

    if not _query_prefers_structured_answer(query):
        return ""

    blocks: list[str] = [
        "以下为知识库中直接命中的原始内容，请优先以这些表格和公式为准："
    ]

    for citation in structured[:2]:
        page_info = (
            f"第{citation['page_number']}页" if citation.get("page_number") else "未知页码"
        )
        blocks.append(
            f"[来源: {citation['document_name']}] ({page_info}, 片段 {citation['chunk_index']})"
        )
        blocks.append(citation.get("content", "").strip())

    return "\n\n".join(block for block in blocks if block)


def _merge_answer_with_structured_citations(
    answer: str,
    query: str,
    citations: list[dict],
) -> str:
    """将结构化命中内容直接并入主回答正文。"""
    appendix = _build_structured_citation_appendix(query, citations)
    if not appendix:
        return answer

    existing = answer or ""
    if appendix in existing:
        return existing
    return f"{existing.rstrip()}\n\n---\n\n{appendix}".strip()
