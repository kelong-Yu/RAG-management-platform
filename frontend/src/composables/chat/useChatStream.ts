import { ref, type Ref } from 'vue'

import { useChatStore } from '@/stores/chat'
import type { Citation, ImageMeta } from '@/types'
import { getToken } from '@/utils'

interface SSEParseResult {
  events: string[]
  remainder: string
}

interface StreamState {
  assistantMsgAdded: boolean
  assistantMsgId: number
  pendingCitations: Citation[] | null
  pendingImages: ImageMeta[] | null
}

interface StreamRequest {
  message: string
  conversationId: number | null
  useRag: boolean
  attachmentIds: number[]
}

interface UseChatStreamOptions {
  chatStore: ReturnType<typeof useChatStore>
  messageCitations: Ref<Record<number, Citation[]>>
  messageImages: Ref<Record<number, ImageMeta[]>>
  visionCapable: Ref<boolean>
  scrollToBottom: () => void
}

function consumeSSEBuffer(buffer: string, flush = false): SSEParseResult {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const remainder = flush ? '' : (parts.pop() ?? '')
  const frames = flush ? parts : parts

  const events: string[] = []
  for (const frame of frames) {
    const trimmed = frame.trim()
    if (!trimmed) continue

    const dataLines = trimmed
      .split('\n')
      .filter((line) => line && !line.startsWith(':'))
      .map((line) => line.match(/^data:\s?(.*)$/)?.[1] ?? null)
      .filter((line): line is string => line !== null && line.length > 0)

    if (dataLines.length > 0) {
      events.push(dataLines.join('\n'))
    }
  }

  return { events, remainder }
}

export function useChatStream(options: UseChatStreamOptions) {
  const { chatStore, messageCitations, messageImages, visionCapable, scrollToBottom } = options
  const streaming = ref(false)
  let abortController: AbortController | null = null

  function syncPendingMetadata(state: StreamState) {
    if (!state.assistantMsgId) return

    if (state.pendingCitations) {
      messageCitations.value[state.assistantMsgId] = state.pendingCitations
      state.pendingCitations = null
    }

    if (state.pendingImages) {
      messageImages.value[state.assistantMsgId] = state.pendingImages
      state.pendingImages = null
    }
  }

  function moveMetadataToPersistedId(oldId: number, newId: number) {
    const existingCitations = messageCitations.value[oldId]
    if (existingCitations) {
      messageCitations.value[newId] = existingCitations
      delete messageCitations.value[oldId]
    }

    const existingImages = messageImages.value[oldId]
    if (existingImages) {
      messageImages.value[newId] = existingImages
      delete messageImages.value[oldId]
    }
  }

  async function handleStreamEvent(event: string, state: StreamState) {
    if (event.startsWith('__ASSISTANT_ID__:')) {
      const persistedId = Number(event.slice('__ASSISTANT_ID__:'.length))
      if (state.assistantMsgId && Number.isFinite(persistedId)) {
        chatStore.replaceMessageId(state.assistantMsgId, persistedId)
        moveMetadataToPersistedId(state.assistantMsgId, persistedId)
        state.assistantMsgId = persistedId
        syncPendingMetadata(state)
      }
      return
    }

    if (event.startsWith('__CITATIONS__:')) {
      try {
        const citations = JSON.parse(event.slice('__CITATIONS__:'.length)) as Citation[]
        if (state.assistantMsgId) {
          messageCitations.value[state.assistantMsgId] = citations
        } else {
          state.pendingCitations = citations
        }
      } catch {
        // ignore parse error
      }
      return
    }

    if (event.startsWith('__IMAGES__:')) {
      try {
        const payload = JSON.parse(event.slice('__IMAGES__:'.length)) as {
          images?: ImageMeta[]
          vision_capable?: boolean
        }

        if (payload.images && Array.isArray(payload.images)) {
          if (state.assistantMsgId) {
            messageImages.value[state.assistantMsgId] = payload.images
          } else {
            state.pendingImages = payload.images
          }
        }

        if (typeof payload.vision_capable === 'boolean') {
          visionCapable.value = payload.vision_capable
        }
      } catch {
        // ignore parse error
      }
      return
    }

    if (event.startsWith('__ERROR__:')) {
      const errorMsg = event.slice('__ERROR__:'.length)
      // 追加错误消息到对话
      chatStore.appendMessage({
        id: Date.now(),
        role: 'assistant',
        content: `[错误] ${errorMsg}`,
        created_at: new Date().toISOString(),
      })
      return
    }

    if (event.startsWith('__CONV_ID__:')) {
      const persistedConversationId = Number(event.slice('__CONV_ID__:'.length))
      if (Number.isFinite(persistedConversationId)) {
        await chatStore.switchConversation(persistedConversationId)
      }
      return
    }

    if (!state.assistantMsgAdded) {
      state.assistantMsgId = Date.now()
      chatStore.appendMessage({
        id: state.assistantMsgId,
        role: 'assistant',
        content: event,
        created_at: new Date().toISOString(),
      })
      state.assistantMsgAdded = true
      syncPendingMetadata(state)
      return
    }

    chatStore.appendToLastMessage(event)
  }

  async function streamAssistantReply(request: StreamRequest) {
    if (streaming.value) return

    streaming.value = true
    abortController = new AbortController()
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const token = getToken()

    try {
      const ragParam = request.useRag ? '&use_rag=true' : ''
      const conversationParam = request.conversationId
        ? `&conversation_id=${request.conversationId}`
        : ''
      const attachmentParams = request.attachmentIds.length > 0
        ? request.attachmentIds.map((id) => `&attachment_ids=${id}`).join('')
        : ''
      const url = `${baseURL}/chat/stream?message=${encodeURIComponent(request.message)}${conversationParam}${ragParam}${attachmentParams}`

      const response = await fetch(url, {
        headers: {
          Accept: 'text/event-stream',
          Authorization: `Bearer ${token}`,
        },
        signal: abortController.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => null)
        throw new Error(errorData?.detail || `请求失败 (${response.status})`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法读取响应流')

      const decoder = new TextDecoder()
      let buffer = ''
      const state: StreamState = {
        assistantMsgAdded: false,
        assistantMsgId: 0,
        pendingCitations: null,
        pendingImages: null,
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const { events, remainder } = consumeSSEBuffer(buffer)
        buffer = remainder

        for (const event of events) {
          await handleStreamEvent(event, state)
        }

        scrollToBottom()
      }

      buffer += decoder.decode()
      const { events: finalEvents } = consumeSSEBuffer(buffer, true)
      for (const event of finalEvents) {
        await handleStreamEvent(event, state)
      }

      if (!state.assistantMsgAdded) {
        chatStore.appendMessage({
          id: Date.now(),
          role: 'assistant',
          content: '模型未返回任何内容，请重试。',
          created_at: new Date().toISOString(),
        })
      }

      await chatStore.refreshConversations()
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        // 用户主动停止，不追加错误消息
        return
      }
      const message = error instanceof Error ? error.message : '请求失败，请重试。'
      chatStore.appendMessage({
        id: Date.now(),
        role: 'assistant',
        content: `[错误] ${message}`,
        created_at: new Date().toISOString(),
      })
    } finally {
      streaming.value = false
      abortController = null
      scrollToBottom()
    }
  }

  function stopStreaming() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  return {
    streaming,
    streamAssistantReply,
    stopStreaming,
  }
}
