"""
Retriever Service — 基于 pgvector + 关键词的混合检索。

检索流程：
1. 尝试将用户问题向量化并做语义检索
2. 同步做关键词候选召回
3. 融合语义分、关键词分、短语命中、标题命中和 chunk 顺序做 rerank
4. 只检索当前用户文档 + 系统默认知识库
5. 返回 top-K chunks 并附带文档元数据
"""

import logging
import re
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, or_, text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.3
LEXICAL_CANDIDATE_LIMIT = 50


@dataclass
class Citation:
    """检索结果中的引用信息。"""

    chunk_id: int
    document_id: int
    document_name: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity: float


async def retrieve(
    query: str,
    user_id: int,
    db: Session,
    top_k: int = DEFAULT_TOP_K,
) -> list[Citation]:
    """根据用户问题混合检索最相关的文档切片。"""
    semantic_hits = await _semantic_search(query, user_id, db, top_k * 3)
    lexical_hits = _lexical_search(query, user_id, db, LEXICAL_CANDIDATE_LIMIT)
    citations = _rerank(query, semantic_hits, lexical_hits, top_k)

    logger.info(
        "Hybrid retrieval: query='%s...', user=%d, semantic=%d, lexical=%d, hits=%d/%d",
        query[:60],
        user_id,
        len(semantic_hits),
        len(lexical_hits),
        len(citations),
        top_k,
    )
    return citations


async def _semantic_search(
    query: str,
    user_id: int,
    db: Session,
    limit: int,
) -> list[Citation]:
    """pgvector 语义召回。Embedding 未配置时返回空列表，由关键词检索兜底。"""
    try:
        query_embedding = await generate_embedding(query)
    except Exception as e:
        logger.warning("Semantic retrieval skipped: %s", e)
        return []

    sql = text("""
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            d.name AS document_name,
            dc.chunk_index,
            dc.page_number,
            dc.content,
            1 - (dc.embedding <=> :embedding) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE (d.user_id = :user_id OR d.is_system = true)
          AND d.status = 'ready'
          AND dc.embedding IS NOT NULL
          AND 1 - (dc.embedding <=> :embedding) > :threshold
        ORDER BY dc.embedding <=> :embedding
        LIMIT :limit
    """).bindparams(bindparam("embedding", type_=Vector(1536)))

    result = db.execute(
        sql,
        {
            "embedding": query_embedding,
            "user_id": user_id,
            "threshold": SIMILARITY_THRESHOLD,
            "limit": limit,
        },
    )

    return [
        Citation(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_name=row.document_name,
            chunk_index=row.chunk_index,
            page_number=row.page_number,
            content=row.content,
            similarity=round(row.similarity, 4),
        )
        for row in result
    ]


def _lexical_search(
    query: str,
    user_id: int,
    db: Session,
    limit: int,
) -> list[Citation]:
    """关键词召回，作为向量检索的兜底和补充。"""
    terms = _query_terms(query)
    if not terms:
        return []

    filters = [DocumentChunk.content.ilike(f"%{term}%") for term in terms[:8]]
    rows = (
        db.query(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(
            or_(Document.user_id == user_id, Document.is_system.is_(True)),
            Document.status == "ready",
            or_(*filters),
        )
        .order_by(Document.is_system.desc(), Document.updated_at.desc())
        .limit(limit)
        .all()
    )

    citations: list[Citation] = []
    for chunk, document in rows:
        score = _lexical_score(query, terms, document.name, chunk.content)
        if score <= 0:
            continue
        citations.append(
            Citation(
                chunk_id=chunk.id,
                document_id=document.id,
                document_name=document.name,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                similarity=round(score, 4),
            )
        )
    return citations


def _rerank(
    query: str,
    semantic_hits: list[Citation],
    lexical_hits: list[Citation],
    top_k: int,
) -> list[Citation]:
    """融合语义和关键词候选，并做轻量 rerank。"""
    terms = _query_terms(query)
    merged: dict[int, Citation] = {}
    semantic_scores: dict[int, float] = {}
    lexical_scores: dict[int, float] = {}

    for hit in semantic_hits:
        merged[hit.chunk_id] = hit
        semantic_scores[hit.chunk_id] = max(
            semantic_scores.get(hit.chunk_id, 0.0),
            hit.similarity,
        )
    for hit in lexical_hits:
        merged.setdefault(hit.chunk_id, hit)
        lexical_scores[hit.chunk_id] = max(
            lexical_scores.get(hit.chunk_id, 0.0),
            hit.similarity,
        )

    scored: list[tuple[float, Citation]] = []
    normalized_query = query.strip().lower()
    for chunk_id, hit in merged.items():
        semantic = semantic_scores.get(chunk_id, 0.0)
        lexical = lexical_scores.get(chunk_id, 0.0)
        content_lower = hit.content.lower()
        phrase_boost = 0.12 if normalized_query and normalized_query in content_lower else 0.0
        title_boost = 0.08 if any(term in hit.document_name.lower() for term in terms) else 0.0
        position_boost = max(0.0, 0.05 - hit.chunk_index * 0.002)
        hybrid_score = (
            semantic * 0.65
            + lexical * 0.35
            + phrase_boost
            + title_boost
            + position_boost
        )
        hit.similarity = round(min(hybrid_score, 1.0), 4)
        scored.append((hybrid_score, hit))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [hit for _, hit in scored[:top_k]]


def _query_terms(query: str) -> list[str]:
    """提取中英文关键词，保序去重。"""
    lowered = query.lower()
    terms = re.findall(r"[a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", lowered)
    if not terms and lowered.strip():
        terms = [lowered.strip()]

    seen: set[str] = set()
    result: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            result.append(term)
    return result


def _lexical_score(
    query: str,
    terms: list[str],
    document_name: str,
    content: str,
) -> float:
    """计算关键词分数，归一化到 0-1。"""
    lowered_content = content.lower()
    lowered_name = document_name.lower()
    if not terms:
        return 0.0

    hits = sum(1 for term in terms if term in lowered_content)
    frequency = sum(lowered_content.count(term) for term in terms)
    title_hits = sum(1 for term in terms if term in lowered_name)
    phrase_hit = 1 if query.strip().lower() in lowered_content else 0

    score = (
        hits / len(terms) * 0.55
        + min(frequency, 8) / 8 * 0.2
        + min(title_hits, 2) / 2 * 0.15
        + phrase_hit * 0.1
    )
    return min(score, 1.0)
