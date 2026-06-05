"""
用户服务 — 注册等业务逻辑。
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.attachment import Attachment
from app.models.conversation import Conversation
from app.models.document import Document
from app.schemas.user import (
    AdminUserUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
ADMIN_EMAIL = "admin@example.local"


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
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


def authenticate_user(db: Session, payload: UserLogin) -> TokenResponse:
    """用户登录认证。

    逻辑：
    1. 根据用户名查询用户
    2. 校验密码
    3. 生成 JWT
    4. 返回 token
    """
    # 1. 查询用户
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 2. 校验密码
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    # 3. 生成 JWT
    access_token = create_access_token(data={"sub": str(user.id)})

    # 4. 返回 token
    return TokenResponse(access_token=access_token)


def get_user_by_id(db: Session, user_id: int) -> UserResponse:
    """根据 ID 查询当前用户。

    Args:
        db: 数据库会话。
        user_id: 用户 ID（来自 JWT）。

    Returns:
        UserResponse 用户信息。

    Raises:
        HTTPException 404: 用户不存在。
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )
    return UserResponse.model_validate(user)


def ensure_admin_user(db: Session) -> User:
    """确保系统内置管理员账号存在。

    账号和密码均为 admin。若账号已存在，会强制保持管理员角色和启用状态。
    """
    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if user is None:
        user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    changed = False
    if user.role != "admin":
        user.role = "admin"
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if user.email != ADMIN_EMAIL:
        user.email = ADMIN_EMAIL
        changed = True
    if changed:
        db.commit()
        db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    """管理员获取用户列表。"""
    return db.query(User).order_by(User.created_at.desc()).all()


def update_user_by_admin(
    db: Session,
    target_user_id: int,
    payload: AdminUserUpdate,
    admin_user_id: int,
) -> User:
    """管理员更新用户角色或启用状态。"""
    user = db.query(User).filter(User.id == target_user_id).first()
    if user is None:
        raise LookupError("用户不存在")
    if user.id == admin_user_id and payload.is_active is False:
        raise ValueError("不能禁用当前管理员账号")

    if payload.role is not None:
        if payload.role not in {"user", "admin"}:
            raise ValueError("角色只能是 user 或 admin")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


def delete_user_by_admin(
    db: Session,
    target_user_id: int,
    admin_user_id: int,
) -> None:
    """管理员删除用户。内置 admin 和当前账号不可删除。"""
    user = db.query(User).filter(User.id == target_user_id).first()
    if user is None:
        raise LookupError("用户不存在")
    if user.username == ADMIN_USERNAME or user.id == admin_user_id:
        raise ValueError("不能删除内置管理员或当前登录账号")
    related_count = (
        db.query(Conversation).filter(Conversation.user_id == target_user_id).count()
        + db.query(Attachment).filter(Attachment.user_id == target_user_id).count()
        + db.query(Document).filter(Document.user_id == target_user_id).count()
    )
    if related_count > 0:
        raise ValueError("该用户已有业务数据，请先禁用账号而不是删除")
    db.delete(user)
    db.commit()
