"""
用户相关接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_current_user_id
from app.db.session import get_db
from app.schemas.user import AdminUserResponse
from app.services.user_service import get_user_by_id

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/")
async def list_users(
    _admin=Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """测试接口 — 查询所有用户，验证数据库连接。"""
    from app.models.user import User

    users = db.query(User).all()
    return {
        "users": [AdminUserResponse.model_validate(user) for user in users],
        "count": len(users),
    }


@router.get("/db-check")
async def db_check(db: Session = Depends(get_db)):
    """数据库连接检查 — 执行 SELECT 1 验证连通性。"""
    result = db.execute(text("SELECT 1"))
    return {"status": "ok", "db_alive": result.scalar() == 1}


@router.get("/me")
async def get_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取当前登录用户信息。"""
    return get_user_by_id(db, user_id)
