<script setup lang="ts">
/**
 * FilesView — 文件管理页面。
 *
 * 使用可复用的 FileUpload 组件，后续可在聊天页和知识库页中直接复用该组件。
 */
import FileUpload from '@/components/FileUpload.vue'
</script>

<template>
  <div class="max-w-2xl mx-auto pt-4">
    <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-6">
      文件管理
    </h1>
    <FileUpload />
  </div>
</template>
