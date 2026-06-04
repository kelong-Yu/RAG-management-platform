<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Fold, Plus, Picture } from '@element-plus/icons-vue'

import { getToken } from '@/utils'
import { useChatStore } from '@/stores/chat'
import { uploadFile } from '@/api/files'
import type { ChatMessage, Citation, ImageMeta } from '@/types'

const RAG_STORAGE_KEY = 'chat:useRag'
const CITATIONS_STORAGE_KEY = 'chat:citations'

// ---- Store ----

const chatStore = useChatStore()

// ---- 状态 ----

const input = ref('')
const streaming = ref(false)
const messageArea = ref<HTMLElement>()
const sidebarVisible = ref(true)
const useRag = ref(localStorage.getItem(RAG_STORAGE_KEY) === 'true')
// 引用来源，key 为消息的临时 ID
const messageCitations = ref<Record<number, Citation[]>>(
  (() => {
    const raw = localStorage.getItem(CITATIONS_STORAGE_KEY)
    if (!raw) return {}
    try {
      return JSON.parse(raw) as Record<number, Citation[]>
    } catch {
      return {}
    }
  })(),
)
const renameDialogVisible = ref(false)
const renameTitle = ref('')
const renameConversationId = ref<number | null>(null)

// ── 图片相关状态 ──
const imageInputRef = ref<HTMLInputElement>()
/** 待发送的图片列表 */
const pendingImages = ref<
  Array<{
    file: File
    previewUrl: string
    uploading: boolean
    attachmentId: number | null
    error: string | null
  }>
>([])
/** 消息关联的图片元数据，key 为消息 temp id */
const messageImages = ref<Record<number, ImageMeta[]>>({})
/** 图片 blob URL 缓存 keyed by attachment_id */
const imageBlobCache = ref<Record<number, string>>({})
/** 当前模型是否支持视觉（由 SSE __IMAGES__ 事件中的 vision_capable 字段决定） */
const visionCapable = ref(false)

const currentConversationTitle = computed(() =>
  chatStore.conversations.find(c => c.id === chatStore.currentConversationId)?.title || '新对话'
)

// 预加载消息关联的图片 blob URL
watch(
  messageImages,
  async (imagesMap) => {
    for (const images of Object.values(imagesMap)) {
      for (const img of images) {
        if (!imageBlobCache.value[img.attachment_id]) {
          try {
            await loadImageBlobUrl(img.attachment_id)
          } catch {
            // 加载失败，保留缓存以避免重复尝试
            imageBlobCache.value[img.attachment_id] = ''
          }
        }
      }
    }
  },
  { deep: true },
)

// ---- 初始化 ----

onMounted(async () => {
  await chatStore.fetchConversations()
  if (
    chatStore.currentConversationId &&
    chatStore.conversations.some(c => c.id === chatStore.currentConversationId)
  ) {
    await chatStore.switchConversation(chatStore.currentConversationId)
  } else if (chatStore.conversations.length > 0) {
    await chatStore.switchConversation(chatStore.conversations[0].id)
  } else {
    chatStore.beginDraftConversation()
  }
  scrollToBottom()
})

watch(useRag, (value) => {
  localStorage.setItem(RAG_STORAGE_KEY, String(value))
})

watch(
  messageCitations,
  (value) => {
    localStorage.setItem(CITATIONS_STORAGE_KEY, JSON.stringify(value))
  },
  { deep: true },
)

// ---- SSE 解析 ----

interface SSEParseResult {
  events: string[]
  remainder: string
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

// ── 图片辅助函数 ──

function triggerImagePicker() {
  imageInputRef.value?.click()
}

function handleImageFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  // MIME 白名单和大小检查 (20MB)
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  const maxSize = 20 * 1024 * 1024

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    if (!allowedTypes.includes(file.type)) {
      ElMessage.warning(`不支持的文件类型: ${file.name}`)
      continue
    }
    if (file.size > maxSize) {
      ElMessage.warning(`文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB): ${file.name}`)
      continue
    }
    pendingImages.value.push({
      file,
      previewUrl: URL.createObjectURL(file),
      uploading: false,
      attachmentId: null,
      error: null,
    })
  }

  // 重置 input，允许重复选同一文件
  input.value = ''
}

function removePendingImage(index: number) {
  const item = pendingImages.value[index]
  if (item) {
    URL.revokeObjectURL(item.previewUrl)
    pendingImages.value.splice(index, 1)
  }
}

async function loadImageBlobUrl(attachmentId: number): Promise<string> {
  if (imageBlobCache.value[attachmentId]) {
    return imageBlobCache.value[attachmentId]
  }
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = getToken()
  const response = await fetch(`${baseURL}/files/${attachmentId}/raw`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`图片加载失败 (${response.status})`)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  imageBlobCache.value[attachmentId] = url
  return url
}

function getImageMeta(msgId: number): ImageMeta[] {
  return messageImages.value[msgId] || []
}

// ---- 方法 ----

function scrollToBottom() {
  nextTick(() => {
    if (messageArea.value) {
      messageArea.value.scrollTop = messageArea.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = input.value.trim()
  const hasImages = pendingImages.value.length > 0
  if ((!text && !hasImages) || streaming.value) return

  const conversationId = chatStore.currentConversationId

  // 上传所有待发送图片
  const attachmentIds: number[] = []
  const uploadedImages: ImageMeta[] = []

  if (hasImages) {
    for (const item of pendingImages.value) {
      item.uploading = true
      try {
        const res = await uploadFile(item.file)
        item.attachmentId = res.data.id
        attachmentIds.push(res.data.id)
        uploadedImages.push({
          attachment_id: res.data.id,
          file_name: res.data.file_name,
          mime_type: res.data.mime_type,
          file_size: res.data.file_size,
          is_image: true,
        })
        item.uploading = false
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '上传失败'
        item.error = msg
        item.uploading = false
        ElMessage.error(`图片上传失败: ${msg}`)
        return // 任一张上传失败就中止
      }
    }
  }

  // 添加用户消息到本地
  const userMsgId = Date.now()
  const userMsg: ChatMessage = {
    id: userMsgId,
    role: 'user',
    content: text || '[图片]',
    extra_data: attachmentIds.length > 0 ? { attachment_ids: attachmentIds } : undefined,
    created_at: new Date().toISOString(),
  }
  chatStore.appendMessage(userMsg)

  // 关联图片到消息
  if (uploadedImages.length > 0) {
    messageImages.value[userMsgId] = uploadedImages
  }

  // 清空待发送图片
  pendingImages.value.forEach((item) => URL.revokeObjectURL(item.previewUrl))
  pendingImages.value = []
  input.value = ''
  streaming.value = true
  scrollToBottom()

  // 构建请求
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = getToken()

  try {
    const ragParam = useRag.value ? '&use_rag=true' : ''
    const conversationParam = conversationId ? `&conversation_id=${conversationId}` : ''
    const attachmentParams = attachmentIds.length > 0
      ? attachmentIds.map((id) => `&attachment_ids=${id}`).join('')
      : ''
    const url = `${baseURL}/chat/stream?message=${encodeURIComponent(text || '[图片]')}${conversationParam}${ragParam}${attachmentParams}`
    const response = await fetch(url, {
      headers: {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      throw new Error(errorData?.detail || `请求失败 (${response.status})`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''
    let assistantMsgAdded = false
    let assistantMsgId = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const { events, remainder } = consumeSSEBuffer(buffer)
      buffer = remainder

      for (const event of events) {
        if (event.startsWith('__ASSISTANT_ID__:')) {
          const persistedId = Number(event.slice('__ASSISTANT_ID__:'.length))
          if (assistantMsgId && Number.isFinite(persistedId)) {
            const existing = messageCitations.value[assistantMsgId]
            chatStore.replaceMessageId(assistantMsgId, persistedId)
            if (existing) {
              messageCitations.value[persistedId] = existing
              delete messageCitations.value[assistantMsgId]
            }
            assistantMsgId = persistedId
          }
          continue
        }

        // 引用元数据（__CITATIONS__:<json>），不展示
        if (event.startsWith('__CITATIONS__:')) {
          try {
            const json = event.slice('__CITATIONS__:'.length)
            messageCitations.value[assistantMsgId] = JSON.parse(json)
          } catch {
            // ignore parse error
          }
          continue
        }

        // 图片元数据（__IMAGES__:<json>），不展示
        if (event.startsWith('__IMAGES__:')) {
          try {
            const json = event.slice('__IMAGES__:'.length)
            const payload = JSON.parse(json)
            if (payload.images && Array.isArray(payload.images)) {
              messageImages.value[assistantMsgId] = payload.images as ImageMeta[]
            }
            if (typeof payload.vision_capable === 'boolean') {
              visionCapable.value = payload.vision_capable
            }
          } catch {
            // ignore parse error
          }
          continue
        }

        // 会话 ID 元数据（__CONV_ID__:<id>），不展示
        if (event.startsWith('__CONV_ID__:')) {
          const persistedConversationId = Number(event.slice('__CONV_ID__:'.length))
          if (Number.isFinite(persistedConversationId)) {
            await chatStore.switchConversation(persistedConversationId)
          }
          continue
        }

        if (!assistantMsgAdded) {
          assistantMsgId = Date.now()
          chatStore.appendMessage({
            id: assistantMsgId,
            role: 'assistant',
            content: event,
            created_at: new Date().toISOString(),
          })
          assistantMsgAdded = true
        } else {
          chatStore.appendToLastMessage(event)
        }
      }
      scrollToBottom()
    }

    // 处理最后残留 buffer
    buffer += decoder.decode()
    const { events: finalEvents } = consumeSSEBuffer(buffer, true)
    for (const event of finalEvents) {
      if (event.startsWith('__ASSISTANT_ID__:')) {
        const persistedId = Number(event.slice('__ASSISTANT_ID__:'.length))
        if (assistantMsgId && Number.isFinite(persistedId)) {
          const existing = messageCitations.value[assistantMsgId]
          chatStore.replaceMessageId(assistantMsgId, persistedId)
          if (existing) {
            messageCitations.value[persistedId] = existing
            delete messageCitations.value[assistantMsgId]
          }
          assistantMsgId = persistedId
        }
        continue
      }
      if (event.startsWith('__CITATIONS__:')) {
        try {
          const json = event.slice('__CITATIONS__:'.length)
          messageCitations.value[assistantMsgId] = JSON.parse(json)
        } catch {
          // ignore
        }
        continue
      }
      if (event.startsWith('__IMAGES__:')) {
        try {
          const json = event.slice('__IMAGES__:'.length)
          const payload = JSON.parse(json)
          if (payload.images && Array.isArray(payload.images)) {
            messageImages.value[assistantMsgId] = payload.images as ImageMeta[]
          }
          if (typeof payload.vision_capable === 'boolean') {
            visionCapable.value = payload.vision_capable
          }
        } catch {
          // ignore
        }
        continue
      }
      if (event.startsWith('__CONV_ID__:')) {
        const persistedConversationId = Number(event.slice('__CONV_ID__:'.length))
        if (Number.isFinite(persistedConversationId)) {
          await chatStore.switchConversation(persistedConversationId)
        }
        continue
      }
      if (!assistantMsgAdded) {
        assistantMsgId = Date.now()
        chatStore.appendMessage({
          id: assistantMsgId,
          role: 'assistant',
          content: event,
          created_at: new Date().toISOString(),
        })
        assistantMsgAdded = true
      } else {
        chatStore.appendToLastMessage(event)
      }
    }

    if (!assistantMsgAdded) {
      chatStore.appendMessage({
        id: Date.now(),
        role: 'assistant',
        content: '模型未返回任何内容，请重试。',
        created_at: new Date().toISOString(),
      })
    }

    // 刷新会话列表以更新标题和排序
    chatStore.refreshConversations()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : '请求失败，请重试。'
    chatStore.appendMessage({
      id: Date.now(),
      role: 'assistant',
      content: message,
      created_at: new Date().toISOString(),
    })
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

async function handleSwitchConversation(id: number) {
  if (streaming.value) return
  await chatStore.switchConversation(id)
  scrollToBottom()
}

async function handleNewConversation() {
  if (streaming.value) return
  chatStore.beginDraftConversation()
  scrollToBottom()
}

async function handleDeleteConversation(id: number) {
  if (streaming.value) return
  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatStore.removeConversation(id)
    ElMessage.success('已删除')
    scrollToBottom()
  } catch {
    // 用户取消
  }
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getCitations(msgId: number): Citation[] {
  return messageCitations.value[msgId] || []
}

function openRenameDialog(conversationId?: number, title?: string) {
  const targetId = conversationId ?? chatStore.currentConversationId
  if (!targetId) return
  renameConversationId.value = targetId
  renameTitle.value = title ?? currentConversationTitle.value
  renameDialogVisible.value = true
}

async function handleRenameConversation() {
  const currentId = renameConversationId.value
  const nextTitle = renameTitle.value.trim()
  if (!currentId || !nextTitle) return

  try {
    await chatStore.renameConversation(currentId, nextTitle)
    renameDialogVisible.value = false
    renameConversationId.value = null
    ElMessage.success('已更新会话标题')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '重命名失败'
    ElMessage.error(msg)
  }
}

function handleCloseRenameDialog() {
  renameDialogVisible.value = false
  renameConversationId.value = null
  renameTitle.value = ''
}
</script>

<template>
  <div class="flex h-[calc(100vh-7rem)] gap-0">
    <!-- ================================ -->
    <!-- 侧边栏 — 会话列表               -->
    <!-- ================================ -->
    <aside
      v-show="sidebarVisible"
      class="w-64 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col"
    >
      <div class="h-14 px-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-center">
        <el-button
          type="primary"
          circle
          :disabled="streaming"
          @click="handleNewConversation"
        >
          <el-icon><Plus /></el-icon>
        </el-button>
        
      </div>

      <div class="flex-1 overflow-y-auto">
        <div
          v-if="chatStore.loadingConversations"
          class="p-4 text-center text-gray-400 text-sm"
        >
          加载中…
        </div>
        <div
          v-else-if="chatStore.conversations.length === 0"
          class="p-4 text-center text-gray-400 text-sm"
        >
          暂无会话
        </div>
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          class="group flex items-center justify-between px-3 py-2.5 cursor-pointer border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          :class="{
            'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500':
              conv.id === chatStore.currentConversationId,
          }"
          @click="handleSwitchConversation(conv.id)"
        >
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-700 dark:text-gray-200 truncate">
              {{ conv.title }}
            </p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              {{ new Date(conv.updated_at).toLocaleDateString('zh-CN') }}
            </p>
          </div>
          <div
            class="ml-2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity "
            :class="{
              'opacity-100': conv.id === chatStore.currentConversationId,
            }"
          >
            <el-button
              size="small"
              text
              :disabled="streaming"
              @click.stop="openRenameDialog(conv.id, conv.title)"
            >
              <el-icon :size="14">
                <Edit />
              </el-icon>
            </el-button>
            <el-button
              size="small"
              text
              type="danger"
              :disabled="streaming"
              @click.stop="handleDeleteConversation(conv.id)"
            >
              <el-icon :size="14">
                <Delete />
              </el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </aside>

    <!-- ================================ -->
    <!-- 主聊天区域                       -->
    <!-- ================================ -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部信息栏 -->
      <div class="grid grid-cols-[112px_minmax(0,1fr)_112px] items-center px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div class="flex items-center justify-start">
          <el-button size="small" text @click="sidebarVisible = !sidebarVisible">
            <el-icon :size="18">
              <Fold />
            </el-icon>
          </el-button>
        </div>

        <div class="text-sm text-gray-600 dark:text-gray-400 truncate text-center font-medium">
          {{ currentConversationTitle }}
        </div>

        <!-- RAG 开关 -->
        <div class="flex items-center justify-end">
          <el-tooltip
            :content="useRag ? '知识库检索已开启 — AI 会参考你的文档回答问题' : '点击开启知识库检索'"
            placement="bottom"
          >
            <el-button
              size="small"
              :type="useRag ? 'success' : 'default'"
              :disabled="streaming"
              @click="useRag = !useRag"
              class="min-w-22 justify-center"
            >
              <span class="flex items-center justify-center gap-1 w-full">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                {{ useRag ? '知识库' : '普通' }}
              </span>
            </el-button>
          </el-tooltip>
        </div>
      </div>

      <!-- 消息区域 -->
      <div
        ref="messageArea"
        class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
      >
        <!-- 加载历史消息 -->
        <div
          v-if="chatStore.loadingMessages"
          class="flex justify-center py-4"
        >
          <span class="text-sm text-gray-400">加载历史消息…</span>
        </div>

        <!-- 空状态 -->
        <div
          v-if="chatStore.messages.length === 0 && !streaming && !chatStore.loadingMessages"
          class="flex items-center justify-center h-full"
        >
          <div class="text-center text-gray-400 dark:text-gray-500">
            <el-icon :size="48" class="mb-3">
              <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
              </svg>
            </el-icon>
            <p class="text-lg">开始新对话</p>
            <p class="text-sm mt-1">在下方输入消息，开始与 AI 交流</p>
            <p v-if="useRag" class="text-sm mt-1 text-green-600 dark:text-green-400">
              知识库检索模式已开启
            </p>
          </div>
        </div>

        <!-- 消息列表 -->
        <template v-for="msg in chatStore.messages" :key="msg.id">
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="max-w-[75%]">
              <!-- 图片附件展示 -->
              <div
                v-if="getImageMeta(msg.id).length > 0"
                class="flex flex-wrap justify-end gap-1.5 mb-1.5"
              >
                <div
                  v-for="img in getImageMeta(msg.id)"
                  :key="img.attachment_id"
                  class="relative group"
                >
                  <img
                    v-if="imageBlobCache[img.attachment_id]"
                    :src="imageBlobCache[img.attachment_id]"
                    :alt="img.file_name"
                    class="max-w-[200px] max-h-[200px] rounded-lg object-cover border border-blue-300"
                    loading="lazy"
                  />
                  <div
                    v-else
                    class="w-[120px] h-[90px] rounded-lg bg-gray-200 dark:bg-gray-600 flex items-center justify-center"
                  >
                    <span class="text-xs text-gray-400">加载中…</span>
                  </div>
                </div>
              </div>
              <div class="bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-br-md">
                <p class="whitespace-pre-wrap wrap-break-word">{{ msg.content }}</p>
              </div>
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right mr-2">
                {{ formatTime(msg.created_at) }}
              </p>
            </div>
          </div>

          <div v-else class="flex justify-start">
            <div class="max-w-[75%]">
              <div class="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
                <p class="whitespace-pre-wrap wrap-break-word">{{ msg.content }}</p>
              </div>

              <!-- 引用来源卡片 -->
              <div
                v-if="getCitations(msg.id).length > 0"
                class="mt-2 space-y-1.5"
              >
                <div class="text-xs text-gray-400 dark:text-gray-500 font-medium mb-1">
                  参考来源：
                </div>
                <div
                  v-for="(citation, idx) in getCitations(msg.id)"
                  :key="idx"
                  class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-2 text-xs"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span class="font-medium text-green-800 dark:text-green-200 truncate">
                      {{ citation.document_name }}
                    </span>
                    <el-tag
                      v-if="citation.page_number"
                      size="small"
                      type="success"
                      class="shrink-0"
                    >
                      第{{ citation.page_number }}页
                    </el-tag>
                    <span class="text-green-600 dark:text-green-400 shrink-0">
                      相关度 {{ (citation.similarity * 100).toFixed(0) }}%
                    </span>
                  </div>
                  <p class="text-gray-600 dark:text-gray-400 line-clamp-3">
                    {{ citation.content_snippet }}
                  </p>
                </div>
              </div>

              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 ml-2">
                {{ formatTime(msg.created_at) }}
              </p>
            </div>
          </div>
        </template>

        <!-- 加载指示器 -->
        <div v-if="streaming && chatStore.messages.length > 0 && chatStore.messages[chatStore.messages.length - 1].role === 'user'" class="flex justify-start">
          <div class="bg-gray-100 dark:bg-gray-700 px-4 py-3 rounded-2xl rounded-bl-md">
            <div class="flex items-center gap-1.5">
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-4">
        <!-- RAG 状态提示 -->
        <div
          v-if="useRag"
          class="max-w-4xl mx-auto mb-2"
        >
          <span class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            知识库检索已开启 — AI 会参考你的文档回答问题
          </span>
        </div>

        <!-- 待发送图片缩略图 -->
        <div
          v-if="pendingImages.length > 0"
          class="max-w-4xl mx-auto mb-2 flex flex-wrap gap-2"
        >
          <div
            v-for="(item, idx) in pendingImages"
            :key="idx"
            class="relative group w-16 h-16 rounded-lg overflow-hidden border border-gray-300 dark:border-gray-600"
          >
            <img
              :src="item.previewUrl"
              class="w-full h-full object-cover"
              :alt="item.file.name"
            />
            <!-- 上传中蒙层 -->
            <div
              v-if="item.uploading"
              class="absolute inset-0 bg-black/40 flex items-center justify-center"
            >
              <span class="text-white text-xs">上传中…</span>
            </div>
            <!-- 错误标记 -->
            <div
              v-if="item.error"
              class="absolute inset-0 bg-red-500/60 flex items-center justify-center"
            >
              <span class="text-white text-xs">失败</span>
            </div>
            <!-- 删除按钮 -->
            <button
              v-if="!item.uploading"
              class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              @click="removePendingImage(idx)"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- 视觉降级 / 启用提示 -->
        <div
          v-if="pendingImages.length > 0"
          class="max-w-4xl mx-auto mb-2"
        >
          <span
            v-if="!visionCapable"
            class="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
              <path d="M12 2L2 22h20L12 2z" />
              <line x1="12" y1="9" x2="12" y2="14" />
              <circle cx="12" cy="18" r="0.5" fill="currentColor" />
            </svg>
            当前模型不支持图像理解，图片仅作展示，AI 无法查看图片内容
          </span>
          <span
            v-else
            class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
            </svg>
            视觉理解已启用 — AI 将分析图片内容并回复
          </span>
        </div>

        <div class="max-w-4xl mx-auto flex items-end gap-3">
          <el-button
            size="default"
            :disabled="streaming"
            @click="triggerImagePicker"
            class="shrink-0"
          >
            <el-icon :size="18"><Picture /></el-icon>
          </el-button>
          <input
            ref="imageInputRef"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            multiple
            class="hidden"
            @change="handleImageFilesSelected"
          />
          <el-input
            v-model="input"
            type="textarea"
            :rows="1"
            :placeholder="useRag ? '输入问题，AI 将从知识库中检索相关知识… (Enter 发送，Shift+Enter 换行)' : '输入消息… (Enter 发送，Shift+Enter 换行)'"
            resize="none"
            class="flex-1"
            :disabled="streaming"
            @keydown.enter.exact.prevent="sendMessage"
          />
          <el-button
            type="primary"
            :disabled="(!input.trim() && pendingImages.length === 0) || streaming"
            @click="sendMessage"
          >
            发送
          </el-button>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="renameDialogVisible"
      title="重命名会话"
      width="420px"
      @closed="handleCloseRenameDialog"
    >
      <el-input
        v-model="renameTitle"
        maxlength="100"
        show-word-limit
        placeholder="输入新的会话标题"
        @keydown.enter.prevent="handleRenameConversation"
      />
      <template #footer>
        <el-button @click="handleCloseRenameDialog">取消</el-button>
        <el-button
          type="primary"
          :disabled="!renameTitle.trim()"
          @click="handleRenameConversation"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
