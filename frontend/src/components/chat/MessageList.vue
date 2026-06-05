<script setup lang="ts">
import { ref } from 'vue'
import type { ChatMessage, Citation, ImageMeta } from '@/types'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
  streaming: boolean
  useRag: boolean
  citations: Record<number, Citation[]>
  messageImages: Record<number, ImageMeta[]>
  imageBlobCache: Record<number, string>
}>()

const emit = defineEmits<{
  (e: 'retry'): void
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

// 引用面板展开状态
const expandedCitations = ref<Set<number>>(new Set())

function isCitationExpanded(messageId: number): boolean {
  return expandedCitations.value.has(messageId)
}

function toggleCitations(messageId: number) {
  const next = new Set(expandedCitations.value)
  if (next.has(messageId)) {
    next.delete(messageId)
  } else {
    next.add(messageId)
  }
  expandedCitations.value = next
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
        <div class="max-w-[75%] flex flex-col items-end">
          <div
            v-if="getImageMeta(message.id).length > 0"
            class="flex flex-wrap justify-end gap-1.5 mb-1.5 max-w-full"
          >
            <div
              v-for="image in getImageMeta(message.id)"
              :key="image.attachment_id"
              class="relative group shrink-0"
            >
              <img
                v-if="imageBlobCache[image.attachment_id]"
                :src="imageBlobCache[image.attachment_id]"
                :alt="image.file_name"
                class="block w-32 h-32 sm:w-40 sm:h-40 rounded-lg object-cover border border-blue-300 bg-white"
                loading="lazy"
              />
              <div
                v-else
                class="w-32 h-32 sm:w-40 sm:h-40 rounded-lg bg-gray-200 dark:bg-gray-600 flex items-center justify-center"
              >
                <span class="text-xs text-gray-400">加载中…</span>
              </div>
            </div>
          </div>
          <div class="inline-block max-w-full bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-br-md">
            <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>
          </div>
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 text-right mr-2">
            {{ formatTime(message.created_at) }}
          </p>
        </div>
      </div>

      <div v-else class="flex justify-start">
        <div class="max-w-[85%]">
          <div class="bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-md">
            <MarkdownContent :content="message.content" />
          </div>

          <div
            v-if="getCitations(message.id).length > 0"
            class="mt-2"
          >
            <button
              class="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400 font-medium hover:text-green-800 dark:hover:text-green-300 transition-colors mb-1.5"
              @click="toggleCitations(message.id)"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                width="14"
                height="14"
                :class="{ 'rotate-90': isCitationExpanded(message.id) }"
                class="transition-transform"
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              参考来源 ({{ getCitations(message.id).length }})
              <span v-if="!isCitationExpanded(message.id)" class="text-green-500/60">
                - 点击展开
              </span>
            </button>
            <div
              v-if="isCitationExpanded(message.id)"
              class="space-y-1.5"
            >
              <div
                v-for="(citation, index) in getCitations(message.id)"
                :key="index"
                class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-2.5 text-xs"
              >
                <div class="flex items-center gap-2 mb-1.5">
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
                  <span class="text-green-600 dark:text-green-400 shrink-0 ml-auto">
                    相关度 {{ (citation.similarity * 100).toFixed(0) }}%
                  </span>
                </div>
                <p class="text-gray-600 dark:text-gray-400 leading-relaxed">
                  {{ citation.content_snippet }}
                </p>
              </div>
            </div>
          </div>

          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 ml-2">
            {{ formatTime(message.created_at) }}
          </p>
          <!-- 错误重试按钮 -->
          <div
            v-if="message.content.startsWith('[错误]')"
            class="mt-1.5 ml-2"
          >
            <el-button
              size="small"
              type="warning"
              plain
              :disabled="streaming"
              @click="emit('retry')"
            >
              重试
            </el-button>
          </div>
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
