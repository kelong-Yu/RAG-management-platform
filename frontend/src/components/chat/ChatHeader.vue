<script setup lang="ts">
import { Fold } from '@element-plus/icons-vue'

defineProps<{
  currentConversationTitle: string
  useRag: boolean
  streaming: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-sidebar'): void
  (e: 'toggle-rag'): void
}>()
</script>

<template>
  <div class="grid grid-cols-[112px_minmax(0,1fr)_112px] h-14 items-center 
  px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
    <div class="flex items-center justify-start">
      <el-button size="small" text @click="emit('toggle-sidebar')">
        <el-icon :size="18">
          <Fold />
        </el-icon>
      </el-button>
    </div>

    <div class="text-sm text-gray-600 dark:text-gray-400 truncate text-center font-medium mr-4">
      {{ currentConversationTitle }}
    </div>

    <div class="flex items-center justify-end ">
      <el-tooltip
        :content="useRag ? '知识库检索已开启 — AI 会参考你的文档回答问题' : '点击开启知识库检索'"
        placement="bottom"
      >
        <el-button
          size="small"
          :type="useRag ? 'success' : 'default'"
          :disabled="streaming"
          class="min-w-22 justify-center mr-8"
          @click="emit('toggle-rag')"
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
</template>
