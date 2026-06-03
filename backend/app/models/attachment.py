"""
Attachment 数据模型 — 统一附件（图片、PDF 等）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名"
    )
    stored_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="存储文件名（UUID 或 hash）"
    )
    file_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="文件相对/绝对路径"
    )
    mime_type: Mapped[str] = mapped_column(
        String(127), nullable=False, comment="MIME 类型"
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="文件大小（字节）"
    )
    source_type: Mapped[str] = mapped_column(
        String(31),
        nullable=False,
        default="upload",
        comment="来源类型：upload / chat / import",
    )
    status: Mapped[str] = mapped_column(
        String(31),
        nullable=False,
        default="uploaded",
        comment="附件状态：uploaded / processing / ready / failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
