"""
DocumentChunk 数据模型 — 文档切片，保留页码、顺序和原始内容及向量。
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属文档 ID",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="切片顺序索引（从 0 开始）"
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="起始页码（1-based，PDF 原文页码）"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="切片文本内容")
    embedding = mapped_column(
        Vector(1536), nullable=True, comment="文本向量（DashScope text-embedding-v2）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
