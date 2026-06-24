// 数据集页 · 纯展示 / 格式化辅助
//
// 从 DatasetsPage.vue 抽出的无状态函数：日期 / 时长 / 文件体量格式化、可见范围与质控
// 状态的标签与配色、文件角色归类、错误消息提取等。全部为纯函数（不依赖组件 ref），
// 是上帝组件拆分的第一刀（零响应式风险）。镜像 composables/pipeline/pipelineFormatters.ts。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 1。

import type { DatasetFile, Recording } from '@/types'

export type DatasetFileRoleFilter = 'all' | 'original' | 'raw-bids' | 'canonical-fif' | 'other'

// ===== 通用 =====

export function queryString(value: unknown) {
  if (Array.isArray(value)) return typeof value[0] === 'string' ? value[0] : ''
  return typeof value === 'string' ? value : ''
}

export function sanitizeCode(value: string) {
  return value
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^A-Za-z0-9-_]/g, '')
    .replace(/-+/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
}

export function getDateValue(value?: string | null) {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

// ===== 日期 / 时长 / 体量 =====

export function formatDate(value?: string | null) {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// UI Phase (docs_v2/6-05): 数据概要展示用 helper
export function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '0 分'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (hours < 24) return mins ? `${hours} 时 ${mins} 分` : `${hours} 时`
  const days = Math.floor(hours / 24)
  const h = hours % 24
  return h ? `${days} 天 ${h} 时` : `${days} 天`
}

export function formatRelative(value?: string | null): string {
  if (!value) return '尚未导入'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const diffMs = Date.now() - date.getTime()
  if (diffMs < 0) return formatDate(value)
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH} 小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 30) return `${diffD} 天前`
  return formatDate(value)
}

export function formatFileSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

// ===== 名称 / 版本标签 =====

export function formatStudyName(value?: string | null) {
  if (!value) return '研究项已准备'
  return value.replace(/\s*Study$/i, ' 研究项')
}

// 6-05 §9：内部版本标识 "working" 对用户翻成"工作版本"；已发布版本保留其 SemVer 号（如 1.0.0）
export function formatVersionLabel(label?: string | null) {
  if (!label || label === 'working') return '工作版本'
  return label
}

// ===== 可见范围 =====

// 6-05 B 方案：可见范围徽章配色（开放度递增：私有→灰中性，共享→主色蓝，公开→成功绿）
export function getVisibilityClass(visibility: string) {
  if (visibility === 'public') return 'badge--success'
  if (visibility === 'shared') return 'badge--primary'
  return 'badge--outline'
}

export function getVisibilityLabel(visibility: string) {
  const labels: Record<string, string> = {
    private: '私有',
    shared: '共享',
    public: '公开',
  }
  return labels[visibility] || visibility
}

// ===== 采集记录展示 =====

export function formatSourceFormat(value?: string | null) {
  if (!value) return '未知'
  const normalized = value.toLowerCase()
  if (normalized === 'brainvision') return 'BrainVision'
  return value.toUpperCase()
}

export function getCurrentVersionLabel(recording: Recording) {
  if (recording.current_version_seq != null) return `v${recording.current_version_seq}`
  if (recording.current_version_id) return '当前版本'
  return '待生成'
}

export function getRecordingUpdatedAt(recording: Recording) {
  const withTimestamps = recording as Recording & { updated_at?: string | null; created_at?: string | null }
  return withTimestamps.updated_at || recording.imported_at || withTimestamps.created_at || null
}

export function formatChannelEvent(channels?: number | null, events?: number | null) {
  const channelLabel = channels == null ? '-' : `${channels} ch`
  const eventLabel = events == null ? '-' : `${events} evt`
  return `${channelLabel} / ${eventLabel}`
}

// ===== 质控状态 =====

export function qaStatusLabel(status: string | null | undefined): string {
  if (status === 'pass') return '已通过'
  if (status === 'fail') return '未通过'
  return '未运行'
}

export function isQaPassed(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  return ['pass', 'passed', 'ok', 'accepted', 'approved'].includes(normalized)
}

export function getQaStatusLabel(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  const labels: Record<string, string> = {
    pass: '通过',
    passed: '通过',
    ok: '通过',
    accepted: '通过',
    approved: '通过',
    pending: '待质控',
    queued: '待质控',
    failed: '未通过',
    fail: '未通过',
    rejected: '未通过',
    warning: '需复核',
    review: '需复核',
  }
  return labels[normalized] || status || '未质控'
}

export function getQaStatusClass(status?: string | null) {
  const normalized = (status || '').toLowerCase()
  if (isQaPassed(normalized)) return 'badge--success'
  if (['failed', 'fail', 'rejected'].includes(normalized)) return 'badge--danger'
  if (['warning', 'review'].includes(normalized)) return 'badge--warning'
  return 'badge--outline'
}

// ===== 错误消息提取 =====

export function getErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('，')
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) return `准备失败 (HTTP ${err.response.status})`
  return err.message ? `准备失败：${err.message}` : '准备失败'
}

export function lifecycleErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | string
    const msg = typeof first === 'string' ? first : first?.msg
    if (msg) return msg
  }
  const message = err instanceof Error ? err.message : ''
  return message || fallback
}

export function getRecordingErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('，')
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) {
    return `采集记录读取失败 (HTTP ${err.response.status})。`
  }
  return err.message ? `采集记录读取失败：${err.message}` : '采集记录读取失败'
}

export function getRecordingFilesErrorMessage(err: any) {
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (err.response?.status) return `文件列表读取失败 (HTTP ${err.response.status})`
  return err.message ? `文件列表读取失败：${err.message}` : '文件列表读取失败'
}

// ===== 文件角色 / 路径 / 分桶 =====

export function countFilesByRole(files: DatasetFile[], keywords: string[]) {
  return files.filter((file) => {
    const role = file.file_role.toLowerCase()
    return keywords.some((keyword) => role.includes(keyword))
  }).length
}

// original/upload/source → 你上传的；canonical/fif → 标准 FIF；raw/bids(幽灵) + sidecar + 其它 → 技术文件
export function fileBucketOf(file: DatasetFile): 'upload' | 'fif' | 'tech' {
  const role = (file.file_role || '').toLowerCase()
  if (role.includes('original') || role.includes('upload') || role.includes('source')) return 'upload'
  if (role.includes('canonical') || role.includes('fif')) return 'fif'
  return 'tech'
}

export function sumFileSize(files: DatasetFile[]) {
  return files.reduce((sum, file) => sum + (file.file_size || 0), 0)
}

export function normalizeFilePath(path: string) {
  return path.replace(/\\/g, '/')
}

export function getFileDisplayPath(file: DatasetFile) {
  return file.logical_path || file.relative_path || file.id
}

export function getFileShortPath(file: DatasetFile) {
  const path = normalizeFilePath(getFileDisplayPath(file))
  const parts = path.split('/').filter(Boolean)
  if (parts.length <= 3) return path
  return parts.slice(-3).join('/')
}

export function getFileFullLogicalPath(file: DatasetFile) {
  return file.logical_path ? normalizeFilePath(file.logical_path) : '未返回 logical_path'
}

export function getFileRelativePath(file: DatasetFile) {
  return file.relative_path ? normalizeFilePath(file.relative_path) : '未返回 relative_path'
}

export function getFileRoleLabel(role: string) {
  const normalized = role.toLowerCase()
  if (normalized.includes('original') || normalized.includes('upload')) return 'original'
  if (normalized.includes('raw') || normalized.includes('bids')) return 'Raw BIDS'
  if (normalized.includes('fif') || normalized.includes('canonical')) return 'canonical FIF'
  return role
}

export function getFileRoleGroup(file: DatasetFile): DatasetFileRoleFilter {
  const normalized = file.file_role.toLowerCase()
  if (normalized.includes('original') || normalized.includes('upload') || normalized.includes('source')) {
    return 'original'
  }
  if (normalized.includes('raw') || normalized.includes('bids')) return 'raw-bids'
  if (normalized.includes('fif') || normalized.includes('canonical')) return 'canonical-fif'
  return 'other'
}

export function matchesFileRoleFilter(file: DatasetFile, filter: DatasetFileRoleFilter) {
  return filter === 'all' || getFileRoleGroup(file) === filter
}
