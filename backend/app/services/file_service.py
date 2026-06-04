"""
File Storage Service — 统一文件存储，含校验、清洗、落盘、元数据管理。

所有文件操作都经过此 service，不在 router 中直接操作磁盘。
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment

# 允许的扩展名 → MIME 类型映射
_ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
}

# 从配置派生的 MIME 白名单（合并图片 + 文档）
_ALLOWED_MIME_TYPES: set[str] = set(
    settings.ALLOWED_IMAGE_MIME_TYPES + settings.ALLOWED_DOCUMENT_MIME_TYPES
)


def _sanitize_filename(filename: str) -> str:
    """清洗文件名：去除路径分隔符和危险字符，保留安全的可见字符。"""
    # 分离文件名和扩展名
    stem, ext = os.path.splitext(filename)
    # 清理 stem：保留字母、数字、中文、下划线、连字符、点
    safe_chars: list[str] = []
    for ch in stem:
        if ch.isalnum() or ch in "._-()（）" or "一" <= ch <= "鿿":
            safe_chars.append(ch)
        else:
            safe_chars.append("_")
    clean_stem = "".join(safe_chars).strip("._- ")
    if not clean_stem:
        clean_stem = "file"
    return f"{clean_stem}{ext.lower()}"


def _validate_file(file: UploadFile) -> None:
    """校验上传文件：大小、MIME 类型、扩展名。"""
    # 1. 大小校验
    if file.size is None:
        raise ValueError("无法获取文件大小")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValueError(
            f"文件大小 {file.size / 1024 / 1024:.1f} MB 超过限制 "
            f"({settings.MAX_UPLOAD_SIZE_MB} MB)"
        )

    # 2. MIME 类型校验
    mime = (file.content_type or "").lower().strip()
    if mime not in _ALLOWED_MIME_TYPES:
        raise ValueError(f"不支持的文件类型: {file.content_type}")

    # 3. 扩展名校验
    if file.filename is None:
        raise ValueError("文件名为空")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件扩展名: {ext}")
    if mime not in _ALLOWED_EXTENSIONS[ext]:
        raise ValueError(f"扩展名 {ext} 与 MIME 类型 {mime} 不匹配")


def _ensure_upload_dir() -> Path:
    """确保上传目录存在，返回 Path 对象。"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_upload(file: UploadFile, user_id: int, db: Session) -> Attachment:
    """
    保存上传文件：校验 → 清洗文件名 → 写磁盘 → 创建 Attachment 记录。

    返回创建的 Attachment ORM 对象（已 flush，含 id）。
    """
    _validate_file(file)

    original_name = file.filename  # type: ignore[assignment] — _validate_file 已确保非 None
    safe_name = _sanitize_filename(original_name)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"

    upload_dir = _ensure_upload_dir()
    file_path = upload_dir / stored_name

    # 写入磁盘
    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    actual_size = file_path.stat().st_size

    attachment = Attachment(
        user_id=user_id,
        file_name=original_name,
        stored_name=stored_name,
        file_path=str(file_path),
        mime_type=(file.content_type or "application/octet-stream").lower(),
        file_size=actual_size,
        source_type="upload",
        status="uploaded",
    )
    db.add(attachment)
    db.flush()  # 获取 id，但不提交（由 router 层统一 commit）

    return attachment


def get_user_attachments(
    user_id: int,
    db: Session,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Attachment], int]:
    """获取当前用户的附件列表（分页）。"""
    query = db.query(Attachment).filter(Attachment.user_id == user_id)

    total = query.count()
    items = (
        query.order_by(Attachment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return items, total


def delete_attachment(attachment_id: int, user_id: int, db: Session) -> None:
    """
    删除附件：校验归属 → 删磁盘文件 → 删 DB 记录。

    Raises:
        LookupError: 附件不存在或不属于当前用户
    """
    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id, Attachment.user_id == user_id)
        .first()
    )
    if attachment is None:
        raise LookupError("附件不存在或无权访问")

    # 删除磁盘文件
    file_path = Path(attachment.file_path)
    if file_path.exists():
        file_path.unlink()

    # 删除 DB 记录
    db.delete(attachment)
