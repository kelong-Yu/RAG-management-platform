"""
用户相关接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/")
async def list_users(db: Session = Depends(get_db)):
    """测试接口 — 查询所有用户，验证数据库连接。"""
    from app.models.user import User

    users = db.query(User).all()
    return {"users": users, "count": len(users)}


@router.get("/db-check")
async def db_check(db: Session = Depends(get_db)):
    """数据库连接检查 — 执行 SELECT 1 验证连通性。"""
    result = db.execute(text("SELECT 1"))
    return {"status": "ok", "db_alive": result.scalar() == 1}
