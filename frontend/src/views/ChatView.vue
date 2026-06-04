<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox, ElTag } from 'element-plus'

import { getToken } from '@/utils'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage, Citation } from '@/types'

// ---- Store ----

const chatStore = useChatStore()

// ---- 状态 ----

const input = ref('')
const streaming = ref(false)
const messageArea = ref<HTMLElement>()
const sidebarVisible = ref(true)
const useRag = ref(false)
// 引用来源，key 为消息的临时 ID
const messageCitations = ref<Record<number, Citation[]>>({})

// ---- 初始化 ----

onMounted(async () => {
  await chatStore.fetchConversations()
  if (chatStore.conversations.length > 0) {
    await chatStore.switchConversation(chatStore.conversations[0].id)
  } else {
    await chatStore.newConversation()
  }
  scrollToBottom()
})

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
  if (!text || streaming.value) return

  // 确保有当前会话
  if (!chatStore.currentConversationId) {
    await chatStore.ensureConversation()
  }
  const conversationId = chatStore.currentConversationId!

  // 添加用户消息到本地
  const userMsgId = Date.now()
  const userMsg: ChatMessage = {
    id: userMsgId,
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  }
  chatStore.appendMessage(userMsg)
  input.value = ''
  streaming.value = true
  scrollToBottom()

  // 构建请求
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = getToken()

  try {
    const ragParam = useRag.value ? '&use_rag=true' : ''
    const url = `${baseURL}/chat/stream?message=${encodeURIComponent(text)}&conversation_id=${conversationId}${ragParam}`
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

        // 会话 ID 元数据（__CONV_ID__:<id>），不展示
        if (event.startsWith('__CONV_ID__:')) {
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
      if (event.startsWith('__CITATIONS__:')) {
        try {
          const json = event.slice('__CITATIONS__:'.length)
          messageCitations.value[assistantMsgId] = JSON.parse(json)
        } catch {
          // ignore
        }
        continue
      }
      if (event.startsWith('__CONV_ID__:')) continue
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
  await chatStore.newConversation()
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
      <div class="p-3 border-b border-gray-200 dark:border-gray-700">
        <el-button
          type="primary"
          class="w-full"
          :disabled="streaming"
          @click="handleNewConversation"
        >
          新对话
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
          <el-button
            class="opacity-0 group-hover:opacity-100 transition-opacity ml-2"
            size="small"
            text
            type="danger"
            :disabled="streaming"
            @click.stop="handleDeleteConversation(conv.id)"
          >
            <el-icon :size="14">
              <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
                <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
              </svg>
            </el-icon>
          </el-button>
        </div>
      </div>
    </aside>

    <!-- ================================ -->
    <!-- 主聊天区域                       -->
    <!-- ================================ -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部信息栏 -->
      <div class="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <el-button size="small" text @click="sidebarVisible = !sidebarVisible">
          <el-icon :size="18">
            <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
              <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
            </svg>
          </el-icon>
        </el-button>
        <span class="text-sm text-gray-600 dark:text-gray-400 truncate flex-1">
          {{ chatStore.conversations.find(c => c.id === chatStore.currentConversationId)?.title || '新对话' }}
        </span>

        <!-- RAG 开关 -->
        <el-tooltip
          :content="useRag ? '知识库检索已开启 — AI 会参考你的文档回答问题' : '点击开启知识库检索'"
          placement="bottom"
        >
          <el-button
            size="small"
            :type="useRag ? 'success' : 'default'"
            :disabled="streaming"
            @click="useRag = !useRag"
            class="shrink-0"
          >
            <span class="flex items-center gap-1">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
              {{ useRag ? '知识库' : '普通' }}
            </span>
          </el-button>
        </el-tooltip>
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
              <div class="bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-br-md">
                <p class="whitespace-pre-wrap break-words">{{ msg.content }}</p>
              </div>
              <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right mr-2">
                {{ formatTime(msg.created_at) }}
              </p>
            </div>
          </div>

          <div v-else class="flex justify-start">
            <div class="max-w-[75%]">
              <div class="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
                <p class="whitespace-pre-wrap break-words">{{ msg.content }}</p>
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

        <div class="max-w-4xl mx-auto flex items-end gap-3">
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
            :disabled="!input.trim() || streaming"
            @click="sendMessage"
          >
            发送
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>
