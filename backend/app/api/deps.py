"""
FastAPI 依赖注入 — JWT 认证等可复用依赖。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_token

security_scheme = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> int:
    """从请求头的 JWT 中解析当前用户 ID。

    用法：作为 FastAPI 路由的依赖注入，自动从 Authorization: Bearer <token>
    中提取并验证 JWT，返回当前登录用户的数据库 ID。
    """
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的认证令牌",
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户标识",
        )
    return int(user_id)
