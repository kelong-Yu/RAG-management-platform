"""
User 请求/响应 Schema — Pydantic v2。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    """注册请求"""
    password: str


class UserResponse(UserBase):
    """对外响应（不含密码）"""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
