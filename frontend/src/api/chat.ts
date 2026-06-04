/**
 * 聊天 API — 会话管理 & 消息发送。
 */

import api from './auth'
import type {
  ChatCapabilities,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  Conversation,
} from '@/types'

// ============================================================
// Conversation
// ============================================================

/** 获取会话列表 */
export function getConversations() {
  return api.get<Conversation[]>('/chat/conversations')
}

/** 获取聊天能力开关 */
export function getChatCapabilities() {
  return api.get<ChatCapabilities>('/chat/capabilities')
}

/** 创建新会话 */
export function createConversation(title?: string) {
  return api.post<Conversation>('/chat/conversations', title ? { title } : {})
}

/** 手动更新会话标题 */
export function updateConversationTitle(id: number, title: string) {
  return api.patch<Conversation>(`/chat/conversations/${id}`, { title })
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
