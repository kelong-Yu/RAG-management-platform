"""
应用核心配置 — 集中管理所有环境变量与默认值。
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# .env 位于 app/.env（相对于本项目结构）
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI Chat"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_chat"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 小时

    # LLM API（后续实现）
    DASH_SCOPE_API_KEY: str = ""
    DASH_SCOPE_API_BASE: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = ""
    TAVILY_API_KEY: str = ""

    model_config = {
        "env_file": str(ENV_PATH),
        "case_sensitive": True,
        "extra": "ignore",  # 允许 .env 中有未定义的键
    }


settings = Settings()
