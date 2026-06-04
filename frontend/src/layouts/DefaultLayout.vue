<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
    <!-- 顶部导航 -->
    <header class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <nav class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
        <!-- 品牌 -->
        <router-link to="/" class="text-xl font-bold text-gray-800 dark:text-gray-100 hover:text-blue-600 transition-colors">
          AI Chat
        </router-link>

        <!-- 右侧操作 -->
        <div class="flex items-center gap-4">
          <template v-if="userStore.isAuthenticated">
            <span class="text-sm text-gray-600 dark:text-gray-300">
              {{ userStore.user?.username }}
            </span>
            <router-link
              to="/chat"
              class="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              聊天
            </router-link>
            <router-link
              to="/files"
              class="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              文件
            </router-link>
            <router-link
              to="/knowledge"
              class="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              知识库
            </router-link>
            <button
              class="text-sm text-gray-600 dark:text-gray-300 hover:text-red-500 transition-colors cursor-pointer"
              @click="handleLogout"
            >
              退出
            </button>
          </template>
          <template v-else>
            <router-link
              to="/login"
              class="text-sm text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              登录
            </router-link>
          </template>
        </div>
      </nav>
    </header>

    <!-- 主内容区 -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <router-view />
    </main>
  </div>
</template>
