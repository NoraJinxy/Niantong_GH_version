// Pipeline 纯展示 / 格式化工具函数
//
// 从 PipelinePage.vue 抽出的「纯函数」集合：只依赖入参与模块常量，
// 不引用任何组件作用域状态（ref / reactive / computed）。供画布、执行详情、
// 结果等多处复用，方便单测与后续拆分。
//
// 颜色 / 阈值等模块常量统一来自 ./pipelineConstants（与原 PipelinePage 内的同名常量一致）。

import {
  PORT_COLORS,
  NODE_STATUS_COLORS,
  CATEGORY_COLORS,
  CATEGORY_SOFT_COLORS,
  NODE_TITLE_MAX_CHARS,
} from './pipelineConstants'
import type { StatusTone } from '@/composables/common/statusTone'

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
  // 缓存命中对用户等同「成功」：缓存是内部加速细节，不向用户暴露。
  // 缓存与否的区分只保留在画布节点配色（nodeStatusSoftColor 的 cached 分支）与 ?debug 浮层，供调试辨认。
  if (normalized === 'cached') return '成功'
  if (normalized === 'skipped') return '跳过'
  if (normalized === 'canceled') return '已取消'
  return status
}

export function jobStatusClass(status: string) {
  const normalized = normalizedJobStatus(status)
  // 缓存命中复用「成功」绿色药丸，与新算成功视觉一致（不暴露缓存语义）。
  if (normalized === 'cached') return 'status-pill--success'
  return `status-pill--${normalized}`
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
  if (status === 'queued' || status === 'pending') return '排队中'
  if (status === 'waiting_user_input') return '等待确认'
  if (status === 'canceled') return '已取消'
  return status
}

// 运行状态 → 药丸 tone（供 StatusPill）。queued/pending/未知归 muted。
export function executionStatusTone(status?: string | null): StatusTone {
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'canceled') return 'danger'
  if (status === 'waiting_user_input') return 'warn'
  if (status === 'running') return 'info'
  return 'muted'
}

// 工作流状态 → 药丸 tone（供 StatusPill）。
export function pipelineStatusTone(status?: string | null): StatusTone {
  if (status === 'active') return 'success'
  if (status === 'draft') return 'warn'
  return 'muted'
}

// 结果保留态 → 药丸 tone（供 StatusPill）。配合 formatArtifactRetention 使用。
export function artifactRetentionTone(
  artifact?: { keep?: boolean; deleted_at?: string | null } | null,
): StatusTone {
  if (artifact?.deleted_at) return 'danger'
  if (artifact?.keep) return 'success'
  return 'muted'
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
  if (status === 'active') return '可运行'
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
  if (mode === 'replay') return '重跑'
  if (mode === 'system') return '系统运行'
  return mode || '-'
}

export function formatArtifactRetention(
  artifact?: { keep?: boolean; cache_eligible?: boolean; deleted_at?: string | null } | null,
) {
  if (!artifact) return '未标记'
  if (artifact.deleted_at) return '已删除'
  if (artifact.keep) return '保存'
  // 缓存/临时是内部保留态，对用户统一收敛成「不保存」（不暴露 cache/temp 语义）
  return '不保存'
}

// 输出数据类型枚举 → 临床友好标签。结果列表 / 筛选的「显示文本」用它；
// 技术折叠仍显原始枚举、路由与筛选匹配仍用原值。未知类型回退原文（不致空白）。
const DATA_TYPE_LABELS: Record<string, string> = {
  raw: '原始数据',
  filtered_raw: '滤波后数据',
  epochs: '分段数据',
  evoked: 'ERP 波形',
  erp: 'ERP 波形',
  tfr: '时频图',
  psd: '功率谱',
  ica: 'ICA 成分',
  source: '源定位',
  microstate: '微状态',
  connectivity: '脑连接',
  json: '指标数据',
}

export function formatDataType(type?: string | null) {
  if (!type) return '结果'
  return DATA_TYPE_LABELS[String(type).toLowerCase()] || type
}

export function categoryColor(category?: string | null) {
  return CATEGORY_COLORS[categoryKey(category)] || '#8A95A8'
}

export function categorySoftColor(category?: string | null) {
  return CATEGORY_SOFT_COLORS[categoryKey(category)] || '#EEF2F8'
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
    // 频谱类输入(PSD/将来 TFR)同时接受连续数据与 Epochs。
    spectral_source: ['spectral_source', 'eeg_data', 'raw', 'dataset_collection', 'epochs'],
    // group 合并入口:沿 unit 轴可堆叠的产物(evoked/psd/tfr/已堆叠块/grand average 回吐)。
    stackable: ['stackable', 'evoked', 'psd', 'tfr', 'unit_stack', 'analysis_result'],
  }
  return Boolean(sourceType && targetType && compatibleTargets[targetType]?.includes(sourceType))
}

export function isWildcardPortType(type?: string): boolean {
  return type === '*' || type === 'any' || type === '' || type === undefined
}

// 某些 input 端口语义上接受多种上游类型。litegraph 0.7.x 的原生连线校验
// (isValidConnection) 支持「逗号分隔的类型列表」——任一类型命中即放行，
// 所以这里把这类端口的 litegraph slot 类型展开成它实际接受的具体类型列表，
// 让画布拖线与后端 port_types_compatible 判定一致。
const MULTI_ACCEPT_LITEGRAPH_TYPES: Record<string, string> = {
  spectral_source: 'epochs,eeg_data',
  // group 合并入口接受多种可堆叠产物——展开成逗号列表让画布原生连线放行。
  stackable: 'evoked,psd,tfr,unit_stack',
}

export function liteGraphPortType(type?: string): string {
  // litegraph.js 0.7.x 的 wildcard 端口必须是 falsy（空字符串 / 0 / null）。
  // 注意：-1 在该版本是 LiteGraph.EVENT/ACTION，会被画成方块且拒绝普通数据线连接。
  if (isWildcardPortType(type)) return ''
  if (type && MULTI_ACCEPT_LITEGRAPH_TYPES[type]) return MULTI_ACCEPT_LITEGRAPH_TYPES[type]
  return type || 'eeg_data'
}
