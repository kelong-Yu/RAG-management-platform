<script setup lang="ts">
import { Picture } from '@element-plus/icons-vue'
import { ref } from 'vue'

import type { PendingImageItem } from '@/composables/chat/useChatImages'

defineProps<{
  input: string
  useRag: boolean
  streaming: boolean
  pendingImages: PendingImageItem[]
  visionCapable: boolean
}>()

const emit = defineEmits<{
  (e: 'update:input', value: string): void
  (e: 'send'): void
  (e: 'remove-image', index: number): void
  (e: 'image-files-selected', files: FileList | null): void
}>()

const imageInputRef = ref<HTMLInputElement>()

function triggerImagePicker() {
  imageInputRef.value?.click()
}

function handleImageFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  emit('image-files-selected', input.files)
  input.value = ''
}
</script>

<template>
  <div class="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-4">
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

    <div
      v-if="pendingImages.length > 0"
      class="max-w-4xl mx-auto mb-2 flex flex-wrap gap-2"
    >
      <div
        v-for="(item, index) in pendingImages"
        :key="index"
        class="relative group w-16 h-16 rounded-lg overflow-hidden border border-gray-300 dark:border-gray-600"
      >
        <img
          :src="item.previewUrl"
          class="w-full h-full object-cover"
          :alt="item.file.name"
        />
        <div
          v-if="item.uploading"
          class="absolute inset-0 bg-black/40 flex items-center justify-center"
        >
          <span class="text-white text-xs">上传中…</span>
        </div>
        <div
          v-if="item.error"
          class="absolute inset-0 bg-red-500/60 flex items-center justify-center"
        >
          <span class="text-white text-xs">失败</span>
        </div>
        <button
          v-if="!item.uploading"
          class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          @click="emit('remove-image', index)"
        >
          ✕
        </button>
      </div>
    </div>

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
        class="shrink-0"
        @click="triggerImagePicker"
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
        :model-value="input"
        type="textarea"
        :rows="1"
        :placeholder="useRag ? '输入问题，AI 将从知识库中检索相关知识… (Enter 发送，Shift+Enter 换行)' : '输入消息… (Enter 发送，Shift+Enter 换行)'"
        resize="none"
        class="flex-1"
        :disabled="streaming"
        @update:model-value="emit('update:input', $event)"
        @keydown.enter.exact.prevent="emit('send')"
      />
      <el-button
        type="primary"
        :disabled="(!input.trim() && pendingImages.length === 0) || streaming"
        @click="emit('send')"
      >
        发送
      </el-button>
    </div>
  </div>
</template>
