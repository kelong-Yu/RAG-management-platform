"""
Document 数据模型 — 知识库文档（由 PDF 等附件解析而来）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    attachment_id: Mapped[int | None] = mapped_column(
        ForeignKey("attachments.id"),
        nullable=True,
        index=True,
        comment="关联的原始附件 ID",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="文档名称"
    )
    doc_type: Mapped[str] = mapped_column(
        String(31),
        nullable=False,
        default="pdf",
        comment="文档类型：pdf / txt / html",
    )
    status: Mapped[str] = mapped_column(
        String(31),
        nullable=False,
        default="uploaded",
        comment="处理状态：uploaded / parsing / chunking / ready / failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败原因"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
