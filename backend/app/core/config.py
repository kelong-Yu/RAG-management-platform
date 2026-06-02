"""
应用核心配置 — 集中管理所有环境变量与默认值。
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI Chat"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_chat"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
