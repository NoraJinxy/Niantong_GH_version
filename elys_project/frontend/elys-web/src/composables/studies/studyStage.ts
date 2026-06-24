// 研究阶段（数据 → 工作流 → 运行 → 就绪）的「单一事实源」。
// 此前 Dashboard / StudiesPage / StudyOverviewTab 各写了一份判定，连标签和「下一步」文案都已漂移。
// 这里收成一个纯函数 deriveStudyStage：吃归一化后的计数，吐出阶段枚举 + 药丸标签/tone + 进度条步数 + 「下一步」文案。
//
// 注意各页数据粒度不同：Dashboard 的 recent_studies.metrics 没有「记录数 / 运行中数」，
// 只有 pipeline_count / execution_count / attention_count，所以这些字段都做成可选，
// 缺失时跳过对应判定（recordingCount 未知 → 不判 needs-data；runningCount 未知 → 当 0）。
import type { StatusTone } from '@/composables/common/statusTone'

export type StudyStage = 'pending' | 'needs-data' | 'needs-pipeline' | 'running' | 'ready'

export interface StudyStageInput {
  /** 摘要是否已加载完成；false → pending（同步中）。缺省按已加载处理。 */
  loaded?: boolean
  /** 采集记录数。null/undefined = 未知（Dashboard 场景），此时跳过 needs-data 判定。 */
  recordingCount?: number | null
  pipelineCount?: number | null
  executionCount?: number | null
  runningExecutionCount?: number | null
  /** 需要处理（失败 / 等待确认）的运行数；>0 时阶段标签覆盖为「需要你看一下」。 */
  attentionExecutionCount?: number | null
}

/** 「下一步」去向（路由由各页自行拼，组合式不耦合 router）。 */
export type StudyNextTarget = 'import-data' | 'configure-pipeline' | 'view-run' | 'continue' | 'view-data'

export interface StudyNextStep {
  title: string
  description: string
  action: string
  target: StudyNextTarget
}

export interface StudyStageResult {
  stage: StudyStage
  needsAttention: boolean
  /** 药丸标签（attention 时覆盖为「需要你看一下」）。 */
  label: string
  tone: StatusTone
  /** 三段式进度条点亮的段数（0–3）。 */
  step: 0 | 1 | 2 | 3
  nextStep: StudyNextStep
}

const STAGE_LABEL: Record<StudyStage, string> = {
  pending: '同步中…',
  'needs-data': '待导入数据',
  'needs-pipeline': '待配置流程',
  running: '运行中',
  ready: '可继续分析',
}

const STAGE_TONE: Record<StudyStage, StatusTone> = {
  pending: 'muted',
  'needs-data': 'warn',
  'needs-pipeline': 'warn',
  running: 'info',
  ready: 'success',
}

// 三段式进度条点亮段数（给 Dashboard 用）。ready 再按是否产出过运行结果细分 2/3，
// 以保留「有数据有流程未跑(2 段) → 跑出结果(3 段)」的渐进。
function stepOf(stage: StudyStage, input: StudyStageInput): 0 | 1 | 2 | 3 {
  if (stage === 'needs-pipeline') return 1
  if (stage === 'running') return 2
  if (stage === 'ready') return (input.executionCount ?? 0) > 0 ? 3 : 2
  return 0 // pending / needs-data
}

const STAGE_NEXT: Record<StudyStage, StudyNextStep> = {
  pending: { title: '加载中', description: '', action: '查看数据', target: 'view-data' },
  'needs-data': {
    title: '先导入数据集',
    description: '当前研究项还没有可处理的数据。导入或关联数据集后再开始后续分析。',
    action: '导入数据集',
    target: 'import-data',
  },
  'needs-pipeline': {
    title: '配置工作流',
    description: '已经有数据了，但还没有工作流。下一步是创建或选择分析流程。',
    action: '进入工作区',
    target: 'configure-pipeline',
  },
  running: {
    title: '查看运行状态',
    description: '当前有运行正在进行，建议先查看进度、日志和输出状态。',
    action: '查看运行记录',
    target: 'view-run',
  },
  ready: {
    title: '可以继续分析',
    description: '数据和工作流已就绪，可以创建新运行或查看既有运行结果。',
    action: '进入工作区',
    target: 'continue',
  },
}

function stageOf(input: StudyStageInput): StudyStage {
  if (input.loaded === false) return 'pending'
  const recordings = input.recordingCount
  const pipelines = input.pipelineCount ?? 0
  const running = input.runningExecutionCount ?? 0
  // recordingCount 已知且为 0 → 还没数据；未知（Dashboard）则跳过此判定
  if (recordings != null && recordings === 0) return 'needs-data'
  if (pipelines === 0) return 'needs-pipeline'
  if (running > 0) return 'running'
  return 'ready'
}

export function deriveStudyStage(input: StudyStageInput): StudyStageResult {
  const stage = stageOf(input)
  const needsAttention = (input.attentionExecutionCount ?? 0) > 0
  return {
    stage,
    needsAttention,
    label: needsAttention ? '需要你看一下' : STAGE_LABEL[stage],
    tone: needsAttention ? 'warn' : STAGE_TONE[stage],
    step: stepOf(stage, input),
    nextStep: STAGE_NEXT[stage],
  }
}
