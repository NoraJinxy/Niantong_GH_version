// 通用错误展示工具：把 axios 抛出的异常解析成给用户看的中文提示。
// 容错读取 err.response.data.detail（FastAPI 习惯）：字符串直接用；
// 校验错误数组取第一条 msg；都不命中时回落到 Error.message，最后用 fallback。

export function friendlyError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return `${fallback}：${detail}`
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | string
    const msg = typeof first === 'string' ? first : first?.msg
    if (msg) return `${fallback}：${msg}`
  }
  const message = err instanceof Error ? err.message : ''
  // axios 在网络/5xx 时只给 "Request failed with status code 500" 这类英文，对用户没意义，换成可操作的中文。
  if (/status code \d{3}/i.test(message)) return `${fallback}：接口暂时不可用，请确认后端服务或 mock API 已开启。`
  return message || fallback
}
