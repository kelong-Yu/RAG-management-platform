/**
 * Files API — 统一文件上传、列表、删除。
 */

import api from './auth'
import type { Attachment, AttachmentListResponse } from '@/types'

/** 上传文件（multipart/form-data） */
export function uploadFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.post<Attachment>('/files/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000, // 上传超时 60s
  })
}

/** 获取附件列表 */
export function getFiles(page = 1, pageSize = 50) {
  return api.get<AttachmentListResponse>('/files', {
    params: { page, page_size: pageSize },
  })
}

/** 删除附件 */
export function deleteFile(id: number) {
  return api.delete<{ message: string }>(`/files/${id}`)
}
