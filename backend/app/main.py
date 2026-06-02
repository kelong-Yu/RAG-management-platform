"""
FastAPI 应用入口。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

# 确保所有模型在 create_all 前被导入
import app.models  # noqa: F401
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动时自动建表。"""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS — 开发阶段允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)
