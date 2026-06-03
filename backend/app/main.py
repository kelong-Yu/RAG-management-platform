"""
FastAPI 应用入口。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

# 确保所有模型被导入，供 Alembic 和 create_all 发现
import app.models  # noqa: F401
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期。

    注意：正式表结构变更请使用 Alembic 迁移：
        cd backend && uv run alembic revision --autogenerate -m "描述"
        uv run alembic upgrade head

    create_all 仅作为开发阶段安全兜底，后续版本将移除。
    """
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
