/**
 * Documents API — 文档管理、处理、切片查询。
 */

import api from './auth'
import type {
  CreateDocumentRequest,
  Document,
  DocumentChunkListResponse,
  DocumentDetail,
  DocumentListResponse,
} from '@/types'

/** 从 PDF 附件创建文档并自动触发处理 */
export function createDocument(attachmentId: number) {
  return api.post<Document>('/documents', {
    attachment_id: attachmentId,
  } satisfies CreateDocumentRequest)
}

/** 获取文档列表 */
export function getDocuments(page = 1, pageSize = 50) {
  return api.get<DocumentListResponse>('/documents', {
    params: { page, page_size: pageSize },
  })
}

/** 获取文档详情 */
export function getDocumentDetail(id: number) {
  return api.get<DocumentDetail>(`/documents/${id}`)
}

/** 获取文档切片列表 */
export function getDocumentChunks(id: number) {
  return api.get<DocumentChunkListResponse>(`/documents/${id}/chunks`)
}

/** 重新处理文档（失败重试） */
export function reprocessDocument(id: number) {
  return api.post<Document>(`/documents/${id}/process`)
}

/** 删除文档及其切片 */
export function deleteDocument(id: number) {
  return api.delete<{ message: string }>(`/documents/${id}`)
}
