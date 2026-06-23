import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { authApi } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function isTokenExpired(t: string): boolean {
    try {
      const payload = JSON.parse(atob(t.split('.')[1]))
      return payload.exp * 1000 < Date.now()
    } catch {
      return true
    }
  }

  function init() {
    const saved = localStorage.getItem('elys_token')
    const savedRefresh = localStorage.getItem('elys_refresh_token')
    const savedUser = localStorage.getItem('elys_user')
    if (saved && savedUser && !isTokenExpired(saved)) {
      let parsedUser: User | null = null
      try {
        parsedUser = JSON.parse(savedUser)
      } catch {
        localStorage.removeItem('elys_user')
      }
      if (parsedUser) {
        token.value = saved
        refreshToken.value = savedRefresh
        user.value = parsedUser
      }
    } else if (saved) {
      localStorage.removeItem('elys_token')
      localStorage.removeItem('elys_refresh_token')
      localStorage.removeItem('elys_user')
    }
  }

  async function login(credentials: { username: string; password: string }) {
    loading.value = true
    error.value = null
    try {
      const res = await authApi.login(credentials)
      token.value = res.data.access_token
      refreshToken.value = res.data.refresh_token
      user.value = res.data.user
      localStorage.setItem('elys_token', res.data.access_token)
      localStorage.setItem('elys_refresh_token', res.data.refresh_token)
      localStorage.setItem('elys_user', JSON.stringify(res.data.user))
      const redirect = router.currentRoute.value.query.redirect
      let target = '/dashboard'
      if (typeof redirect === 'string' && redirect.startsWith('/')) {
        try {
          const url = new URL(redirect, window.location.origin)
          if (url.origin === window.location.origin) {
            target = url.pathname + url.search + url.hash
          }
        } catch {
          target = '/dashboard'
        }
      }
      router.push(target)
    } catch (err: any) {
      error.value = err.response?.data?.detail || '登录失败，请重试'
      throw err
    } finally {
      loading.value = false
    }
  }

  function logout() {
    // JWT 无状态：登出就是清本地 token + 跳登录页，没有后端调用。
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('elys_token')
    localStorage.removeItem('elys_refresh_token')
    localStorage.removeItem('elys_user')
    router.push('/login')
  }

  return { user, token, refreshToken, loading, error, isAuthenticated, init, login, logout }
})
