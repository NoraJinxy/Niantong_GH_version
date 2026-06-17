// 从 PipelinePage.vue 抽出的集中常量（模块级 `const 大写名 = 字面量`）。
// 另有 composable / 函数会按原名 import 这些常量，导出名与原变量名保持一致。

import type { PipelineExecutionMode } from '@/types'

export const LOAD_DATA_NODE_TYPE = 'eeg/data/load'
export const EPOCH_NODE_TYPE = 'eeg/epoch/segment'
export const ERP_NODE_TYPE = 'eeg/analysis/erp'
export const TFR_NODE_TYPE = 'eeg/analysis/tfr'
export const PSD_NODE_TYPE = 'eeg/analysis/psd'
export const ICA_APPLY_NODE_TYPE = 'eeg/ica/apply'
export const NULL_FILTER_VALUE = '__elys_null__'
export const DEFAULT_LOAD_DATA_QA_STATUS = ['converted', 'checked']

export const LITEGRAPH_NODE_ID_PROP = '__elys_node_id'
export const LITEGRAPH_HIDPI_EVENT_PROP = '__elys_hidpi_event'
export const LITEGRAPH_ORIGINAL_CLIENT_X_PROP = '__elys_original_client_x'
export const LITEGRAPH_ORIGINAL_CLIENT_Y_PROP = '__elys_original_client_y'
export const LITEGRAPH_ENGINE_INFO = {
  name: 'litegraph.js',
  version: '0.7.18',
}
export const CATEGORY_COLORS: Record<string, string> = {
  data: '#2F5F8F',
  input: '#2F5F8F',
  preprocess: '#2F766F',
  preprocessing: '#2F766F',
  ica: '#6B5F95',
  epoch: '#4C7A5B',
  analysis: '#9A6A28',
  output: '#687386',
  qc: '#9B557A',
  visualization: '#4F6F9F',
}
export const CATEGORY_SOFT_COLORS: Record<string, string> = {
  data: '#EEF4FA',
  input: '#EEF4FA',
  preprocess: '#EDF7F5',
  preprocessing: '#EDF7F5',
  ica: '#F3F1F8',
  epoch: '#F0F7F2',
  analysis: '#FAF4E8',
  output: '#F2F4F7',
  qc: '#F8EEF4',
  visualization: '#EEF3F9',
}
export const PORT_COLORS: Record<string, string> = {
  eeg_data: '#2F5F8F',
  dataset_collection: '#2F5F8F',
  raw: '#386B9A',
  epochs: '#4C7A5B',
  evoked: '#9A6A28',
  analysis_result: '#6B5F95',
  ica_matrix: '#6B5F95',
  events: '#9A6A28',
  figure_spec: '#687386',
  psd: '#2F766F',
  spectral_source: '#2F766F',
  tfr: '#9B557A',
  connectivity: '#4F6F9F',
  microstate: '#9B557A',
  source_estimate: '#6B5F95',
}

// 连线视觉常量(集中管理,方便统一调整)
export const LINK_DEFAULT_COLOR = '#475569'   // slate-600 :普通连线
export const LINK_HIGHLIGHT_COLOR = '#2563EB' // blue-600 :选中节点 / 拖动节点 / hover 时的相关连线
export const LINK_CONNECTING_COLOR = '#2563EB'// blue-600 :拖线建立连接时的临时连线
export const LINK_HIGHLIGHT_WIDTH_MULT = 1.5  // 高亮连线相对默认宽度的倍率
export const NODE_STATUS_COLORS: Record<string, string> = {
  queued: '#687386',
  pending: '#687386',
  running: '#C7831D',
  waiting_user_input: '#8B5CF6',
  success: '#2F766F',
  completed: '#2F766F',
  failed: '#B42318',
  canceled: '#687386',
  cached: '#6B5F95',
  skipped: '#687386',
}
export const EXECUTION_POLL_INTERVAL_MS = 1500
export const EXECUTION_CANCELABLE_STATUSES = ['queued', 'running', 'waiting_user_input']
export const EXECUTION_RETRYABLE_STATUSES = ['failed', 'canceled']
export const TASK_CANCELABLE_STATUSES = ['queued', 'pending', 'running', 'waiting', 'waiting_user_input', 'started']
export const TASK_RETRYABLE_STATUSES = ['failed', 'canceled']
export const EXECUTION_MODE_OPTIONS: Array<{ value: PipelineExecutionMode; label: string; description: string }> = [
  { value: 'trial', label: '试跑', description: '用于边调参数边看数据' },
  { value: 'analysis', label: '正式分析', description: '用于正式结果和报告追溯' },
  { value: 'replay', label: '重跑', description: '复用历史快照重跑一次执行；当前后端通常由 Retry 触发' },
  { value: 'system', label: '系统运行', description: '系统维护或自动化任务使用，人工运行时会受状态规则限制' },
]
export const NODE_CARD_WIDTH = 264
export const NODE_CARD_MIN_HEIGHT = 112
export const NODE_TITLE_MAX_CHARS = 22
export const NODE_GAP_X = 304
export const NODE_GAP_Y = 168
export const LITEGRAPH_MIN_ZOOM = 0.58
export const LITEGRAPH_MAX_ZOOM = 1.75
export const LITEGRAPH_MAX_PIXEL_RATIO = 2

// ========== Pipeline 草稿 localStorage 暂存 ==========
export const DRAFT_LS_PREFIX = 'elys-pipeline-draft-'
export const DRAFT_STORAGE_VERSION = 1

// ========== 阶段 1: 抽屉式布局 ==========
export const LAYOUT_LS_PREFIX = 'elys-pipeline-layout-'

// LiteGraph 连线高亮 patch 标记（防止 HMR 重载时重复包装 prototype）。
export const LINK_HIGHLIGHT_PATCH_MARK = '__elysLinkHighlightPatched__'

/** 节点类型是否需要在画布上显示 save 图标 —— LoadData 是 source 节点没有结果。
 *  Save 节点（eeg/output/save_result）在 P6 阶段已彻底删除，无需再排除。
 */
export const NO_SAVE_ICON_NODE_TYPES = new Set<string>([
  'eeg/data/load',
])
