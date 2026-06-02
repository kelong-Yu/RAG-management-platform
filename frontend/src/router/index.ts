import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { title: '聊天', requiresAuth: true },
    },
  ],
})

// 全局前置守卫 — 标题设置 & 认证校验
router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'AI Chat'}`

  // 需要登录的页面，未登录则跳转 /login
  if (to.meta.requiresAuth && !getToken()) {
    next({ name: 'login' })
    return
  }

  next()
})

export default router
