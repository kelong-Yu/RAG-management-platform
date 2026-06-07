"""
Document Service — PDF 文本提取、chunk 切分、文档处理状态编排。

处理流程：uploaded → parsing → chunking → embedding → ready / failed
"""

import hashlib
import logging
import re
from pathlib import Path

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.models.attachment import Attachment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User

logger = logging.getLogger(__name__)

# ── chunk 切分配置 ─────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 1000  # 每个 chunk 最多包含的字符数
DEFAULT_CHUNK_OVERLAP = 200  # 相邻 chunk 重叠字符数
DEFAULT_KNOWLEDGE_BASE_FILE = PROJECT_ROOT / "Default-know-base.md"
DEFAULT_KNOWLEDGE_BASE_SOURCE = "default-knowledge-base"
DEFAULT_KNOWLEDGE_BASE_SCHEMA_VERSION = "v2-structured-rag"
HTML_TABLE_BLOCK_RE = re.compile(r"(?is)<html\b[\s\S]*?</html>|<table\b[\s\S]*?</table>")
MARKDOWN_TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$"
)


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
    将按页提取的文本切分成语义 chunk，保留页码信息。

    切分策略：
    1. 先按标题、段落、列表项、句子边界形成语义片段
    2. 将相邻语义片段合并到目标 chunk_size 内
    3. 段落过长时再按句子/长度拆分
    4. 相邻 chunk 保留 chunk_overlap 字符重叠，提升召回连续性

    返回:
        list[dict]: [{"chunk_index": 0, "page_number": 1, "content": "..."}, ...]
    """
    chunks: list[dict] = []
    chunk_index = 0

    for page in pages:
        page_num = page["page_number"]
        for content in _semantic_chunk_text(
            page["text"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ):
            chunks.append({
                "chunk_index": chunk_index,
                "page_number": page_num,
                "content": content,
            })
            chunk_index += 1

    return chunks


def _semantic_chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """按语义边界切分文本，适配 PDF 提取文本和 Markdown 文档。"""
    normalized = _normalize_text(text)
    if not normalized:
        return []

    units = _split_semantic_units(normalized, chunk_size)
    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = unit

    if current:
        chunks.append(current)

    if chunk_overlap <= 0 or len(chunks) <= 1:
        return chunks

    overlapped: list[str] = []
    previous_tail = ""
    for chunk in chunks:
        merged = f"{previous_tail}\n\n{chunk}".strip() if previous_tail else chunk
        overlapped.append(merged[: chunk_size + chunk_overlap].strip())
        previous_tail = chunk[-chunk_overlap:].strip()

    return overlapped


def _normalize_text(text: str) -> str:
    """统一换行和空白，尽量保留 Markdown 标题/列表结构。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _split_semantic_units(text: str, chunk_size: int) -> list[str]:
    """将文本拆成可合并的语义单元。"""
    blocks = _split_structured_blocks(text)
    units: list[str] = []

    for block in blocks:
        if _is_structured_block(block):
            units.append(block)
            continue

        if len(block) <= chunk_size:
            units.append(block)
            continue

        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) > 1:
            buffer = ""
            for line in lines:
                candidate = f"{buffer}\n{line}".strip() if buffer else line
                if len(candidate) <= chunk_size:
                    buffer = candidate
                else:
                    if buffer:
                        units.extend(_split_long_text(buffer, chunk_size))
                    buffer = line
            if buffer:
                units.extend(_split_long_text(buffer, chunk_size))
            continue

        units.extend(_split_long_text(block, chunk_size))

    return units


def _split_structured_blocks(text: str) -> list[str]:
    """按段落拆分文本，同时保护 HTML/Markdown 表格块不被破坏。"""
    blocks: list[str] = []
    cursor = 0

    for match in HTML_TABLE_BLOCK_RE.finditer(text):
        before = text[cursor:match.start()]
        blocks.extend(_split_plain_blocks(before))
        html_block = match.group(0).strip()
        if html_block:
            blocks.append(html_block)
        cursor = match.end()

    blocks.extend(_split_plain_blocks(text[cursor:]))
    return [block for block in blocks if block.strip()]


def _split_plain_blocks(text: str) -> list[str]:
    """拆分普通文本块，并将 Markdown 表格视作单独结构块。"""
    if not text.strip():
        return []

    blocks: list[str] = []
    current_lines: list[str] = []
    lines = text.split("\n")
    index = 0

    def flush_current() -> None:
        if current_lines:
            block = "\n".join(current_lines).strip()
            if block:
                blocks.append(block)
            current_lines.clear()

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            flush_current()
            index += 1
            continue

        if _looks_like_markdown_table(lines, index):
            flush_current()
            table_lines = [lines[index].rstrip(), lines[index + 1].rstrip()]
            index += 2
            while index < len(lines):
                current = lines[index]
                if not current.strip():
                    break
                if "|" not in current:
                    break
                table_lines.append(current.rstrip())
                index += 1
            blocks.append("\n".join(table_lines).strip())
            continue

        current_lines.append(line.rstrip())
        index += 1

    flush_current()
    return blocks


def _looks_like_markdown_table(lines: list[str], index: int) -> bool:
    """判断从当前行开始是否为 Markdown 表格。"""
    if index + 1 >= len(lines):
        return False

    header = lines[index].strip()
    separator = lines[index + 1].strip()
    if "|" not in header:
        return False
    return bool(MARKDOWN_TABLE_SEPARATOR_RE.match(separator))


def _is_markdown_table_block(block: str) -> bool:
    """判断整块文本是否为 Markdown 表格。"""
    lines = [line.strip() for line in block.split("\n") if line.strip()]
    if len(lines) < 2:
        return False
    if "|" not in lines[0]:
        return False
    return bool(MARKDOWN_TABLE_SEPARATOR_RE.match(lines[1]))


def _is_structured_block(block: str) -> bool:
    """判断是否为需要整体保留的结构化块。"""
    stripped = block.strip()
    return bool(HTML_TABLE_BLOCK_RE.fullmatch(stripped)) or _is_markdown_table_block(
        stripped
    )


def _split_long_text(text: str, chunk_size: int) -> list[str]:
    """对超长语义单元做句子优先切分。"""
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    units: list[str] = []
    buffer = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = f"{buffer} {part}".strip() if buffer else part
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            if buffer:
                units.append(buffer)
            while len(part) > chunk_size:
                split_at = _find_split_point(part, chunk_size)
                units.append(part[:split_at].strip())
                part = part[split_at:].strip()
            buffer = part

    if buffer:
        units.append(buffer)
    return units


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
        is_system=False,
        is_deletable=True,
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
    """获取当前用户可访问的文档列表（含系统默认知识库）。"""
    query = db.query(Document).filter(
        or_(Document.user_id == user_id, Document.is_system.is_(True))
    )

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


def get_chunk_counts(document_ids: list[int], db: Session) -> dict[int, int]:
    """批量获取文档切片数量，避免列表接口逐条查询。"""
    if not document_ids:
        return {}

    rows = (
        db.query(
            DocumentChunk.document_id,
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .filter(DocumentChunk.document_id.in_(document_ids))
        .group_by(DocumentChunk.document_id)
        .all()
    )

    return {row.document_id: row.chunk_count for row in rows}


def delete_document(document_id: int, user_id: int, db: Session) -> None:
    """
    删除文档及其关联的所有 chunks。
    注意：不会删除关联的附件（附件由独立的文件管理流程处理）。
    """
    document = _get_document_with_check(document_id, user_id, db)
    if document.is_system or not document.is_deletable:
        raise PermissionError("系统内置知识库文件禁止删除，只能查看详情")

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
    if document.user_id != user_id and not document.is_system:
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


async def _embed_chunks(document_id: int, db: Session) -> None:
    """异步为文档的所有未向量化 chunk 生成 embedding。"""
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

    embeddings = await generate_embeddings(texts)

    # 将向量写回各 chunk
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    db.flush()
    logger.info(
        "Document %d: generated embeddings for %d chunks", document_id, len(chunks)
    )


def _embed_chunks_sync(document_id: int, db: Session) -> None:
    """同步包装器：为文档的所有未向量化 chunk 生成 embedding。"""
    import asyncio

    asyncio.run(_embed_chunks(document_id, db))


# ── 系统默认知识库 ───────────────────────────────────────────────────────


def _prepare_default_knowledge_base(
    admin_user_id: int, db: Session
) -> tuple[Document | None, list[str]]:
    """准备默认知识库文档及其切片文本。"""
    path = DEFAULT_KNOWLEDGE_BASE_FILE
    if not path.exists():
        logger.warning("Default knowledge base file not found: %s", path)
        return None, []

    content = path.read_text(encoding="utf-8")
    versioned_content = f"{DEFAULT_KNOWLEDGE_BASE_SCHEMA_VERSION}\n{content}"
    source_hash = hashlib.sha256(versioned_content.encode("utf-8")).hexdigest()

    document = (
        db.query(Document)
        .filter(Document.source_name == DEFAULT_KNOWLEDGE_BASE_SOURCE)
        .first()
    )
    if document and document.source_hash == source_hash:
        has_pending_embeddings = (
            db.query(DocumentChunk.id)
            .filter(
                DocumentChunk.document_id == document.id,
                DocumentChunk.embedding.is_(None),
            )
            .first()
            is not None
        )
        if (
            document.status == "ready"
            and not document.error_message
            and not has_pending_embeddings
        ):
            return document, []

    if document is None:
        document = Document(
            user_id=admin_user_id,
            attachment_id=None,
            name=path.name,
            doc_type="md",
            status="chunking",
            is_system=True,
            is_deletable=False,
            source_name=DEFAULT_KNOWLEDGE_BASE_SOURCE,
            source_hash=source_hash,
        )
        db.add(document)
        db.flush()
    else:
        document.user_id = admin_user_id
        document.name = path.name
        document.doc_type = "md"
        document.status = "chunking"
        document.error_message = None
        document.is_system = True
        document.is_deletable = False
        document.source_hash = source_hash
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).delete()
        db.flush()

    chunks = _semantic_chunk_text(content)
    for index, chunk_content in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                page_number=None,
                content=chunk_content,
            )
        )

    db.flush()
    document.status = "embedding"
    db.flush()
    return document, chunks


def _finalize_default_knowledge_base(
    document: Document,
    chunks: list[str],
    db: Session,
) -> Document:
    """提交默认知识库的最终状态。"""
    document.status = "ready"
    db.commit()
    db.refresh(document)
    logger.info(
        "Default knowledge base ready: document=%d chunks=%d",
        document.id,
        len(chunks),
    )
    return document


def ensure_default_knowledge_base(admin_user_id: int, db: Session) -> Document | None:
    """将 backend/Default-know-base.md 导入为系统内置知识库。

    该文档对所有用户可见，可参与检索，但不可被用户删除。
    若源文件内容发生变化，会重建切片并重新尝试 embedding。
    """
    document, chunks = _prepare_default_knowledge_base(admin_user_id, db)
    if document is None or not chunks:
        return document

    try:
        _embed_chunks_sync(document.id, db)
    except Exception as embed_err:
        logger.warning(
            "Default knowledge base embedding skipped: %s", embed_err
        )
        document.error_message = f"Embedding 失败，已保留关键词检索能力: {embed_err}"

    return _finalize_default_knowledge_base(document, chunks, db)


async def ensure_default_knowledge_base_async(
    admin_user_id: int, db: Session
) -> Document | None:
    """异步同步默认知识库，避免在已运行的事件循环中再次启动 loop。"""
    document, chunks = _prepare_default_knowledge_base(admin_user_id, db)
    if document is None or not chunks:
        return document

    try:
        await _embed_chunks(document.id, db)
    except Exception as embed_err:
        logger.warning(
            "Default knowledge base embedding skipped: %s", embed_err
        )
        document.error_message = f"Embedding 失败，已保留关键词检索能力: {embed_err}"

    return _finalize_default_knowledge_base(document, chunks, db)


def get_all_documents(
    db: Session,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[tuple[Document, str | None]], int]:
    """管理员获取所有知识库文档及拥有者用户名。"""
    query = db.query(Document, User.username).join(User, User.id == Document.user_id)
    total = query.count()
    rows = (
        query.order_by(Document.is_system.desc(), Document.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def delete_document_by_admin(document_id: int, db: Session) -> None:
    """管理员删除知识库文档，系统内置知识库仍禁止删除。"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise LookupError("文档不存在")
    if document.is_system or not document.is_deletable:
        raise PermissionError("系统内置知识库文件禁止删除，只能查看详情")
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.delete(document)
    db.commit()
