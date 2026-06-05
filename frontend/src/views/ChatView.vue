<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import ChatHeader from '@/components/chat/ChatHeader.vue'
import ChatInputPanel from '@/components/chat/ChatInputPanel.vue'
import ConversationSidebar from '@/components/chat/ConversationSidebar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import RenameConversationDialog from '@/components/chat/RenameConversationDialog.vue'
import { useChatImages } from '@/composables/chat/useChatImages'
import { useChatStream } from '@/composables/chat/useChatStream'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage, Citation, ImageMeta } from '@/types'

const RAG_STORAGE_KEY = 'chat:useRag'
const CITATIONS_STORAGE_KEY = 'chat:citations'

const chatStore = useChatStore()
const {
  conversations,
  currentConversationId,
  messages,
  loadingConversations,
  loadingMessages,
} = storeToRefs(chatStore)

const input = ref('')
const messageArea = ref<HTMLElement>()
const sidebarVisible = ref(true)
const useRag = ref(localStorage.getItem(RAG_STORAGE_KEY) === 'true')
const messageCitations = ref<Record<number, Citation[]>>(
  (() => {
    const raw = localStorage.getItem(CITATIONS_STORAGE_KEY)
    if (!raw) return {}
    try {
      return JSON.parse(raw) as Record<number, Citation[]>
    } catch {
      return {}
    }
  })(),
)
const renameDialogVisible = ref(false)
const renameTitle = ref('')
const renameConversationId = ref<number | null>(null)

const currentConversationTitle = computed(() =>
  conversations.value.find((conversation) => conversation.id === currentConversationId.value)?.title || '新对话'
)

const {
  pendingImages,
  messageImages,
  imageBlobCache,
  visionCapable,
  fetchVisionCapability,
  handleImageFilesSelected,
  removePendingImage,
  clearPendingImages,
  uploadPendingImages,
} = useChatImages(messages)

const { streaming, streamAssistantReply } = useChatStream({
  chatStore,
  messageCitations,
  messageImages,
  visionCapable,
  scrollToBottom,
})

onMounted(async () => {
  await fetchVisionCapability()
  await chatStore.fetchConversations()

  if (
    currentConversationId.value &&
    conversations.value.some((conversation) => conversation.id === currentConversationId.value)
  ) {
    await chatStore.switchConversation(currentConversationId.value)
  } else if (conversations.value.length > 0) {
    await chatStore.switchConversation(conversations.value[0].id)
  } else {
    chatStore.beginDraftConversation()
  }

  scrollToBottom()
})

watch(useRag, (value) => {
  localStorage.setItem(RAG_STORAGE_KEY, String(value))
})

watch(
  messageCitations,
  (value) => {
    localStorage.setItem(CITATIONS_STORAGE_KEY, JSON.stringify(value))
  },
  { deep: true },
)

function scrollToBottom() {
  nextTick(() => {
    if (messageArea.value) {
      messageArea.value.scrollTop = messageArea.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = input.value.trim()
  const hasImages = pendingImages.value.length > 0
  if ((!text && !hasImages) || streaming.value) return

  let attachmentIds: number[] = []
  let uploadedImages: ImageMeta[] = []

  if (hasImages) {
    try {
      const uploaded = await uploadPendingImages()
      attachmentIds = uploaded.attachmentIds
      uploadedImages = uploaded.uploadedImages
    } catch {
      return
    }
  }

  const userMsgId = Date.now()
  const userMessage: ChatMessage = {
    id: userMsgId,
    role: 'user',
    content: text || '[图片]',
    extra_data: attachmentIds.length > 0 ? { attachment_ids: attachmentIds } : undefined,
    created_at: new Date().toISOString(),
  }

  chatStore.appendMessage(userMessage)

  if (uploadedImages.length > 0) {
    messageImages.value[userMsgId] = uploadedImages
  }

  clearPendingImages()
  input.value = ''
  scrollToBottom()

  await streamAssistantReply({
    message: text || '[图片]',
    conversationId: currentConversationId.value,
    useRag: useRag.value,
    attachmentIds,
  })
}

async function handleSwitchConversation(id: number) {
  if (streaming.value) return
  await chatStore.switchConversation(id)
  scrollToBottom()
}

function handleNewConversation() {
  if (streaming.value) return
  chatStore.beginDraftConversation()
  scrollToBottom()
}

async function handleDeleteConversation(id: number) {
  if (streaming.value) return

  try {
    await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await chatStore.removeConversation(id)
    ElMessage.success('已删除')
    scrollToBottom()
  } catch {
    // 用户取消
  }
}

function openRenameDialog(conversationId?: number, title?: string) {
  const targetId = conversationId ?? currentConversationId.value
  if (!targetId) return

  renameConversationId.value = targetId
  renameTitle.value = title ?? currentConversationTitle.value
  renameDialogVisible.value = true
}

async function handleRenameConversation() {
  const currentId = renameConversationId.value
  const nextTitle = renameTitle.value.trim()
  if (!currentId || !nextTitle) return

  try {
    await chatStore.renameConversation(currentId, nextTitle)
    renameDialogVisible.value = false
    renameConversationId.value = null
    ElMessage.success('已更新会话标题')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '重命名失败'
    ElMessage.error(message)
  }
}

function handleCloseRenameDialog() {
  renameDialogVisible.value = false
  renameConversationId.value = null
  renameTitle.value = ''
}
</script>

<template>
  <div class="flex h-[calc(100vh-7rem)] gap-0">
    <ConversationSidebar
      :visible="sidebarVisible"
      :conversations="conversations"
      :current-conversation-id="currentConversationId"
      :loading="loadingConversations"
      :streaming="streaming"
      @new-conversation="handleNewConversation"
      @switch-conversation="handleSwitchConversation"
      @delete-conversation="handleDeleteConversation"
      @rename-conversation="openRenameDialog"
    />

    <div class="flex-1 flex flex-col min-w-0">
      <ChatHeader
        :current-conversation-title="currentConversationTitle"
        :use-rag="useRag"
        :streaming="streaming"
        @toggle-sidebar="sidebarVisible = !sidebarVisible"
        @toggle-rag="useRag = !useRag"
      />

      <div ref="messageArea" class="flex-1 overflow-y-auto">
        <MessageList
          :messages="messages"
          :loading="loadingMessages"
          :streaming="streaming"
          :use-rag="useRag"
          :citations="messageCitations"
          :message-images="messageImages"
          :image-blob-cache="imageBlobCache"
        />
      </div>

      <ChatInputPanel
        :input="input"
        :use-rag="useRag"
        :streaming="streaming"
        :pending-images="pendingImages"
        :vision-capable="visionCapable"
        @update:input="input = $event"
        @send="sendMessage"
        @remove-image="removePendingImage"
        @image-files-selected="handleImageFilesSelected"
      />
    </div>

    <RenameConversationDialog
      v-model:visible="renameDialogVisible"
      v-model:title="renameTitle"
      @save="handleRenameConversation"
      @closed="handleCloseRenameDialog"
    />
  </div>
</template>
