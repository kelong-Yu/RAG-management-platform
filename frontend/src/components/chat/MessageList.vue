<script setup lang="ts">
import type { ChatMessage, Citation, ImageMeta } from '@/types'

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
  streaming: boolean
  useRag: boolean
  citations: Record<number, Citation[]>
  messageImages: Record<number, ImageMeta[]>
  imageBlobCache: Record<number, string>
}>()

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getCitations(messageId: number): Citation[] {
  return props.citations[messageId] || []
}

function getImageMeta(messageId: number): ImageMeta[] {
  return props.messageImages[messageId] || []
}
</script>

<template>
  <div class="min-h-full px-4 py-6 space-y-4">
    <div
      v-if="loading"
      class="flex justify-center py-4"
    >
      <span class="text-sm text-gray-400">加载历史消息…</span>
    </div>

    <div
      v-if="messages.length === 0 && !streaming && !loading"
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

    <template v-for="message in messages" :key="message.id">
      <div v-if="message.role === 'user'" class="flex justify-end">
        <div class="max-w-[75%]">
          <div
            v-if="getImageMeta(message.id).length > 0"
            class="flex flex-wrap justify-end gap-1.5 mb-1.5"
          >
            <div
              v-for="image in getImageMeta(message.id)"
              :key="image.attachment_id"
              class="relative group"
            >
              <img
                v-if="imageBlobCache[image.attachment_id]"
                :src="imageBlobCache[image.attachment_id]"
                :alt="image.file_name"
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
            <p class="whitespace-pre-wrap wrap-break-word">{{ message.content }}</p>
          </div>
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right mr-2">
            {{ formatTime(message.created_at) }}
          </p>
        </div>
      </div>

      <div v-else class="flex justify-start">
        <div class="max-w-[75%]">
          <div class="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
            <p class="whitespace-pre-wrap wrap-break-word">{{ message.content }}</p>
          </div>

          <div
            v-if="getCitations(message.id).length > 0"
            class="mt-2 space-y-1.5"
          >
            <div class="text-xs text-gray-400 dark:text-gray-500 font-medium mb-1">
              参考来源：
            </div>
            <div
              v-for="(citation, index) in getCitations(message.id)"
              :key="index"
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
            {{ formatTime(message.created_at) }}
          </p>
        </div>
      </div>
    </template>

    <div
      v-if="streaming && messages.length > 0 && messages[messages.length - 1].role === 'user'"
      class="flex justify-start"
    >
      <div class="bg-gray-100 dark:bg-gray-700 px-4 py-3 rounded-2xl rounded-bl-md">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
          <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
        </div>
      </div>
    </div>
  </div>
</template>
