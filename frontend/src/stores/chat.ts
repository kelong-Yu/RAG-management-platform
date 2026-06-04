import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Conversation, ChatMessage } from '@/types'
import {
  getConversations,
  createConversation,
  deleteConversation as deleteConversationApi,
  getMessages,
  updateConversationTitle as updateConversationTitleApi,
} from '@/api/chat'

const CURRENT_CONVERSATION_STORAGE_KEY = 'chat:currentConversationId'

function persistCurrentConversationId(id: number | null) {
  if (id === null) {
    localStorage.removeItem(CURRENT_CONVERSATION_STORAGE_KEY)
    return
  }
  localStorage.setItem(CURRENT_CONVERSATION_STORAGE_KEY, String(id))
}

export const useChatStore = defineStore('chat', () => {
  // ---- 状态 ----
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<number | null>(
    (() => {
      const raw = localStorage.getItem(CURRENT_CONVERSATION_STORAGE_KEY)
      return raw ? Number(raw) : null
    })(),
  )
  const messages = ref<ChatMessage[]>([])
  const loadingConversations = ref(false)
  const loadingMessages = ref(false)

  // ---- 会话操作 ----

  /** 加载会话列表 */
  async function fetchConversations() {
    loadingConversations.value = true
    try {
      const res = await getConversations()
      conversations.value = res.data
    } finally {
      loadingConversations.value = false
    }
  }

  /** 新建会话并设为当前 */
  async function newConversation(): Promise<Conversation> {
    const res = await createConversation()
    const conv = res.data
    conversations.value.unshift(conv)
    currentConversationId.value = conv.id
    persistCurrentConversationId(conv.id)
    messages.value = []
    return conv
  }

  /** 开始一个未持久化的新对话草稿 */
  function beginDraftConversation() {
    currentConversationId.value = null
    persistCurrentConversationId(null)
    messages.value = []
  }

  /** 确保存在当前会话（没有则新建） */
  async function ensureConversation(): Promise<Conversation> {
    if (currentConversationId.value) {
      const found = conversations.value.find(
        (c) => c.id === currentConversationId.value,
      )
      if (found) return found
    }
    return await newConversation()
  }

  /** 切换到指定会话并加载历史消息 */
  async function switchConversation(id: number) {
    currentConversationId.value = id
    persistCurrentConversationId(id)
    loadingMessages.value = true
    try {
      const res = await getMessages(id)
      messages.value = res.data
    } finally {
      loadingMessages.value = false
    }
  }

  /** 删除会话 */
  async function removeConversation(id: number) {
    await deleteConversationApi(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentConversationId.value === id) {
      beginDraftConversation()
      // 自动切换到第一个会话或新建
      if (conversations.value.length > 0) {
        await switchConversation(conversations.value[0].id)
      } else {
        beginDraftConversation()
      }
    }
  }

  /** 追加消息到当前会话（本地，不等后端） */
  function appendMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  /** 更新最后一条消息内容（用于流式追加 token） */
  function appendToLastMessage(token: string) {
    const last = messages.value[messages.value.length - 1]
    if (last) {
      last.content += token
    }
  }

  /** 用持久化后的消息 id 替换前端临时 id */
  function replaceMessageId(oldId: number, newId: number) {
    const target = messages.value.find((msg) => msg.id === oldId)
    if (target) {
      target.id = newId
    }
  }

  /** 手动更新当前会话标题 */
  async function renameConversation(id: number, title: string) {
    const res = await updateConversationTitleApi(id, title)
    const updated = res.data
    const index = conversations.value.findIndex((conv) => conv.id === id)
    if (index >= 0) {
      conversations.value[index] = updated
    }
    return updated
  }

  /** 刷新当前会话列表（用于更新标题和排序） */
  async function refreshConversations() {
    await fetchConversations()
  }

  return {
    conversations,
    currentConversationId,
    messages,
    loadingConversations,
    loadingMessages,
    fetchConversations,
    newConversation,
    beginDraftConversation,
    ensureConversation,
    switchConversation,
    removeConversation,
    appendMessage,
    appendToLastMessage,
    replaceMessageId,
    renameConversation,
    refreshConversations,
  }
})
