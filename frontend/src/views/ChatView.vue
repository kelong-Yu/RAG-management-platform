<script setup lang="ts">
import { nextTick, ref } from 'vue'

import { getToken } from '@/utils'

// ---- 类型 ----

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

interface SSEParseResult {
  events: string[]
  remainder: string
}

// ---- 状态 ----

const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(false)
const messageArea = ref<HTMLElement>()
let nextId = 1

// ---- 方法 ----

function scrollToBottom() {
  nextTick(() => {
    if (messageArea.value) {
      messageArea.value.scrollTop = messageArea.value.scrollHeight
    }
  })
}

function consumeSSEBuffer(buffer: string, flush = false): SSEParseResult {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const remainder = flush ? '' : (parts.pop() ?? '')
  const frames = flush ? parts : parts
  const events: string[] = []

  if (flush && remainder) {
    frames.push(remainder)
  }

  for (const frame of frames) {
    const trimmedFrame = frame.trim()
    if (!trimmedFrame) continue

    const dataLines = trimmedFrame
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

async function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return

  // 添加用户消息
  messages.value.push({
    id: nextId++,
    role: 'user',
    content: text,
    timestamp: Date.now(),
  })
  input.value = ''
  loading.value = true
  scrollToBottom()

  // 构建请求 URL
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const token = getToken()

  try {
    const response = await fetch(
      `${baseURL}/chat/stream?message=${encodeURIComponent(text)}`,
      {
        headers: {
          Accept: 'text/event-stream',
          Authorization: `Bearer ${token}`,
        },
      },
    )

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)
      throw new Error(errorData?.detail || `请求失败 (${response.status})`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const decoder = new TextDecoder()
    let buffer = ''
    let assistantMsgIndex: number | null = null

    const appendAssistantMessage = (content: string) => {
      if (assistantMsgIndex === null) {
        messages.value.push({
          id: nextId++,
          role: 'assistant',
          content,
          timestamp: Date.now(),
        })
        assistantMsgIndex = messages.value.length - 1
        loading.value = false
      } else {
        messages.value[assistantMsgIndex].content += content
      }
    }

    // 逐帧读取 SSE 流
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const { events, remainder } = consumeSSEBuffer(buffer)
      buffer = remainder

      for (const event of events) {
        appendAssistantMessage(event)
      }
      scrollToBottom()
    }

    buffer += decoder.decode()
    const { events: finalEvents } = consumeSSEBuffer(buffer, true)

    for (const event of finalEvents) {
      appendAssistantMessage(event)
    }

    // 流中没有收到任何数据
    if (assistantMsgIndex === null) {
      messages.value.push({
        id: nextId++,
        role: 'assistant',
        content: '模型未返回任何内容，请重试。',
        timestamp: Date.now(),
      })
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : '请求失败，请重试。'
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: message,
      timestamp: Date.now(),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-7rem)]">
    <!-- 消息区域 -->
    <div
      ref="messageArea"
      class="flex-1 overflow-y-auto px-4 py-6 space-y-4"
    >
      <!-- 空状态 -->
      <div
        v-if="messages.length === 0"
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
        </div>
      </div>

      <!-- 消息列表 -->
      <template v-for="msg in messages" :key="msg.id">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="flex justify-end">
          <div class="max-w-[75%]">
            <div class="bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-br-md">
              <p class="whitespace-pre-wrap wrap-break-word">{{ msg.content }}</p>
            </div>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right mr-2">
              {{ formatTime(msg.timestamp) }}
            </p>
          </div>
        </div>

        <!-- 助手消息 -->
        <div v-else class="flex justify-start">
          <div class="max-w-[75%]">
            <div class="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
              <p class="whitespace-pre-wrap wrap-break-word">{{ msg.content }}</p>
            </div>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 ml-2">
              {{ formatTime(msg.timestamp) }}
            </p>
          </div>
        </div>
      </template>

      <!-- 加载指示器 — 等待首个 Token -->
      <div v-if="loading" class="flex justify-start">
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
      <div class="max-w-4xl mx-auto flex items-end gap-3">
        <el-input
          v-model="input"
          type="textarea"
          :rows="1"
          placeholder="输入消息… (Enter 发送，Shift+Enter 换行)"
          resize="none"
          class="flex-1"
          :disabled="loading"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <el-button
          type="primary"
          :disabled="!input.trim() || loading"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>
