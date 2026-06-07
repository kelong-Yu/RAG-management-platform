<script setup lang="ts">
/**
 * KnowledgeView — 知识库页面。
 *
 * 展示文档列表、处理状态、切片数量，支持从 PDF 附件创建文档、重试、删除。
 * 覆盖 loading / empty / error / success 四种状态。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDocument,
  deleteDocument,
  getDocumentChunks,
  getDocumentDetail,
  getDocuments,
  reprocessDocument,
} from '@/api/documents'
import { getFiles } from '@/api/files'
import type {
  Attachment,
  Document,
  DocumentChunk,
  DocumentDetail,
} from '@/types'

// ── 状态 ──────────────────────────────────────────────────────────────

const loading = ref(false)
const error = ref<string | null>(null)
const documents = ref<Document[]>([])
const total = ref(0)

// PDF 附件列表（用于创建文档）
const pdfAttachments = ref<Attachment[]>([])
const loadingAttachments = ref(false)
const showCreateDialog = ref(false)
const creatingDocId = ref<number | null>(null)

// 文档详情抽屉
const detailDrawerVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref<string | null>(null)
const selectedDocument = ref<DocumentDetail | null>(null)
const selectedChunks = ref<DocumentChunk[]>([])

// ── 计算属性 ──────────────────────────────────────────────────────────

const isEmpty = computed(() => !loading.value && documents.value.length === 0)

// ── 方法 ──────────────────────────────────────────────────────────────

async function fetchDocuments(page = 1, pageSize = 50) {
  loading.value = true
  error.value = null
  try {
    const res = await getDocuments(page, pageSize)
    documents.value = res.data.items
    total.value = res.data.total
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载文档列表失败'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function fetchPdfAttachments() {
  loadingAttachments.value = true
  try {
    const res = await getFiles(1, 100)
    pdfAttachments.value = res.data.items.filter(
      (f) => f.mime_type === 'application/pdf' && f.source_type !== 'chat'
    )
  } catch {
    ElMessage.error('加载附件列表失败')
  } finally {
    loadingAttachments.value = false
  }
}

async function handleCreateFromAttachment(attachmentId: number) {
  creatingDocId.value = attachmentId
  try {
    await createDocument(attachmentId)
    ElMessage.success('文档创建成功，正在处理...')
    showCreateDialog.value = false
    await fetchDocuments()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '创建文档失败'
    ElMessage.error(msg)
  } finally {
    creatingDocId.value = null
  }
}

async function handleRetry(documentId: number) {
  try {
    await reprocessDocument(documentId)
    ElMessage.success('已触发重新处理')
    await fetchDocuments()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '重试失败'
    ElMessage.error(msg)
  }
}

async function handleOpenDetail(documentId: number) {
  detailDrawerVisible.value = true
  detailLoading.value = true
  detailError.value = null

  try {
    const [detailRes, chunksRes] = await Promise.all([
      getDocumentDetail(documentId),
      getDocumentChunks(documentId),
    ])
    selectedDocument.value = detailRes.data
    selectedChunks.value = chunksRes.data.items
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载文档详情失败'
    detailError.value = msg
    ElMessage.error(msg)
  } finally {
    detailLoading.value = false
  }
}

function handleCloseDetail() {
  detailDrawerVisible.value = false
  detailError.value = null
  selectedDocument.value = null
  selectedChunks.value = []
}

async function handleDelete(document: Document) {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档「${document.name}」及其所有切片吗？原始附件不会被删除。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return // 用户取消
  }

  try {
    await deleteDocument(document.id)
    ElMessage.success('已删除')
    await fetchDocuments()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '删除失败'
    ElMessage.error(msg)
  }
}

function handleOpenCreate() {
  showCreateDialog.value = true
  fetchPdfAttachments()
}

// ── 状态辅助 ──────────────────────────────────────────────────────────

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    uploaded: '待处理',
    parsing: '解析中',
    chunking: '切片中',
    embedding: '向量化中',
    ready: '就绪',
    failed: '失败',
  }
  return map[status] || status
}

function documentTypeLabel(doc: Document | DocumentDetail): string {
  if (doc.is_system) {
    return '系统内置'
  }
  const map: Record<string, string> = {
    pdf: 'PDF',
    md: 'Markdown',
    txt: '文本',
    html: 'HTML',
  }
  return map[doc.doc_type] || doc.doc_type
}

function statusType(status: string): 'info' | 'warning' | 'success' | 'danger' | '' {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger' | ''> = {
    uploaded: 'info',
    parsing: 'warning',
    chunking: 'warning',
    embedding: 'warning',
    ready: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

// ── 生命周期 ──────────────────────────────────────────────────────────

onMounted(() => {
  fetchDocuments()
})
</script>

<template>
  <div class="max-w-4xl mx-auto pt-4">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100">
        知识库
      </h1>
      <el-button type="primary" @click="handleOpenCreate">
        + 新建文档
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-16">
      <el-icon class="is-loading text-3xl text-gray-400">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="size-8"
        >
          <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
      </el-icon>
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="text-center py-16 text-red-500 dark:text-red-400"
    >
      <p class="text-lg mb-4">{{ error }}</p>
      <el-button @click="fetchDocuments()">重新加载</el-button>
    </div>

    <!-- Empty -->
    <div
      v-else-if="isEmpty"
      class="text-center py-16 text-gray-400 dark:text-gray-500"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="size-16 mx-auto mb-4 opacity-40"
      >
        <path
          d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
      <p class="text-lg mb-4">知识库中还没有文档</p>
      <p class="text-sm mb-6">
        请先在「文件管理」页面上传 PDF，然后在此创建文档
      </p>
      <el-button type="primary" @click="handleOpenCreate">
        新建第一个文档
      </el-button>
    </div>

    <!-- 文档列表 -->
    <div v-else class="space-y-3">
      <div class="text-sm text-gray-500 dark:text-gray-400 mb-2">
        共 {{ total }} 个文档
      </div>

      <div
        v-for="doc in documents"
        :key="doc.id"
        class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between gap-4"
      >
        <!-- 文档信息 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium text-gray-800 dark:text-gray-100 truncate">
              {{ doc.name }}
            </span>
            <el-tag v-if="doc.is_system" size="small" type="info">
              系统内置
            </el-tag>
          </div>
          <div class="text-xs text-gray-400 dark:text-gray-500 space-x-3">
            <span>{{ documentTypeLabel(doc) }}</span>
            <span>更新于 {{ formatTime(doc.updated_at) }}</span>
            <span v-if="doc.status === 'ready'">
              · {{ doc.chunk_count ?? 0 }} 个切片
            </span>
          </div>
          <!-- 错误信息 -->
          <div
            v-if="doc.status === 'failed' && doc.error_message"
            class="text-xs text-red-500 dark:text-red-400 mt-1 truncate"
          >
            错误：{{ doc.error_message }}
          </div>
        </div>

        <!-- 状态标签 -->
        <el-tag
          :type="statusType(doc.status)"
          size="small"
          class="shrink-0"
        >
          {{ statusLabel(doc.status) }}
        </el-tag>

        <!-- 操作 -->
        <div class="flex items-center gap-1 shrink-0">
          <el-button
            size="small"
            plain
            @click="handleOpenDetail(doc.id)"
          >
            详情
          </el-button>
          <el-button
            v-if="doc.status === 'failed' && !doc.is_system"
            size="small"
            @click="handleRetry(doc.id)"
          >
            重试
          </el-button>
          <el-button
            v-if="doc.is_deletable"
            size="small"
            type="danger"
            plain
            @click="handleDelete(doc)"
          >
            删除
          </el-button>
          <el-tag v-else type="info" class=" mx-1 ml-3">
            只读
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 文档详情抽屉 -->
    <el-drawer
      :model-value="detailDrawerVisible"
      title="文档详情"
      size="50%"
      @close="handleCloseDetail"
    >
      <div v-if="detailLoading" class="flex justify-center py-12">
        <el-icon class="is-loading text-2xl text-gray-400">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="size-6"
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </el-icon>
      </div>

      <div
        v-else-if="detailError"
        class="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-500"
      >
        {{ detailError }}
      </div>

      <div v-else-if="selectedDocument" class="space-y-6">
        <div class="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/60">
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100 break-all">
                {{ selectedDocument.name }}
              </h3>
              <div class="mt-2 space-y-1 text-sm text-gray-500 dark:text-gray-400">
                <p>状态：{{ statusLabel(selectedDocument.status) }}</p>
                <p>切片数量：{{ selectedDocument.chunk_count }}</p>
                <p>文档类型：{{ documentTypeLabel(selectedDocument) }}</p>
                <p v-if="selectedDocument.is_system">
                  权限：系统内置文件，仅支持查看详情和参与检索
                </p>
                <p>创建时间：{{ formatTime(selectedDocument.created_at) }}</p>
                <p>更新时间：{{ formatTime(selectedDocument.updated_at) }}</p>
              </div>
            </div>
            <el-tag :type="statusType(selectedDocument.status)" size="small">
              {{ statusLabel(selectedDocument.status) }}
            </el-tag>
          </div>
          <div
            v-if="selectedDocument.error_message"
            class="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-500"
          >
            {{ selectedDocument.error_message }}
          </div>
        </div>

        <div>
          <div class="mb-3 flex items-center justify-between">
            <h4 class="text-base font-medium text-gray-800 dark:text-gray-100">
              切片预览
            </h4>
            <el-button
              size="small"
              plain
              @click="handleOpenDetail(selectedDocument.id)"
            >
              刷新
            </el-button>
          </div>

          <div
            v-if="selectedChunks.length === 0"
            class="rounded border border-dashed border-gray-300 px-4 py-8 text-center text-sm text-gray-400 dark:border-gray-600 dark:text-gray-500"
          >
            当前文档暂无切片数据
          </div>

          <div v-else class="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
            <div
              v-for="chunk in selectedChunks"
              :key="chunk.id"
              class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
            >
              <div class="mb-2 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
                <span>切片 #{{ chunk.chunk_index }}</span>
                <span v-if="chunk.page_number !== null">页码 {{ chunk.page_number }}</span>
                <span>{{ formatTime(chunk.created_at) }}</span>
              </div>
              <pre class="whitespace-pre-wrap wrap-break-word text-sm leading-6 text-gray-700 dark:text-gray-200 font-sans">{{ chunk.content }}</pre>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 新建文档对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="从 PDF 附件创建文档"
      width="520px"
    >
      <div v-if="loadingAttachments" class="text-center py-8">
        <el-icon class="is-loading text-2xl text-gray-400">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="size-6"
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </el-icon>
      </div>

      <div v-else-if="pdfAttachments.length === 0" class="text-center py-8 text-gray-400">
        <p>暂无可用的 PDF 附件</p>
        <p class="text-sm mt-1">请先在「文件管理」页面上传 PDF</p>
      </div>

      <div v-else class="space-y-2 max-h-80 overflow-y-auto">
        <div
          v-for="att in pdfAttachments"
          :key="att.id"
          class="flex items-center justify-between p-3 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <div class="flex-1 min-w-0">
            <div class="text-sm truncate font-medium">{{ att.file_name }}</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ (att.file_size / 1024).toFixed(1) }} KB · {{ formatTime(att.created_at) }}
            </div>
          </div>
          <el-button
            size="small"
            type="primary"
            :loading="creatingDocId === att.id"
            @click="handleCreateFromAttachment(att.id)"
          >
            创建文档
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
