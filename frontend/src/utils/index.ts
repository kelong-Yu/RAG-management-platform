// ============================================================
// 工具函数 — 占位，后续扩充
// ============================================================

/** 从 localStorage 读取 token */
export const getToken = (): string | null => {
  return localStorage.getItem('access_token')
}

/** 向 localStorage 写入 token */
export const setToken = (token: string): void => {
  localStorage.setItem('access_token', token)
}

/** 清除 localStorage 中的 token */
export const removeToken = (): void => {
  localStorage.removeItem('access_token')
}
