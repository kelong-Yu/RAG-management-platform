import axios from 'axios'
import type { LoginRequest, LoginResponse, RegisterRequest, User } from '@/types'
import router from '@/router'
import { removeToken } from '@/utils'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ============================================================
// 请求拦截器 — 注入 JWT token
// ============================================================

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// ============================================================
// 响应拦截器 — 401 时清除登录态并跳转
// ============================================================

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      removeToken()
      // 避免在 /login 页重复跳转
      if (router.currentRoute.value.name !== 'login') {
        window.location.replace('/login')
      }
    }
    return Promise.reject(error)
  },
)

// ============================================================
// Auth API
// ============================================================

/** 用户注册 */
export function register(data: RegisterRequest) {
  return api.post<{ message: string }>('/auth/register', data)
}

/** 用户登录 */
export function login(data: LoginRequest) {
  return api.post<LoginResponse>('/auth/login', data)
}

/** 获取当前用户信息 */
export function getMe() {
  return api.get<User>('/users/me')
}

export default api
