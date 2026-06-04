// ============================================================
// 基础类型定义
// ============================================================

/** 用户信息 */
export interface User {
  id: number
  username: string
  email: string
  created_at: string
}

/** API 统一响应 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 注册请求 */
export interface RegisterRequest {
  username: string
  email: string
  password: string
}

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
}

/** 登录响应 */
export interface LoginResponse {
  access_token: string
  token_type: string
}

/** 分页参数 */
export interface PaginationParams {
  page: number
  page_size: number
}

/** 分页数据 */
export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 会话 */
export interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

/** 聊天消息 */
export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  extra_data?: Record<string, unknown> | null
  created_at: string
}

/** 聊天请求 */
export interface ChatRequest {
  message: string
  conversation_id?: number
  use_rag?: boolean
  attachment_ids?: number[]
}

/** 聊天响应 */
export interface ChatResponse {
  answer: string
  conversation_id: number
  citations: Citation[]
  attachment_ids: number[]
}

/** 聊天能力 */
export interface ChatCapabilities {
  vision_capable: boolean
}

/** 引用来源 */
export interface Citation {
  document_name: string
  page_number: number | null
  chunk_index: number
  content_snippet: string
  similarity: number
}

/** 图片附件元数据（来自 SSE __IMAGES__ 事件或 API 响应） */
export interface ImageMeta {
  attachment_id: number
  file_name: string
  mime_type: string
  file_size: number
  is_image: boolean
}

// ============================================================
// 上传 & 附件
// ============================================================

/** 上传状态枚举 */
export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error'

/** 附件来源类型 */
export type AttachmentSourceType = 'upload' | 'chat' | 'import'

/** 附件处理状态 */
export type AttachmentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

/** 附件 */
export interface Attachment {
  id: number
  user_id: number
  file_name: string
  stored_name: string
  file_path: string
  mime_type: string
  file_size: number
  source_type: AttachmentSourceType
  status: AttachmentStatus
  created_at: string
}

/** 附件列表 */
export interface AttachmentListResponse {
  items: Attachment[]
  total: number
}

/** 上传进度/状态（前端使用） */
export interface UploadState {
  file_id: number | null
  status: UploadStatus
  error_message: string | null
}

// ============================================================
// 知识库 & 文档
// ============================================================

/** 文档类型 */
export type DocumentType = 'pdf' | 'txt' | 'html'

/** 文档处理状态 */
export type DocumentStatus =
  | 'uploaded'
  | 'parsing'
  | 'chunking'
  | 'embedding'
  | 'ready'
  | 'failed'

/** 文档 */
export interface Document {
  id: number
  user_id: number
  attachment_id: number | null
  name: string
  doc_type: DocumentType
  status: DocumentStatus
  error_message: string | null
  chunk_count?: number | null
  created_at: string
  updated_at: string
}

/** 文档列表 */
export interface DocumentListResponse {
  items: Document[]
  total: number
}

/** 文档切片 */
export interface DocumentChunk {
  id: number
  document_id: number
  chunk_index: number
  page_number: number | null
  content: string
  created_at: string
}

/** 切片列表 */
export interface DocumentChunkListResponse {
  items: DocumentChunk[]
  total: number
}

/** 文档详情（含切片数量） */
export interface DocumentDetail extends Document {
  chunk_count: number
}

/** 创建文档请求 */
export interface CreateDocumentRequest {
  attachment_id: number
}
