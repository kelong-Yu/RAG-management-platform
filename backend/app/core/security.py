"""
密码加密工具 — 基于 bcrypt 的哈希与校验。
"""

import bcrypt


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希，返回字符串。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
