"""
Documents API — 文档管理、处理和切片查询。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentProcessRequest,
    DocumentResponse,
)
from app.services.document_service import (
    create_document_from_attachment,
    delete_document,
    get_chunk_count,
    get_chunk_counts,
    get_document,
    get_document_chunks,
    get_user_documents,
    process_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """从已有 PDF 附件创建文档，并自动触发处理流程。"""
    try:
        document = create_document_from_attachment(body.attachment_id, user_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    db.commit()

    # 异步触发处理（同步执行，但提交后处理以保证文档已持久化）
    try:
        document = process_document(document.id, user_id, db)
        db.commit()
    except Exception:
        db.rollback()
        # 处理失败不阻断创建流程，状态已在 process_document 中标记为 failed
        db.refresh(document)

    db.refresh(document)
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """获取当前用户的文档列表。"""
    items, total = get_user_documents(user_id, db, page=page, page_size=page_size)
    chunk_counts = get_chunk_counts([item.id for item in items], db)
    return DocumentListResponse(
        items=[
            DocumentResponse(
                id=item.id,
                user_id=item.user_id,
                attachment_id=item.attachment_id,
                name=item.name,
                doc_type=item.doc_type,
                status=item.status,
                error_message=item.error_message,
                chunk_count=chunk_counts.get(item.id, 0),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """获取文档详情（含切片数量）。"""
    try:
        document = get_document(document_id, user_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    chunk_count = get_chunk_count(document.id, db)
    return DocumentDetailResponse(
        id=document.id,
        user_id=document.user_id,
        attachment_id=document.attachment_id,
        name=document.name,
        doc_type=document.doc_type,
        status=document.status,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=chunk_count,
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def list_chunks(
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """获取文档的所有切片（按索引顺序）。"""
    try:
        chunks = get_document_chunks(document_id, user_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return DocumentChunkListResponse(
        items=[DocumentChunkResponse.model_validate(c) for c in chunks],
        total=len(chunks),
    )


@router.post("/{document_id}/process", response_model=DocumentResponse)
def reprocess_document(
    document_id: int,
    _body: DocumentProcessRequest | None = None,  # 保留扩展空间
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """重新处理文档（用于失败重试）。"""
    try:
        document = process_document(document_id, user_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}")
def remove_document(
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """删除文档及其所有切片（不删除原始附件）。"""
    try:
        delete_document(document_id, user_id, db)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    db.commit()
    return {"message": "已删除"}
