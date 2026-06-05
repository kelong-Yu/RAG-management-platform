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


class UserLogin(BaseModel):
    """登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT 令牌响应"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(UserBase):
    """对外响应（不含密码）"""
    id: int
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(UserResponse):
    """管理员用户列表响应。"""

    pass


class AdminUserUpdate(BaseModel):
    """管理员更新用户状态。"""

    role: str | None = None
    is_active: bool | None = None
