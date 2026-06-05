"""
File Storage Service — 统一文件存储，含校验、清洗、落盘、元数据管理。

所有文件操作都经过此 service，不在 router 中直接操作磁盘。
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment

logger = logging.getLogger(__name__)

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
_ALLOWED_SOURCE_TYPES = {"upload", "chat", "import"}


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


def save_upload(
    file: UploadFile,
    user_id: int,
    db: Session,
    source_type: str = "upload",
) -> Attachment:
    """
    保存上传文件：校验 → 清洗文件名 → 写磁盘 → 创建 Attachment 记录。

    返回创建的 Attachment ORM 对象（已 flush，含 id）。
    """
    _validate_file(file)
    if source_type not in _ALLOWED_SOURCE_TYPES:
        raise ValueError(f"不支持的附件来源类型: {source_type}")

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
        source_type=source_type,
        status="uploaded",
    )
    db.add(attachment)
    db.flush()  # 获取 id，但不提交（由 router 层统一 commit）

    logger.info(
        "File uploaded: user=%d id=%d name=%s size=%d mime=%s",
        user_id, attachment.id, safe_name, actual_size,
        attachment.mime_type,
    )

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
        logger.info("File deleted from disk: user=%d id=%d path=%s",
                     user_id, attachment_id, attachment.file_path)

    # 删除 DB 记录
    db.delete(attachment)
    logger.info("Attachment record deleted: user=%d id=%d", user_id, attachment_id)


def cleanup_orphan_files(db: Session) -> dict:
    """
    清理磁盘上未被任何 Attachment 记录引用的孤立文件。

    遍历上传目录中的所有文件，检查是否有对应的数据库记录。
    孤立文件会被删除。同时清理已标记为 failed 且超过保留期的附件。

    Returns:
        {"orphan_files_removed": int, "failed_records_removed": int, "freed_bytes": int}
    """
    import time as _time

    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.exists():
        return {"orphan_files_removed": 0, "failed_records_removed": 0, "freed_bytes": 0}

    # 1. 清理磁盘孤立文件
    all_stored_names = set(
        row[0] for row in db.query(Attachment.stored_name).all()
    )
    orphan_removed = 0
    freed_bytes = 0

    for file_path in upload_dir.iterdir():
        if file_path.is_file() and file_path.name not in all_stored_names:
            try:
                size = file_path.stat().st_size
                file_path.unlink()
                orphan_removed += 1
                freed_bytes += size
                logger.info("Cleaned orphan file: %s (%d bytes)", file_path.name, size)
            except OSError as e:
                logger.warning("Failed to remove orphan file %s: %s", file_path.name, e)

    # 2. 清理 7 天前的 failed 附件记录及其磁盘文件
    cutoff = _time.time() - 7 * 24 * 3600
    failed_removed = 0
    old_failed = (
        db.query(Attachment)
        .filter(
            Attachment.status == "failed",
            Attachment.created_at.isnot(None),
        )
        .all()
    )

    for att in old_failed:
        created_ts = att.created_at.timestamp() if att.created_at else 0
        if created_ts < cutoff:
            file_path = Path(att.file_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    freed_bytes += file_path.stat().st_size
                except OSError as e:
                    logger.warning("Failed to remove failed file %s: %s", att.file_path, e)
            db.delete(att)
            failed_removed += 1
            logger.info("Cleaned failed attachment: id=%d user=%d", att.id, att.user_id)

    if orphan_removed > 0 or failed_removed > 0:
        logger.info(
            "Cleanup complete: orphan_files=%d failed_records=%d freed_bytes=%d",
            orphan_removed, failed_removed, freed_bytes,
        )

    return {
        "orphan_files_removed": orphan_removed,
        "failed_records_removed": failed_removed,
        "freed_bytes": freed_bytes,
    }
