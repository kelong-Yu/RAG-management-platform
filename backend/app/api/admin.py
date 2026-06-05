"""
Admin API — 用户管理、知识库管理和系统默认知识库同步。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import AdminDocumentListResponse, AdminDocumentResponse
from app.schemas.user import AdminUserResponse, AdminUserUpdate
from app.services.document_service import (
    delete_document_by_admin,
    ensure_default_knowledge_base,
    get_all_documents,
    get_chunk_counts,
)
from app.services.user_service import (
    delete_user_by_admin,
    list_users,
    update_user_by_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserResponse])
def admin_list_users(
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员查看用户列表。"""
    return [AdminUserResponse.model_validate(user) for user in list_users(db)]


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员更新用户角色和启用状态。"""
    try:
        user = update_user_by_admin(db, user_id, body, admin.id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AdminUserResponse.model_validate(user)


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员删除无业务数据的用户。已有业务数据的用户应禁用。"""
    try:
        delete_user_by_admin(db, user_id, admin.id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "已删除"}


@router.get("/documents", response_model=AdminDocumentListResponse)
def admin_list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员查看全部知识库文档。"""
    rows, total = get_all_documents(db, page=page, page_size=page_size)
    documents = [row[0] for row in rows]
    chunk_counts = get_chunk_counts([document.id for document in documents], db)

    return AdminDocumentListResponse(
        items=[
            AdminDocumentResponse(
                id=document.id,
                user_id=document.user_id,
                attachment_id=document.attachment_id,
                name=document.name,
                doc_type=document.doc_type,
                status=document.status,
                error_message=document.error_message,
                is_system=document.is_system,
                is_deletable=document.is_deletable,
                source_name=document.source_name,
                chunk_count=chunk_counts.get(document.id, 0),
                created_at=document.created_at,
                updated_at=document.updated_at,
                owner_username=username,
            )
            for document, username in rows
        ],
        total=total,
    )


@router.delete("/documents/{document_id}")
def admin_delete_document(
    document_id: int,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """管理员删除知识库文档；系统内置默认知识库禁止删除。"""
    try:
        delete_document_by_admin(document_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"message": "已删除"}


@router.post("/knowledge/default/sync", response_model=AdminDocumentResponse)
def admin_sync_default_knowledge_base(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """重新同步 backend/Default-know-base.md 到系统默认知识库。"""
    document = ensure_default_knowledge_base(admin.id, db)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="默认知识库文件不存在",
        )
    chunk_count = get_chunk_counts([document.id], db).get(document.id, 0)
    return AdminDocumentResponse(
        id=document.id,
        user_id=document.user_id,
        attachment_id=document.attachment_id,
        name=document.name,
        doc_type=document.doc_type,
        status=document.status,
        error_message=document.error_message,
        is_system=document.is_system,
        is_deletable=document.is_deletable,
        source_name=document.source_name,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        owner_username=admin.username,
    )
