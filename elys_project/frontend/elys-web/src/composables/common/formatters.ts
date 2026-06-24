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

// 短时间（月-日 时:分，不含年）。列表 / 卡片里省空间用。空值 → '暂无时间'。
export function formatShortDate(value?: string | null): string {
  if (!value) return '暂无时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无时间'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 相对时间：刚刚 / N 分钟前 / N 小时前（仅当天）；更久或跨天回落到 formatShortDate。
export function formatRelativeTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  const diffMs = Date.now() - date.getTime()
  if (!Number.isFinite(diffMs)) return ''
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 0) return formatShortDate(value)
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24 && date.toDateString() === new Date().toDateString()) {
    return `${diffH} 小时前`
  }
  return formatShortDate(value)
}

// 绝对时间（年-月-日 时:分:秒），用于 hover 的精确时间提示。
export function formatAbsoluteTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const HH = String(date.getHours()).padStart(2, '0')
  const MM = String(date.getMinutes()).padStart(2, '0')
  const SS = String(date.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${HH}:${MM}:${SS}`
}

// ISO 串 → 毫秒时间戳（排序用）；空 / 不可解析 → 0。
export function timestamp(value?: string | null): number {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

// 字节数 → 人类可读体积（含 GB 档）。真 0 字节 → '0 B'；空 / NaN → '未知大小'。
export function formatFileSize(bytes?: number | null): string {
  if (bytes == null || Number.isNaN(bytes)) return '未知大小'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}
