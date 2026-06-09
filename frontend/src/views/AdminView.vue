<script setup lang="ts">
/**
 * AdminView — 管理员控制台。
 *
 * 管理用户、知识库文档，并支持同步系统默认知识库。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteAdminDocument,
  deleteAdminUser,
  getAdminDocuments,
  getAdminUsers,
  syncDefaultKnowledgeBase,
  updateAdminUser,
} from '@/api/admin'
import { useUserStore } from '@/stores/user'
import type { AdminDocument, AdminUser } from '@/types'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const syncingDefault = ref(false)
const users = ref<AdminUser[]>([])
const documents = ref<AdminDocument[]>([])
const documentTotal = ref(0)
const error = ref<string | null>(null)

const isAdmin = computed(() => userStore.user?.role === 'admin')

async function fetchAdminData() {
  if (!isAdmin.value) {
    ElMessage.error('需要管理员权限')
    router.push('/chat')
    return
  }

  loading.value = true
  error.value = null
  try {
    const [userRes, docRes] = await Promise.all([
      getAdminUsers(),
      getAdminDocuments(),
    ])
    users.value = userRes.data
    documents.value = docRes.data.items
    documentTotal.value = docRes.data.total
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载管理员数据失败'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleToggleActive(user: AdminUser) {
  try {
    const res = await updateAdminUser(user.id, { is_active: !user.is_active })
    users.value = users.value.map((item) => (item.id === user.id ? res.data : item))
    ElMessage.success(res.data.is_active ? '已启用账号' : '已禁用账号')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新用户失败')
  }
}

async function handleRoleChange(user: AdminUser, role: 'user' | 'admin') {
  try {
    const res = await updateAdminUser(user.id, { role })
    users.value = users.value.map((item) => (item.id === user.id ? res.data : item))
    ElMessage.success('角色已更新')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新角色失败')
    await fetchAdminData()
  }
}

async function handleDeleteUser(user: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${user.username}」吗？已有业务数据的用户不能直接删除。`,
      '删除用户',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await deleteAdminUser(user.id)
    users.value = users.value.filter((item) => item.id !== user.id)
    ElMessage.success('用户已删除')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除用户失败')
  }
}

async function handleSyncDefaultKnowledgeBase() {
  syncingDefault.value = true
  try {
    await syncDefaultKnowledgeBase()
    ElMessage.success('默认知识库已同步')
    await fetchAdminData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '同步默认知识库失败')
  } finally {
    syncingDefault.value = false
  }
}

async function handleDeleteDocument(document: AdminDocument) {
  if (!document.is_deletable) {
    ElMessage.info('系统内置知识库文件禁止删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除知识库文档「${document.name}」吗？`,
      '删除文档',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  try {
    await deleteAdminDocument(document.id)
    await fetchAdminData()
    ElMessage.success('文档已删除')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除文档失败')
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchAdminData()
})
</script>

<template>
  <div class="max-w-6xl mx-auto space-y-8 pt-4">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100">
        管理员控制台
      </h1>
      <el-button :loading="loading" @click="fetchAdminData">
        刷新
      </el-button>
    </div>

    <div
      v-if="error"
      class="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-500"
    >
      {{ error }}
    </div>

    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
          用户管理
        </h2>
        <span class="text-sm text-gray-500">共 {{ users.length }} 个用户</span>
      </div>

      <el-table v-loading="loading" :data="users" border >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="角色" width="150" >
          <template #default="{ row }">
            <el-select
              v-model="row.role"
              size="small"
              @change="handleRoleChange(row, row.role)"
            >
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" >
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" >
          <template #default="{ row }">
            <div >
              <el-button size="small" @click="handleToggleActive(row)">
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="row.username === 'admin' || row.id === userStore.user?.id"
                @click="handleDeleteUser(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="space-y-3">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">
            知识库管理
          </h2>
          <p class="text-sm text-gray-500">
            共 {{ documentTotal }} 个文档，系统内置默认知识库禁止删除
          </p>
        </div>
        <el-button
          type="primary"
          :loading="syncingDefault"
          @click="handleSyncDefaultKnowledgeBase"
        >
          同步默认知识库
        </el-button>
      </div>

      <el-table v-loading="loading" :data="documents" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="文档名" min-width="220" />
        <el-table-column label="归属" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" size="small" type="info">
              系统内置
            </el-tag>
            <span v-else>{{ row.owner_username || `用户 ${row.user_id}` }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doc_type" label="类型" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="切片" width="90">
          <template #default="{ row }">
            {{ row.chunk_count ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="180">
          <template #default="{ row }">
            {{ formatTime(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="danger"
              plain
              :disabled="!row.is_deletable"
              @click="handleDeleteDocument(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>
