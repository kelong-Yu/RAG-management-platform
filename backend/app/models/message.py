"""
Message 数据模型 — 聊天消息。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # system / user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, comment="扩展元数据，例：{\"attachment_ids\": [1, 2]}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 反向关联
    conversation = relationship("Conversation", back_populates="messages")
