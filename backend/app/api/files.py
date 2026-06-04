"""
Files API — 统一文件上传、列表、删除。
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.attachment import AttachmentListResponse, AttachmentResponse
from app.services.file_service import delete_attachment, get_user_attachments, save_upload

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=AttachmentResponse)
def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """上传文件（图片或 PDF）。"""
    try:
        attachment = save_upload(file, user_id, db)
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
