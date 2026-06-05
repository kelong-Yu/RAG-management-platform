import { ElMessage } from 'element-plus'
import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

import { getChatCapabilities } from '@/api/chat'
import { uploadFile } from '@/api/files'
import type { ChatMessage, ImageMeta } from '@/types'
import { getToken } from '@/utils'

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
const MAX_IMAGE_SIZE = 20 * 1024 * 1024

export interface PendingImageItem {
  file: File
  previewUrl: string
  uploading: boolean
  attachmentId: number | null
  error: string | null
}

function revokePreviewUrl(url: string) {
  URL.revokeObjectURL(url)
}

function extractAttachmentIds(message: ChatMessage): number[] {
  const extra = message.extra_data
  if (!extra || typeof extra !== 'object') return []

  const attachmentIds = (extra as Record<string, unknown>).attachment_ids
  if (!Array.isArray(attachmentIds)) return []

  return attachmentIds.filter(
    (id): id is number => typeof id === 'number' && Number.isFinite(id),
  )
}

export function useChatImages(messages: Ref<ChatMessage[]>) {
  const pendingImages = ref<PendingImageItem[]>([])
  const messageImages = ref<Record<number, ImageMeta[]>>({})
  const imageBlobCache = ref<Record<number, string>>({})
  const visionCapable = ref(false)

  watch(
    messageImages,
    async (imagesMap) => {
      for (const images of Object.values(imagesMap)) {
        for (const image of images) {
          if (!imageBlobCache.value[image.attachment_id]) {
            try {
              await loadImageBlobUrl(image.attachment_id)
            } catch {
              imageBlobCache.value[image.attachment_id] = ''
            }
          }
        }
      }
    },
    { deep: true },
  )

  watch(
    messages,
    (nextMessages) => {
      hydrateMessageImagesFromMessages(nextMessages)
    },
    { deep: true, immediate: true },
  )

  onBeforeUnmount(() => {
    clearPendingImages()
    Object.values(imageBlobCache.value).forEach((url) => {
      if (url) {
        revokePreviewUrl(url)
      }
    })
  })

  async function fetchVisionCapability() {
    try {
      const capabilitiesRes = await getChatCapabilities()
      visionCapable.value = capabilitiesRes.data.vision_capable
    } catch {
      // 能力查询失败时保持默认 false，避免阻塞聊天页初始化
    }
  }

  function handleImageFilesSelected(files: FileList | File[] | null) {
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        ElMessage.warning(`不支持的文件类型: ${file.name}`)
        continue
      }

      if (file.size > MAX_IMAGE_SIZE) {
        ElMessage.warning(`文件过大 (${(file.size / 1024 / 1024).toFixed(1)}MB): ${file.name}`)
        continue
      }

      pendingImages.value.push({
        file,
        previewUrl: URL.createObjectURL(file),
        uploading: false,
        attachmentId: null,
        error: null,
      })
    }
  }

  function removePendingImage(index: number) {
    const item = pendingImages.value[index]
    if (!item) return

    revokePreviewUrl(item.previewUrl)
    pendingImages.value.splice(index, 1)
  }

  function clearPendingImages() {
    pendingImages.value.forEach((item) => {
      revokePreviewUrl(item.previewUrl)
    })
    pendingImages.value = []
  }

  async function uploadPendingImages() {
    const attachmentIds: number[] = []
    const uploadedImages: ImageMeta[] = []

    for (const item of pendingImages.value) {
      item.uploading = true
      item.error = null

      try {
        const res = await uploadFile(item.file)
        item.attachmentId = res.data.id
        attachmentIds.push(res.data.id)
        uploadedImages.push({
          attachment_id: res.data.id,
          file_name: res.data.file_name,
          mime_type: res.data.mime_type,
          file_size: res.data.file_size,
          is_image: true,
        })
        item.uploading = false
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : '上传失败'
        item.error = message
        item.uploading = false
        ElMessage.error(`图片上传失败: ${message}`)
        throw error
      }
    }

    return { attachmentIds, uploadedImages }
  }

  async function retryUpload(index: number): Promise<ImageMeta | null> {
    const item = pendingImages.value[index]
    if (!item || item.attachmentId) return null

    item.uploading = true
    item.error = null

    try {
      const res = await uploadFile(item.file)
      item.attachmentId = res.data.id
      item.uploading = false
      const meta: ImageMeta = {
        attachment_id: res.data.id,
        file_name: res.data.file_name,
        mime_type: res.data.mime_type,
        file_size: res.data.file_size,
        is_image: true,
      }
      return meta
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '上传失败'
      item.error = message
      item.uploading = false
      ElMessage.error(`重试上传失败: ${message}`)
      return null
    }
  }

  async function loadImageBlobUrl(attachmentId: number): Promise<string> {
    if (imageBlobCache.value[attachmentId]) {
      return imageBlobCache.value[attachmentId]
    }

    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const token = getToken()
    const response = await fetch(`${baseURL}/files/${attachmentId}/raw`, {
      headers: { Authorization: `Bearer ${token}` },
    })

    if (!response.ok) {
      throw new Error(`图片加载失败 (${response.status})`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    imageBlobCache.value[attachmentId] = url
    return url
  }

  function getImageMeta(messageId: number): ImageMeta[] {
    return messageImages.value[messageId] || []
  }

  function hydrateMessageImagesFromMessages(nextMessages: ChatMessage[]) {
    for (const message of nextMessages) {
      const attachmentIds = extractAttachmentIds(message)
      if (attachmentIds.length === 0) continue
      if (messageImages.value[message.id]?.length) continue

      messageImages.value[message.id] = attachmentIds.map((attachmentId) => ({
        attachment_id: attachmentId,
        file_name: `image-${attachmentId}`,
        mime_type: 'image/*',
        file_size: 0,
        is_image: true,
      }))
    }
  }

  return {
    pendingImages,
    messageImages,
    imageBlobCache,
    visionCapable,
    fetchVisionCapability,
    handleImageFilesSelected,
    removePendingImage,
    clearPendingImages,
    uploadPendingImages,
    retryUpload,
    getImageMeta,
  }
}
