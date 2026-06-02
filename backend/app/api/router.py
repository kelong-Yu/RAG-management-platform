"""
API 路由汇总 — 注册所有子路由。
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.users import router as users_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(auth_router)
