import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '首页', requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册', guest: true },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/views/ChatView.vue'),
      meta: { title: '聊天', requiresAuth: true },
    },
    {
      path: '/files',
      name: 'files',
      component: () => import('@/views/FilesView.vue'),
      meta: { title: '文件管理', requiresAuth: true },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'AI Chat'}`

  const hasToken = !!getToken()

  // 需要登录的页面 → 未登录则跳转 /login
  if (to.meta.requiresAuth && !hasToken) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }

  // 游客页面（/login、/register）→ 已登录则跳转 /chat
  if (to.meta.guest && hasToken) {
    next({ name: 'chat' })
    return
  }

  next()
})

export default router
