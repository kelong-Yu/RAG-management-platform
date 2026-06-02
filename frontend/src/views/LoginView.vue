<script setup lang="ts">
</script>

<template>
  <div class="flex items-center justify-center min-h-[60vh]">
    <div class="w-full max-w-md p-8 space-y-6 bg-white dark:bg-gray-800 rounded-xl shadow-lg">
      <h2 class="text-2xl font-semibold text-center text-gray-800 dark:text-gray-100">
        用户登录
      </h2>

      <form class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            用户名
          </label>
          <input
            type="text"
            placeholder="请输入用户名"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                   placeholder-gray-400 dark:placeholder-gray-500"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            密码
          </label>
          <input
            type="password"
            placeholder="请输入密码"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                   placeholder-gray-400 dark:placeholder-gray-500"
          />
        </div>

        <button
          type="submit"
          class="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium
                 rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2
                 focus:ring-blue-500 focus:ring-offset-2"
        >
          登录
        </button>
      </form>

      <p class="text-sm text-center text-gray-500 dark:text-gray-400">
        还没有账号？
        <a href="#" class="text-blue-600 hover:text-blue-500">立即注册</a>
      </p>
    </div>
  </div>
</template>
