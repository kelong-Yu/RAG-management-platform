"""
Files API — 统一文件上传、列表、删除、原始内容获取。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentListResponse, AttachmentResponse
from app.services.file_service import (
    cleanup_orphan_files,
    delete_attachment,
    get_user_attachments,
    save_upload,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=AttachmentResponse)
def upload_file(
    file: UploadFile = File(...),
    source_type: str = Form("upload"),
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """上传文件（图片或 PDF）。"""
    try:
        attachment = save_upload(file, user_id, db, source_type=source_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("", response_model=AttachmentListResponse)
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """获取当前用户的附件列表。"""
    items, total = get_user_attachments(user_id, db, page=page, page_size=page_size)
    return AttachmentListResponse(
        items=[AttachmentResponse.model_validate(item) for item in items],
        total=total,
    )


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """删除附件（同时删除磁盘文件）。"""
    try:
        delete_attachment(file_id, user_id, db)
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    db.commit()
    return {"message": "已删除"}


@router.get("/{file_id}/raw")
def get_file_raw(
    file_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取文件原始内容（用于图片预览等）。

    返回带正确 Content-Type 的文件内容，前端可用作 blob URL 或直接 src 引用。
    通过 JWT Bearer token 鉴权，确保只有文件所有者可访问。
    """
    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == file_id, Attachment.user_id == user_id)
        .first()
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在或无权访问",
        )

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已从磁盘删除",
        )

    return FileResponse(
        file_path,
        media_type=attachment.mime_type,
        filename=attachment.file_name,
    )


@router.post("/cleanup")
def cleanup_files(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员清理孤立文件和过期失败附件。

    注意：当前版本允许任何登录用户触发清理，
    后续可增加管理员权限校验。
    """
    result = cleanup_orphan_files(db)
    db.commit()
    return result
