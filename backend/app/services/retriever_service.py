"""
Retriever Service — 基于 pgvector 的语义检索，限定用户可访问的知识范围。

检索流程：
1. 将用户问题向量化
2. 在 document_chunks 中做余弦相似度搜索
3. 只检索当前用户的文档
4. 返回 top-K chunks 并附带文档元数据
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embedding_service import generate_embedding

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.3  # 低于此相似度的结果视为无命中


@dataclass
class Citation:
    """检索结果中的引用信息。"""

    chunk_id: int
    document_id: int
    document_name: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity: float  # 余弦相似度，1 为最相似


async def retrieve(
    query: str,
    user_id: int,
    db: Session,
    top_k: int = DEFAULT_TOP_K,
) -> list[Citation]:
    """
    根据用户问题检索最相关的文档切片。

    Args:
        query: 用户问题
        user_id: 当前用户 ID（限定知识范围）
        db: 数据库 session
        top_k: 返回最相似的结果数

    Returns:
        按相似度降序排列的引用列表，相似度低于阈值的结果会被过滤。
    """
    # 1. 生成问题向量
    query_embedding = await generate_embedding(query)

    # 2. pgvector 余弦相似度搜索（<=> 是 cosine distance）
    # 只检索当前用户文档的 chunks
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
        WHERE d.user_id = :user_id
          AND dc.embedding IS NOT NULL
          AND 1 - (dc.embedding <=> :embedding) > :threshold
        ORDER BY dc.embedding <=> :embedding
        LIMIT :top_k
    """)

    result = db.execute(
        sql,
        {
            "embedding": query_embedding,
            "user_id": user_id,
            "threshold": SIMILARITY_THRESHOLD,
            "top_k": top_k,
        },
    )

    citations: list[Citation] = []
    for row in result:
        citations.append(
            Citation(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_name=row.document_name,
                chunk_index=row.chunk_index,
                page_number=row.page_number,
                content=row.content,
                similarity=round(row.similarity, 4),
            )
        )

    logger.info(
        "Retrieval: query='%s...', user=%d, hits=%d/%d",
        query[:60],
        user_id,
        len(citations),
        top_k,
    )

    return citations
