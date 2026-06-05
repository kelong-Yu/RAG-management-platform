"""
FastAPI 应用入口。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings

# 确保所有模型被导入，供 Alembic 和 create_all 发现
import app.models  # noqa: F401
from app.db.session import Base, engine
from app.db.session import SessionLocal
from app.services.document_service import ensure_default_knowledge_base
from app.services.user_service import ensure_admin_user

# ── 日志配置 ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 抑制过于冗长的第三方库日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ── 限流中间件（简易内存版，生产环境建议换 Redis-based） ─────────────────

# 限流配置：时间窗口(秒) → 最大请求数
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/chat/": (60, 30),           # 聊天接口：60 秒内最多 30 次
    "/chat/stream": (60, 20),     # 流式聊天：60 秒内最多 20 次
    "/files/upload": (60, 30),    # 上传：60 秒内最多 30 次
    "/auth/login": (60, 10),      # 登录：60 秒内最多 10 次
    "/auth/register": (60, 5),    # 注册：60 秒内最多 5 次
}
_DEFAULT_RATE_LIMIT = (60, 100)  # 默认：60 秒内 100 次

# 简易滑动窗口存储: { "ip:path": [timestamp, ...] }
_rate_window: dict[str, list[float]] = {}
import time as _time


def _clean_rate_window():
    """清理过期的限流记录。"""
    now = _time.monotonic()
    expired_keys = []
    for key, timestamps in _rate_window.items():
        _rate_window[key] = [t for t in timestamps if now - t < 120]
        if not _rate_window[key]:
            expired_keys.append(key)
    for key in expired_keys:
        del _rate_window[key]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期。

    注意：正式表结构变更请使用 Alembic 迁移：
        cd backend && uv run alembic revision --autogenerate -m "描述"
        uv run alembic upgrade head

    create_all 仅作为开发阶段安全兜底，后续版本将移除。
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = ensure_admin_user(db)
        ensure_default_knowledge_base(admin.id, db)
    except Exception as e:
        logger.error("Startup seed failed: %s", e, exc_info=True)
    finally:
        db.close()
    logger.info("Application startup complete")
    yield
    logger.info("Application shutting down")


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


# ── 限流中间件 ────────────────────────────────────────────────────────────


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """简易限流中间件：基于 IP + 路径前缀的滑动窗口限流。"""
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # 匹配合适的限流规则
    window_sec, max_req = _DEFAULT_RATE_LIMIT
    for prefix, (ws, mr) in _RATE_LIMITS.items():
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            window_sec, max_req = ws, mr
            break

    key = f"{client_ip}:{path}"
    now = _time.monotonic()

    if key not in _rate_window:
        _rate_window[key] = []

    # 清理窗口外的旧记录
    _rate_window[key] = [t for t in _rate_window[key] if now - t < window_sec]

    if len(_rate_window[key]) >= max_req:
        logger.warning("Rate limit exceeded: ip=%s path=%s count=%d/%d",
                       client_ip, path, len(_rate_window[key]), max_req)
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"请求过于频繁，请 {window_sec} 秒后再试",
                "retry_after": window_sec,
            },
        )

    _rate_window[key].append(now)

    # 定期清理（每 500 次请求触发一次全量清理）
    if sum(len(v) for v in _rate_window.values()) % 500 == 0:
        _clean_rate_window()

    response = await call_next(request)
    return response


# 注册路由
app.include_router(api_router)
