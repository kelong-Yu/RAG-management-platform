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
  created_at: string
}

/** 聊天请求 */
export interface ChatRequest {
  message: string
  conversation_id?: number
}

/** 聊天响应 */
export interface ChatResponse {
  answer: string
  conversation_id: number
}
