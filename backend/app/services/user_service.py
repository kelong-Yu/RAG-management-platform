"""
用户服务 — 注册等业务逻辑。
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse


def register_user(db: Session, payload: UserCreate) -> UserResponse:
    """注册新用户。

    规则：
    1. 用户名 & 邮箱不能为空
    2. 用户名不能重复
    3. 邮箱不能重复
    4. 密码 bcrypt 加密存储
    """
    # 校验非空
    if not payload.username or not payload.username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名不能为空",
        )
    if not payload.email or not payload.email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱不能为空",
        )

    username = payload.username.strip()
    email = payload.email.strip()

    # 唯一性校验
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="邮箱已注册",
        )

    # 创建用户
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)
