"""
数据模型 — 统一导入，确保 Base.metadata 能发现所有模型。
"""

from app.models.user import User

__all__ = ["User"]
