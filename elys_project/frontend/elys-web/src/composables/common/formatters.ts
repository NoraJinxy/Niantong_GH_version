// 通用展示格式化工具（与具体业务无关，多页共用）。
// 业务专用的格式化在 composables/<feature>/<feature>Formatters.ts，别往这里堆。

// 把后端 ISO 时间串渲染成 zh-CN 本地时间（年-月-日 时:分）。
// 空值 → '暂无'；不可解析 → 原样返回。
export function formatDateTime(value?: string | null): string {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
