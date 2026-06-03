<script setup lang="ts">
import { nextTick, ref } from 'vue'

// ---- 类型 ----

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp: number
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

function sendMessage() {
  const text = input.value.trim()
  if (!text) return

  // 添加用户消息
  messages.value.push({
    id: nextId++,
    role: 'user',
    content: text,
    timestamp: Date.now(),
  })
  input.value = ''
  scrollToBottom()

  // 模拟 AI 回复
  loading.value = true
  setTimeout(() => {
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: '这是一个模拟回复。后续将接入大模型 API 实现真正的对话。',
      timestamp: Date.now(),
    })
    loading.value = false
    scrollToBottom()
  }, 800)
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

      <!-- 加载指示器 -->
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
