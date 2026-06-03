import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'

import App from './App.vue'
import router from './router'
import './style.css'
import 'element-plus/dist/index.css'
import { getToken } from './utils'
import { useUserStore } from './stores/user'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 应用启动时恢复登录态：
// - 本地有 token → 调用 fetchUser 验证有效性 → 失败则清空登录态
// - 本地无 token → 直接挂载
const userStore = useUserStore()

async function restoreAuth() {
  if (getToken()) {
    try {
      await userStore.fetchUser()
    } catch {
      // 401 响应拦截器已调用 logout() 清除 token 和用户状态
      // 此处仅吞掉异常，让应用正常挂载
    }
  }
}

restoreAuth().finally(() => {
  app.mount('#app')
})
