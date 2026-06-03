/**
 * 聊天 API — 会话管理 & 消息发送。
 */

import api from './auth'
import type { ChatMessage, ChatRequest, ChatResponse, Conversation } from '@/types'

// ============================================================
// Conversation
// ============================================================

/** 获取会话列表 */
export function getConversations() {
  return api.get<Conversation[]>('/chat/conversations')
}

/** 创建新会话 */
export function createConversation(title?: string) {
  return api.post<Conversation>('/chat/conversations', title ? { title } : {})
}

/** 删除会话 */
export function deleteConversation(id: number) {
  return api.delete(`/chat/conversations/${id}`)
}

// ============================================================
// Message
// ============================================================

/** 获取会话历史消息 */
export function getMessages(conversationId: number) {
  return api.get<ChatMessage[]>(`/chat/conversations/${conversationId}/messages`)
}

/** 非流式发送消息 */
export function sendMessage(data: ChatRequest) {
  return api.post<ChatResponse>('/chat/', data)
}
