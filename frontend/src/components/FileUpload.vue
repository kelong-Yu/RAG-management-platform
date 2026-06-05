<script setup lang="ts">
/**
 * FileUpload — 统一文件上传组件（图片 & PDF）。
 *
 * 可复用于聊天页和知识库页，内置拖拽/选择、前端预校验、
 * 上传进度展示、成功后列表 + 删除。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadFile, getFiles, deleteFile as deleteFileApi } from '@/api/files'
import type { Attachment, UploadStatus } from '@/types'

// ---- Props ----

const props = withDefaults(
  defineProps<{
    /** 允许的 MIME 类型列表，不传则默认支持图片 + PDF */
    allowedMimeTypes?: string[]
    /** 最大文件大小（MB），默认从环境变量读取或使用 20 */
    maxSizeMB?: number
  }>(),
  {
    allowedMimeTypes: () => [
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'application/pdf',
    ],
    maxSizeMB: 20,
  },
)

const emit = defineEmits<{
  (e: 'uploaded', attachment: Attachment): void
  (e: 'deleted', id: number): void
}>()

// ---- 状态 ----

const attachments = ref<Attachment[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const dragOver = ref(false)
const uploadingFiles = ref<Map<number, UploadStatus>>(new Map()) // 用临时 id 追踪

// ---- 允许的扩展名 ----

const allowedExtensions = computed(() => {
  const map: Record<string, string> = {
    'image/jpeg': '.jpg, .jpeg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
  }
  return props.allowedMimeTypes.map((m) => map[m] || m).join(', ')
})

// ---- 方法 ----

async function fetchList() {
  loading.value = true
  error.value = null
  try {
    const res = await getFiles()
    attachments.value = res.data.items
  } catch {
    error.value = '获取文件列表失败，请检查网络后重试'
    ElMessage.error('获取文件列表失败')
  } finally {
    loading.value = false
  }
}

/** 前端预校验 */
function validateFile(file: File): string | null {
  // 大小
  const maxBytes = props.maxSizeMB * 1024 * 1024
  if (file.size > maxBytes) {
    const mb = (file.size / 1024 / 1024).toFixed(1)
    return `文件 ${file.name} 大小为 ${mb} MB，超过 ${props.maxSizeMB} MB 限制`
  }
  // 类型
  if (!props.allowedMimeTypes.includes(file.type)) {
    return `不支持的文件类型: ${file.type || '未知'}`
  }
  return null
}

async function handleFiles(files: FileList | File[]) {
  const fileArr = Array.from(files)
  for (const file of fileArr) {
    const error = validateFile(file)
    if (error) {
      ElMessage.warning(error)
      continue
    }

    const tempId = Date.now() + Math.random()
    uploadingFiles.value.set(tempId, 'uploading')
    try {
      const res = await uploadFile(file)
      attachments.value.unshift(res.data)
      uploadingFiles.value.set(tempId, 'success')
      emit('uploaded', res.data)
    } catch (err: unknown) {
      uploadingFiles.value.set(tempId, 'error')
      const msg =
        err instanceof Error ? err.message : '上传失败，请重试'
      // 从 axios error 中提取 detail
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail
      ElMessage.error(detail || msg)
    }
    // 3s 后清除上传状态
    setTimeout(() => uploadingFiles.value.delete(tempId), 3000)
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    handleFiles(e.dataTransfer.files)
  }
}

function onFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    handleFiles(target.files)
    target.value = '' // 重置以允许重复选择同一文件
  }
}

async function handleDelete(attachment: Attachment) {
  try {
    await deleteFileApi(attachment.id)
    attachments.value = attachments.value.filter((a) => a.id !== attachment.id)
    emit('deleted', attachment.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function isImage(mime: string): boolean {
  return mime.startsWith('image/')
}

function uploadingCount(): number {
  let count = 0
  uploadingFiles.value.forEach((s) => {
    if (s === 'uploading') count++
  })
  return count
}

// ---- 初始化 ----

onMounted(() => {
  fetchList()
})
</script>

<template>
  <div class="file-upload">
    <!-- ============================== -->
    <!-- 拖拽/选择上传区               -->
    <!-- ============================== -->
    <div
      class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors"
      :class="{
        'border-blue-400 bg-blue-50 dark:bg-blue-900/10': dragOver,
        'border-gray-300 dark:border-gray-600 hover:border-blue-400':
          !dragOver,
      }"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
      @click="($refs.fileInput as HTMLInputElement)?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        :accept="props.allowedMimeTypes.join(',')"
        multiple
        class="hidden"
        @change="onFileInput"
      />

      <!-- idle -->
      <div v-if="uploadingCount() === 0">
        <el-icon :size="36" class="text-gray-400 mb-2">
          <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
            <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" />
          </svg>
        </el-icon>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          拖拽文件到此处，或点击选择文件
        </p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          支持 {{ allowedExtensions }}，单文件最大 {{ maxSizeMB }} MB
        </p>
      </div>

      <!-- uploading -->
      <div v-else>
        <el-icon :size="36" class="text-blue-500 mb-2 animate-spin">
          <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
            <path
              d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"
            />
          </svg>
        </el-icon>
        <p class="text-sm text-blue-600 dark:text-blue-400">正在上传…</p>
      </div>
    </div>

    <!-- ============================== -->
    <!-- 文件列表                       -->
    <!-- ============================== -->
    <div class="mt-4">
      <!-- loading -->
      <div
        v-if="loading"
        class="text-center py-6 text-sm text-gray-400"
      >
        加载中…
      </div>

      <!-- error -->
      <div
        v-else-if="error"
        class="text-center py-6"
      >
        <p class="text-sm text-red-500 dark:text-red-400 mb-3">{{ error }}</p>
        <el-button size="small" @click="fetchList()">重新加载</el-button>
      </div>

      <!-- empty -->
      <div
        v-else-if="attachments.length === 0"
        class="text-center py-6 text-sm text-gray-400"
      >
        暂无上传文件
      </div>

      <!-- list -->
      <div v-else class="space-y-2">
        <div
          v-for="att in attachments"
          :key="att.id"
          class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:shadow-sm transition-shadow"
        >
          <!-- 文件图标 -->
          <div class="shrink-0 w-10 h-10 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
            <!-- 图片类型 -->
            <el-icon v-if="isImage(att.mime_type)" :size="20" class="text-blue-400">
              <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
                <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" />
              </svg>
            </el-icon>
            <!-- PDF/文档类型 -->
            <el-icon v-else :size="20" class="text-red-400">
              <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
                <path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-1.5v2H13V7h1.5c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z" />
              </svg>
            </el-icon>
          </div>

          <!-- 文件信息 -->
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-700 dark:text-gray-200 truncate">
              {{ att.file_name }}
            </p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              {{ formatSize(att.file_size) }}
              ·
              {{ att.mime_type }}
              ·
              {{ new Date(att.created_at).toLocaleString('zh-CN') }}
            </p>
          </div>

          <!-- 删除按钮 -->
          <el-button
            size="small"
            text
            type="danger"
            @click="handleDelete(att)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.file-upload {
  @apply w-full;
}
</style>
