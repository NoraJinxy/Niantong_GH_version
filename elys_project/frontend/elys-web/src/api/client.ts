import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
export const DATA_API_BASE_URL = import.meta.env.VITE_DATA_API_BASE_URL || API_BASE_URL

const ACCESS_TOKEN_KEY = 'elys_token'
const REFRESH_TOKEN_KEY = 'elys_refresh_token'
const USER_KEY = 'elys_user'

// 默认 30s：10s 太紧（pipeline 运行触发 / 校验 / 多表 join 查询都可能超过 10s）。
// 真正的长跑请求（数据上传 / 导出等）走 dataApi（120s）或单独传 timeout。
function createClient(baseURL: string, timeout = 30000) {
  const client = axios.create({
    baseURL,
    timeout,
    headers: { 'Content-Type': 'application/json' },
  })

  client.interceptors.request.use((config) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    return config
  })

  client.interceptors.response.use(
    (res) => res,
    async (error) => {
      const originalRequest = error.config as typeof error.config & { _retry?: boolean }
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

      if (error.response?.status === 401 && refreshToken && !originalRequest?._retry) {
        originalRequest._retry = true
        try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          localStorage.setItem(ACCESS_TOKEN_KEY, res.data.access_token)
          localStorage.setItem(REFRESH_TOKEN_KEY, res.data.refresh_token)
          localStorage.setItem(USER_KEY, JSON.stringify(res.data.user))
          originalRequest.headers.Authorization = `Bearer ${res.data.access_token}`
          return client(originalRequest)
        } catch {
          // Fall through to logout cleanup below.
        }
      }

      if (error.response?.status === 401) {
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        window.location.href = '/login'
      }
      return Promise.reject(error)
    },
  )

  return client
}

export const api = createClient(API_BASE_URL)
export const dataApi = createClient(DATA_API_BASE_URL, 120000)
