"""
Document Service — PDF 文本提取、chunk 切分、文档处理状态编排。

处理流程：uploaded → parsing → chunking → embedding → ready / failed
"""

import asyncio
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

# ── chunk 切分配置 ─────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 1000  # 每个 chunk 最多包含的字符数
DEFAULT_CHUNK_OVERLAP = 200  # 相邻 chunk 重叠字符数


# ── 文本提取 ───────────────────────────────────────────────────────────


def _extract_text_from_pdf(file_path: str) -> list[dict]:
    """
    使用 pymupdf 从 PDF 中按页提取文本。

    返回:
        list[dict]: [{"page_number": 1, "text": "..."}, ...]

    Raises:
        ValueError: PDF 无法打开或文本提取失败
    """
    import fitz  # pymupdf

    pages: list[dict] = []

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"无法打开 PDF 文件: {e}") from e

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text()
            if text and text.strip():
                pages.append({
                    "page_number": page_index + 1,  # 1-based
                    "text": text.strip(),
                })
    finally:
        doc.close()

    if not pages:
        raise ValueError("PDF 文件中未提取到文本内容，可能为扫描件或空文件")

    return pages


# ── chunk 切分 ─────────────────────────────────────────────────────────


def _chunk_pages(
    pages: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    将按页提取的文本切分成 chunk，保留页码信息。

    切分策略：
    1. 在 chunk_size 内尽量按段落边界（双换行）切分
    2. 段落过长时按句子边界（单换行或句号）切分
    3. 仍过长时硬截断
    4. 相邻 chunk 保留 chunk_overlap 字符重叠

    返回:
        list[dict]: [{"chunk_index": 0, "page_number": 1, "content": "..."}, ...]
    """
    chunks: list[dict] = []
    chunk_index = 0
    carry = ""  # 跨页残留文本
    carry_page = 1

    for page in pages:
        page_num = page["page_number"]
        text = carry + page["text"]
        carry = ""
        carry_page = page_num

        while len(text) > chunk_size:
            # 在 chunk_size 范围内寻找最佳切分点
            split_at = _find_split_point(text, chunk_size)
            chunk_content = text[:split_at].strip()
            if chunk_content:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": carry_page,
                    "content": chunk_content,
                })
                chunk_index += 1

            # 下一段从 split_at 开始，减去 overlap
            text = text[max(split_at - chunk_overlap, 0):].strip()
            carry_page = page_num

        carry = text

    # 处理最后的残留文本
    if carry and carry.strip():
        chunks.append({
            "chunk_index": chunk_index,
            "page_number": carry_page,
            "content": carry.strip(),
        })

    return chunks


def _find_split_point(text: str, max_len: int) -> int:
    """
    在 text[:max_len] 范围内寻找最佳切分点。

    优先级：
    1. 最后一个双换行（段落边界）
    2. 最后一个换行（行边界）
    3. 最后一个句号/问号/感叹号（句子边界）
    4. 最后一个空格
    5. max_len 硬截断
    """
    if len(text) <= max_len:
        return len(text)

    search_range = text[:max_len]

    # 段落边界
    for sep in ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", " "]:
        pos = search_range.rfind(sep)
        if pos > max_len * 0.3:  # 不要太靠前，至少保留 30%
            return pos + len(sep)

    return max_len


# ── 文档处理编排 ───────────────────────────────────────────────────────


def create_document_from_attachment(
    attachment_id: int, user_id: int, db: Session
) -> Document:
    """
    从已上传的附件创建文档记录，状态为 uploaded。

    Raises:
        LookupError: 附件不存在或不属于当前用户
        ValueError: 附件不是 PDF
    """
    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id, Attachment.user_id == user_id)
        .first()
    )
    if attachment is None:
        raise LookupError("附件不存在或无权访问")

    if attachment.mime_type != "application/pdf":
        raise ValueError("仅支持从 PDF 附件创建文档")

    # 检查是否已有文档关联此附件（避免重复创建）
    existing = (
        db.query(Document)
        .filter(Document.attachment_id == attachment_id)
        .first()
    )
    if existing:
        return existing

    document = Document(
        user_id=user_id,
        attachment_id=attachment_id,
        name=attachment.file_name,
        doc_type="pdf",
        status="uploaded",
    )
    db.add(document)
    db.flush()
    logger.info("Document %d created from attachment %d", document.id, attachment_id)
    return document


def process_document(document_id: int, user_id: int, db: Session) -> Document:
    """
    处理文档：文本提取 → chunk 切分 → 保存 chunks → Embedding。

    状态流转：uploaded/parsing/chunking/embedding/ready → parsing → chunking → embedding → ready
    失败时：→ failed（记录 error_message）
    """
    document = _get_document_with_check(document_id, user_id, db)

    try:
        # ── 阶段 1: 文本提取 (parsing) ──
        _set_status(document, "parsing", db)
        logger.info("Document %d: starting text extraction", document.id)

        attachment = _get_attachment_for_document(document, db)
        pages = _extract_text_from_pdf(attachment.file_path)
        logger.info(
            "Document %d: extracted text from %d pages", document.id, len(pages)
        )

        # ── 阶段 2: chunk 切分 (chunking) ──
        _set_status(document, "chunking", db)
        logger.info("Document %d: starting chunking", document.id)

        # 清除旧 chunks（重试场景）
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).delete()

        chunks_data = _chunk_pages(pages)

        for data in chunks_data:
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=data["chunk_index"],
                page_number=data["page_number"],
                content=data["content"],
            )
            db.add(chunk)

        db.flush()
        logger.info(
            "Document %d: created %d chunks", document.id, len(chunks_data)
        )

        # ── 阶段 3: Embedding ──
        _set_status(document, "embedding", db)
        logger.info("Document %d: starting embedding generation", document.id)

        try:
            _embed_chunks_sync(document.id, db)
        except Exception as embed_err:
            logger.error(
                "Document %d: embedding failed - %s", document.id, embed_err
            )
            # Embedding 失败不阻断，chunk 数据仍可用，状态标记为 ready 但记录 warning
            document.error_message = f"Embedding 失败: {embed_err}"

        # ── 阶段 4: 完成 ──
        _set_status(document, "ready", db)
        logger.info("Document %d: processing complete", document.id)

    except Exception as e:
        logger.error("Document %d: processing failed - %s", document.id, e)
        _set_status(document, "failed", db)
        document.error_message = str(e)

    return document


# ── 文档查询 ───────────────────────────────────────────────────────────


def get_user_documents(
    user_id: int,
    db: Session,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Document], int]:
    """获取当前用户的文档列表（分页，按更新时间倒序）。"""
    query = db.query(Document).filter(Document.user_id == user_id)

    total = query.count()
    items = (
        query.order_by(Document.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return items, total


def get_document(document_id: int, user_id: int, db: Session) -> Document:
    """获取单个文档（含归属校验）。"""
    return _get_document_with_check(document_id, user_id, db)


def get_document_chunks(
    document_id: int, user_id: int, db: Session
) -> list[DocumentChunk]:
    """获取文档的所有切片（先校验文档归属）。"""
    _get_document_with_check(document_id, user_id, db)  # 归属校验

    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )


def get_chunk_count(document_id: int, db: Session) -> int:
    """获取文档的切片数量。"""
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .count()
    )


def delete_document(document_id: int, user_id: int, db: Session) -> None:
    """
    删除文档及其关联的所有 chunks。
    注意：不会删除关联的附件（附件由独立的文件管理流程处理）。
    """
    document = _get_document_with_check(document_id, user_id, db)

    # 删除 chunks（CASCADE 配置会确保 DB 级别也清理，这里显式删除）
    db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).delete()

    # 删除文档
    db.delete(document)
    logger.info("Document %d deleted", document_id)


# ── 内部辅助 ───────────────────────────────────────────────────────────


def _get_document_with_check(
    document_id: int, user_id: int, db: Session
) -> Document:
    """获取文档并校验归属。"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise LookupError("文档不存在")
    if document.user_id != user_id:
        raise LookupError("文档不存在或无权访问")
    return document


def _get_attachment_for_document(
    document: Document, db: Session
) -> Attachment:
    """获取文档关联的附件。"""
    if document.attachment_id is None:
        raise ValueError("文档未关联附件，无法处理")
    attachment = db.query(Attachment).filter(
        Attachment.id == document.attachment_id
    ).first()
    if attachment is None:
        raise ValueError("关联附件不存在")
    return attachment


def _set_status(document: Document, status: str, db: Session) -> None:
    """更新文档处理状态并立即 flush。"""
    document.status = status
    db.flush()


def _embed_chunks_sync(document_id: int, db: Session) -> None:
    """同步包装器：为文档的所有未向量化 chunk 生成 embedding。

    在独立的事件循环中运行 async embedding 调用。
    """
    from app.services.embedding_service import generate_embeddings

    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.embedding.is_(None),
        )
        .all()
    )

    if not chunks:
        logger.info("Document %d: no chunks need embedding", document_id)
        return

    # 提取文本
    texts = [c.content for c in chunks]

    # 在同步上下文中运行异步 embedding 生成
    loop = asyncio.new_event_loop()
    try:
        embeddings = loop.run_until_complete(generate_embeddings(texts))
    finally:
        loop.close()

    # 将向量写回各 chunk
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    db.flush()
    logger.info(
        "Document %d: generated embeddings for %d chunks", document_id, len(chunks)
    )
