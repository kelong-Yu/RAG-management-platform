"""
认证接口 — 注册 / 登录。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserCreate, UserLogin
from app.services.user_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(payload: UserCreate, db: Session = Depends(get_db)):
    register_user(db, payload)
    return {"message": "register success"}


@router.post("/login")
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    return authenticate_user(db, payload)
