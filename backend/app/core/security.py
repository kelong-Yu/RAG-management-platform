"""
密码加密与 JWT 工具 — 基于 bcrypt 的哈希与校验，以及 JWT 令牌的创建与验证。
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回字符串。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict) -> str:
    """创建 JWT 访问令牌。

    Args:
        data: 要编码到令牌中的 payload 数据（如 {"sub": user_id}）。

    Returns:
        JWT 字符串。
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str) -> dict | None:
    """验证 JWT 令牌。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 payload 字典；验证失败（过期、签名不匹配等）返回 None。
    """
    try:
        payload: dict = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
