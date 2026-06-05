<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  visible: boolean
  title: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'update:title', value: string): void
  (e: 'save'): void
  (e: 'closed'): void
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const dialogTitle = computed({
  get: () => props.title,
  set: (value: string) => emit('update:title', value),
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    title="重命名会话"
    width="420px"
    @closed="emit('closed')"
  >
    <el-input
      v-model="dialogTitle"
      maxlength="100"
      show-word-limit
      placeholder="输入新的会话标题"
      @keydown.enter.prevent="emit('save')"
    />
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        :disabled="!dialogTitle.trim()"
        @click="emit('save')"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
