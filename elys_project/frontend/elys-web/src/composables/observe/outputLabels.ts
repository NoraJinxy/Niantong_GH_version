// 多产物观察页（时域 / 频域 / 时频）共用：挂载时取各 study_output 的「轻量元数据」，
// 让数据集选择器在「加载重绘图数据之前」就显示真名（被试 · 条件），而非退化的「数据集 N」。
// 名字本来只能从已加载的绘图响应里取，而页面默认只加载第 1 个数据集 → 其余一直是「数据集 N」。
import { pipelineApi } from '@/api/pipelines'
import type { StudyOutput } from '@/types'
import { fmtSubject } from './observeUtils'

export interface OutputOptionMeta {
  datasetLabel: string
  eventLabel: string
  displayName: string
  subjectLabel: string
  condition: string
}

const BIDS_KEYS = ['sub', 'ses', 'task', 'run', 'acq', 'rec', 'proc', 'space', 'desc']

function parseBidsParts(label: string): Record<string, string> {
  const out: Record<string, string> = {}
  const re = /(?:^|[_\s.-])(sub|ses|task|run|acq|rec|proc|space|desc)-([^_\s.()]+)/gi
  for (const match of label.matchAll(re)) {
    const key = match[1].toLowerCase()
    out[key] = `${key}-${match[2]}`
  }
  return out
}

export function compactDatasetLabels(labels: string[]): string[] {
  if (labels.length <= 1) return labels
  const parsed = labels.map(parseBidsParts)
  const hasBids = parsed.some((parts) => Object.keys(parts).length > 0)
  if (!hasBids) return labels

  const diffKeys = BIDS_KEYS.filter((key) => {
    const values = new Set(parsed.map((parts) => parts[key] || ''))
    return values.size > 1
  })
  const keys = parsed.some((parts) => parts.sub) ? ['sub', ...diffKeys.filter((key) => key !== 'sub')] : diffKeys
  const fallbackKeys = keys.length ? keys : BIDS_KEYS.filter((key) => parsed.some((parts) => parts[key])).slice(0, 1)

  return labels.map((label, i) => {
    const parts = fallbackKeys.map((key) => parsed[i][key]).filter(Boolean)
    return parts.length ? parts.join('_') : label
  })
}

function stripCondition(label: string, condition: string): string {
  if (!label || !condition) return label
  const escaped = condition.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return label
    .replace(new RegExp(`\\s*[·/|_-]\\s*${escaped}\\s*$`, 'i'), '')
    .replace(new RegExp(`\\s*\\(${escaped}\\)\\s*$`, 'i'), '')
    .replace(new RegExp(`\\s+${escaped}\\s*$`, 'i'), '')
    .trim()
}

function formatDatasetLabel(data: StudyOutput): string {
  const subject = fmtSubject(data.bids_subject_id || data.subject_id || '')
  const parts = [data.bids_subject_id || data.subject_id || '', data.session || '', data.task ? `task-${data.task}` : '', data.run_label || '']
    .map((part) => String(part || '').trim())
    .filter(Boolean)
  const bidsLike = parts.length ? parts.join('_') : ''
  const display = stripCondition(data.display_name || '', data.condition || '')
  return display || bidsLike || subject || ''
}

function metaFromOutput(data: StudyOutput): OutputOptionMeta {
  const condition = data.condition || ''
  const datasetLabel = formatDatasetLabel(data)
  return {
    datasetLabel,
    eventLabel: condition || '整体',
    displayName: data.display_name || datasetLabel,
    subjectLabel: fmtSubject(data.bids_subject_id || data.subject_id || ''),
    condition,
  }
}

export async function loadOutputOptionMeta(
  studyId: string,
  outputIds: string[],
  into: Record<number, OutputOptionMeta>,
): Promise<void> {
  if (!studyId || !outputIds.length) return
  await Promise.allSettled(
    outputIds.map(async (id, i) => {
      if (into[i]) return
      const { data } = await pipelineApi.getStudyOutput(studyId, id)
      into[i] = metaFromOutput(data)
    }),
  )
}

/**
 * 并发取 outputIds 各自的元数据，把「被试 · 条件 / display_name」写进 into[index]（index 与 outputIds 对齐）。
 * best-effort：取不到的项静默跳过（segLabel 自行退回「数据集 N」）；已有值不覆盖（已加载数据填的更准）。
 */
export async function loadOutputLabels(
  studyId: string,
  outputIds: string[],
  into: Record<number, string>,
): Promise<void> {
  if (!studyId || outputIds.length < 2) return
  const meta: Record<number, OutputOptionMeta> = {}
  await loadOutputOptionMeta(studyId, outputIds, meta)
  for (const [i, item] of Object.entries(meta)) {
    if (!into[Number(i)] && item.datasetLabel) into[Number(i)] = item.datasetLabel
  }
}
