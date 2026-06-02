import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '@/types'
import { getMe as getMeApi, login as loginApi, register as registerApi } from '@/api/auth'
import { removeToken, setToken } from '@/utils'

// ============================================================
// 用户状态 — 全局用户信息 & 认证状态
// ============================================================
export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)

  /** 设置当前用户 */
  const setUser = (u: User) => {
    user.value = u
    isAuthenticated.value = true
  }

  /** 退出登录 */
  const logout = () => {
    user.value = null
    isAuthenticated.value = false
    removeToken()
  }

  /** 注册 */
  const register = async (username: string, email: string, password: string) => {
    await registerApi({ username, email, password })
  }

  /** 登录 — 保存 token 并拉取用户信息 */
  const login = async (username: string, password: string) => {
    const res = await loginApi({ username, password })
    setToken(res.data.access_token)
    const userRes = await getMeApi()
    setUser(userRes.data)
  }

  /** 从服务端刷新当前用户信息（用于页面刷新恢复登录态） */
  const fetchUser = async () => {
    try {
      const res = await getMeApi()
      setUser(res.data)
    } catch {
      logout()
    }
  }

  return {
    user,
    isAuthenticated,
    setUser,
    logout,
    register,
    login,
    fetchUser,
  }
})
