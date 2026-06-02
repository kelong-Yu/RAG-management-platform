import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '@/types'

// ============================================================
// 用户状态 — 全局用户信息 & 认证状态
// ============================================================
export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)

  const setUser = (u: User) => {
    user.value = u
    isAuthenticated.value = true
  }

  const logout = () => {
    user.value = null
    isAuthenticated.value = false
    localStorage.removeItem('access_token')
  }

  return {
    user,
    isAuthenticated,
    setUser,
    logout,
  }
})
