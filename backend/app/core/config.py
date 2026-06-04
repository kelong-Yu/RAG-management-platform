"""
应用核心配置 — 集中管理所有环境变量与默认值。
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# .env 位于 app/.env（相对于本项目结构）
# config.py -> app/core/config.py, so .parent.parent = app/
APP_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = APP_DIR / ".env"

# 项目根目录（backend/），即 app/ 的父目录
PROJECT_ROOT = APP_DIR.parent


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI Chat"
    DEBUG: bool = True

    # 数据库（默认值与 docker-compose.yml 保持一致）
    DATABASE_URL: str = "postgresql://admin:admin@localhost:5432/aichat"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # ============================================================
    # 上传配置
    # ============================================================
    UPLOAD_DIR: str = str(PROJECT_ROOT / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_IMAGE_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    ]
    ALLOWED_DOCUMENT_MIME_TYPES: list[str] = [
        "application/pdf",
    ]

    # LLM API
    DASH_SCOPE_API_KEY: str = ""
    DASH_SCOPE_API_BASE: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = ""
    TAVILY_API_KEY: str = ""

    # Embedding
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = ""
    EMBEDDING_MODEL: str = "text-embedding-v2"

    model_config = {
        "env_file": str(ENV_PATH),
        "case_sensitive": True,
        "extra": "ignore",  # 允许 .env 中有未定义的键
    }


settings = Settings()
