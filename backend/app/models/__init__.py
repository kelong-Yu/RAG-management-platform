"""
数据模型 — 统一导入，确保 Base.metadata 能发现所有模型。
"""

from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.models.user import User

__all__ = ["User", "Conversation", "Message", "Attachment", "Document"]
