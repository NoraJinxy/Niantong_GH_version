import type { LoginRequest, LoginResponse } from '@/types'
import { api } from './client'

export const authApi = {
  login: (data: LoginRequest) => api.post<LoginResponse>('/auth/login', data),
  refresh: (refreshToken: string) =>
    api.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken }),
  // 没有 logout 端点 —— JWT 是无状态的，登出就是前端清掉本地 token；
  // 如果将来要做服务端撤销，加 refresh_token 黑名单表，那时再补回来。
  me: () => api.get('/auth/me'),
}
