// Pipeline 纯展示 / 格式化工具函数
//
// 从 PipelinePage.vue 抽出的「纯函数」集合：只依赖入参与模块常量，
// 不引用任何组件作用域状态（ref / reactive / computed）。供画布、执行详情、
// 派生数据等多处复用，方便单测与后续拆分。
//
// 颜色 / 阈值等模块常量统一来自 ./pipelineConstants（与原 PipelinePage 内的同名常量一致）。

import {
  PORT_COLORS,
  NODE_STATUS_COLORS,
  CATEGORY_COLORS,
  CATEGORY_SOFT_COLORS,
  NODE_TITLE_MAX_CHARS,
} from './pipelineConstants'

export function pipelinePortColors(alpha = 1) {
  return Object.fromEntries(
    Object.entries(PORT_COLORS).map(([type, color]) => [type, alpha >= 1 ? color : withAlpha(color, alpha)]),
  )
}

export function portTypeColor(type?: string | number | null) {
  if (typeof type !== 'string') return '#8A95A8'
  return PORT_COLORS[type] || '#8A95A8'
}

export function withAlpha(hex: string, alpha: number) {
  const normalized = hex.replace('#', '')
  if (normalized.length !== 6) return hex
  const value = Number.parseInt(normalized, 16)
  if (!Number.isFinite(value)) return hex
  const r = (value >> 16) & 255
  const g = (value >> 8) & 255
  const b = value & 255
  return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, alpha))})`
}

export function normalizedJobStatus(status?: string | null) {
  const text = String(status || '').trim().toLowerCase()
  if (text === 'completed') return 'success'
  return text || 'pending'
}

export function nodeStatusColor(status?: string | null) {
  return NODE_STATUS_COLORS[normalizedJobStatus(status)] || '#687386'
}

export function nodeStatusSoftColor(status?: string | null) {
  const normalized = normalizedJobStatus(status)
  if (normalized === 'failed') return '#FFF4F2'
  if (normalized === 'success') return '#F0F8F4'
  if (normalized === 'running') return '#FFF8E8'
  if (normalized === 'cached') return '#F5F1FA'
  if (normalized === 'waiting_user_input') return '#F5F1FA'
  return '#F8FAFC'
}

export function formatJobStatus(status: string) {
  const normalized = normalizedJobStatus(status)
  if (normalized === 'success') return '成功'
  if (normalized === 'failed') return '失败'
  if (normalized === 'queued') return '排队'
  if (normalized === 'running') return '运行中'
  if (normalized === 'waiting_user_input') return '等待确认'
  if (normalized === 'pending') return '等待'
  if (normalized === 'cached') return '缓存'
  if (normalized === 'skipped') return '跳过'
  if (normalized === 'canceled') return '已取消'
  return status
}

export function jobStatusClass(status: string) {
  return `status-pill--${normalizedJobStatus(status)}`
}

// UI Phase (docs_v2/6-05) P1-2: 步骤可视化状态映射
export function stepVisualState(status: string): 'done' | 'doing' | 'pending' | 'failed' | 'waiting' | 'skipped' {
  const s = normalizedJobStatus(status)
  if (s === 'success' || s === 'completed' || s === 'cached') return 'done'
  if (s === 'running') return 'doing'
  if (s === 'failed' || s === 'canceled') return 'failed'
  if (s === 'waiting_user_input') return 'waiting'
  if (s === 'skipped') return 'skipped'
  return 'pending'
}

export function stepIcon(status: string): string {
  const v = stepVisualState(status)
  if (v === 'done') return '✓'
  if (v === 'doing') return '⏳'
  if (v === 'failed') return '✕'
  if (v === 'waiting') return '!'
  if (v === 'skipped') return '—'
  return '○'
}

export function isStepDone(status: string): boolean {
  const v = stepVisualState(status)
  return v === 'done' || v === 'skipped'
}

export function formatFileSize(value?: number | null) {
  if (value === null || value === undefined) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

export function shortId(value?: string | null) {
  if (!value) return ''
  const text = String(value)
  return text.length > 8 ? text.slice(0, 8) : text
}

export function numericMetric(value: unknown) {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

export function formatMetricNumber(value: unknown, suffix = '') {
  const numberValue = numericMetric(value)
  if (numberValue === null) return '-'
  const digits = Math.abs(numberValue) >= 10 ? 1 : 3
  return `${Number(numberValue.toFixed(digits))}${suffix}`
}

export function formatSecondsMetric(value: unknown) {
  const seconds = numericMetric(value)
  if (seconds === null) return '-'
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  return `${(seconds / 60).toFixed(2)}min`
}

export function formatDurationMs(durationMs?: number | null) {
  if (durationMs === null || durationMs === undefined) return '—'
  if (durationMs < 1000) return `${durationMs}ms`
  return `${(durationMs / 1000).toFixed(durationMs < 10000 ? 1 : 0)}s`
}

export function formatPipelineExecutionStatus(status: string) {
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '运行中'
  if (status === 'queued') return '排队'
  if (status === 'waiting_user_input') return '等待确认'
  if (status === 'canceled') return '已取消'
  return status
}

export function formatTaskStatus(status?: string | null) {
  if (status === 'success' || status === 'completed') return '成功'
  if (status === 'failed') return '失败'
  if (status === 'running') return '运行中'
  if (status === 'queued' || status === 'pending') return '排队'
  if (status === 'waiting_user_input') return '等待确认'
  if (status === 'canceled') return '已取消'
  if (status === 'retrying') return '重试中'
  return status || '-'
}

export function formatDateTime(value?: string | null) {
  if (!value) return '-'
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

export function formatPipelineStatus(status: string) {
  if (status === 'active') return '已启用'
  if (status === 'draft') return '草稿'
  if (status === 'archived') return '已归档'
  if (status === 'deleted') return '已删除'
  return status || '草稿'
}

export function allowedExecutionModeText(status: string) {
  if (status === 'draft') return '试跑'
  if (status === 'active') return '试跑或正式分析'
  return '无'
}

export function formatExecutionMode(mode?: string | null) {
  if (mode === 'trial') return '试跑'
  if (mode === 'analysis') return '正式分析'
  if (mode === 'replay') return '重放'
  if (mode === 'system') return '系统运行'
  return mode || '-'
}

export function formatArtifactRetention(
  artifact?: { keep?: boolean; cache_eligible?: boolean; deleted_at?: string | null } | null,
) {
  if (!artifact) return '未标记'
  if (artifact.deleted_at) return '已删除'
  if (artifact.keep) return '保存'
  if (artifact.cache_eligible) return '缓存'
  return '临时'
}

export function categoryColor(category?: string | null) {
  return CATEGORY_COLORS[categoryKey(category)] || '#8A95A8'
}

export function categorySoftColor(category?: string | null) {
  return CATEGORY_SOFT_COLORS[categoryKey(category)] || '#EEF2F8'
}

export function categoryLabel(category?: string | null) {
  return String(category || 'Node').trim() || 'Node'
}

export function compactNodeTitle(title: string) {
  const normalized = title.trim()
  if (normalized.length <= NODE_TITLE_MAX_CHARS) return normalized
  return `${normalized.slice(0, NODE_TITLE_MAX_CHARS - 1)}…`
}

export function categoryKey(category?: string | null) {
  const text = String(category || '').trim().toLowerCase()
  if (!text) return ''
  if (text.includes('data') || text.includes('load')) return 'data'
  if (text.includes('input')) return 'input'
  if (text.includes('preprocess') || text.includes('filter') || text.includes('clean')) return 'preprocess'
  if (text.includes('ica')) return 'ica'
  if (text.includes('epoch')) return 'epoch'
  if (text.includes('analysis') || text.includes('erp') || text.includes('time') || text.includes('frequency')) return 'analysis'
  if (text.includes('visual') || text.includes('plot') || text.includes('figure')) return 'visualization'
  if (text.includes('qc') || text.includes('quality')) return 'qc'
  if (text.includes('output') || text.includes('export')) return 'output'
  return text
}

export function portTypesCompatible(sourceType?: string, targetType?: string) {
  if (isWildcardPortType(sourceType) || isWildcardPortType(targetType)) return true
  if (sourceType === targetType) return true
  const compatibleTargets: Record<string, string[]> = {
    analysis_result: ['analysis_result', 'evoked', 'epochs', 'psd', 'tfr', 'connectivity', 'microstate', 'source_estimate'],
    eeg_data: ['eeg_data', 'raw', 'dataset_collection'],
  }
  return Boolean(sourceType && targetType && compatibleTargets[targetType]?.includes(sourceType))
}

export function isWildcardPortType(type?: string): boolean {
  return type === '*' || type === 'any' || type === '' || type === undefined
}

export function liteGraphPortType(type?: string): string {
  // litegraph.js 0.7.x 的 wildcard 端口必须是 falsy（空字符串 / 0 / null）。
  // 注意：-1 在该版本是 LiteGraph.EVENT/ACTION，会被画成方块且拒绝普通数据线连接。
  if (isWildcardPortType(type)) return ''
  return type || 'eeg_data'
}
