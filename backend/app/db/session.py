"""
数据库会话 — SQLAlchemy engine & session 工厂（后续实现）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM 模型基类"""
    pass


def get_db():
    """FastAPI 依赖 — 为每个请求提供独立数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
