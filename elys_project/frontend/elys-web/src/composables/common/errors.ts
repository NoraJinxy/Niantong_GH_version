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
  return message || fallback
}
