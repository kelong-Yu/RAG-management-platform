/**
 * Admin API — 用户管理、知识库管理和默认知识库同步。
 */

import api from './auth'
import type {
  AdminDocument,
  AdminDocumentListResponse,
  AdminUser,
  AdminUserUpdate,
} from '@/types'

export function getAdminUsers() {
  return api.get<AdminUser[]>('/admin/users')
}

export function updateAdminUser(userId: number, data: AdminUserUpdate) {
  return api.patch<AdminUser>(`/admin/users/${userId}`, data)
}

export function deleteAdminUser(userId: number) {
  return api.delete<{ message: string }>(`/admin/users/${userId}`)
}

export function getAdminDocuments(page = 1, pageSize = 100) {
  return api.get<AdminDocumentListResponse>('/admin/documents', {
    params: { page, page_size: pageSize },
  })
}

export function deleteAdminDocument(documentId: number) {
  return api.delete<{ message: string }>(`/admin/documents/${documentId}`)
}

export function syncDefaultKnowledgeBase() {
  return api.post<AdminDocument>('/admin/knowledge/default/sync')
}
