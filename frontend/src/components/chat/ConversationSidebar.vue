<script setup lang="ts">
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import type { Conversation } from '@/types'

defineProps<{
  visible: boolean
  conversations: Conversation[]
  currentConversationId: number | null
  loading: boolean
  streaming: boolean
}>()

const emit = defineEmits<{
  (e: 'new-conversation'): void
  (e: 'switch-conversation', id: number): void
  (e: 'delete-conversation', id: number): void
  (e: 'rename-conversation', id: number, title: string): void
}>()
</script>

<template>
  <aside
    v-show="visible"
    class="w-64 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col"
  >
    <div class="h-14 px-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-center">
      <el-button
        type="primary"
        circle
        :disabled="streaming"
        @click="emit('new-conversation')"
      >
        <el-icon><Plus /></el-icon>
      </el-button>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div
        v-if="loading"
        class="p-4 text-center text-gray-400 text-sm"
      >
        加载中…
      </div>
      <div
        v-else-if="conversations.length === 0"
        class="p-4 text-center text-gray-400 text-sm"
      >
        暂无会话
      </div>
      <div
        v-for="conversation in conversations"
        :key="conversation.id"
        class="group flex items-center justify-between px-3 py-2.5 cursor-pointer border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        :class="{
          'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500':
            conversation.id === currentConversationId,
        }"
        @click="emit('switch-conversation', conversation.id)"
      >
        <div class="flex-1 min-w-0">
          <p class="text-sm text-gray-700 dark:text-gray-200 truncate">
            {{ conversation.title }}
          </p>
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
            {{ new Date(conversation.updated_at).toLocaleDateString('zh-CN') }}
          </p>
        </div>
        <div
          class="ml-2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity "
          :class="{
            'opacity-100': conversation.id === currentConversationId,
          }"
        >
          <el-button
            size="small"
            text
            :disabled="streaming"
            @click.stop="emit('rename-conversation', conversation.id, conversation.title)"
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
            @click.stop="emit('delete-conversation', conversation.id)"
          >
            <el-icon :size="14">
              <Delete />
            </el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </aside>
</template>
