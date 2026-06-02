"""
API 路由汇总 — 注册所有子路由。
"""

from fastapi import APIRouter

from app.api.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
