// 工作流编辑器 · 产物预览（结果弹窗：指标 / 事件 / 曲线）
//
// 从 PipelinePage.vue 抽出：点结果产物 → 拉预览 → 渲染指标/事件/采样曲线。
// 依赖 selectedStudyId / describeError + 运行态核心的 runArtifacts（预览回填 preview_json），经 options 传入。
// resetArtifactPreview 被运行态核心 onResetTracking 回调调用（解构出的同名引用，运行时触发）。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { StudyOutput, StudyOutputPreview } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { shortId, numericMetric, formatMetricNumber, formatSecondsMetric } from './pipelineFormatters'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

interface ArtifactPreviewOptions {
  selectedStudyId: ComputedRef<string>
  runArtifacts: Ref<StudyOutput[]>
  describeError: (error: unknown, fallback: string) => string
}

export function useArtifactPreview(options: ArtifactPreviewOptions) {
  const { selectedStudyId, runArtifacts, describeError } = options

  const selectedArtifactPreview = ref<StudyOutputPreview | null>(null)
  const artifactPreviewOpen = ref(false)
  const artifactPreviewLoading = ref(false)
  const artifactPreviewError = ref('')
  let artifactPreviewSeq = 0

  function getPreviewSummary(previewJson?: Record<string, unknown>): Record<string, unknown> {
    const summary = previewJson?.summary
    return isRecord(summary) ? summary : {}
  }

  function buildArtifactPreviewMetrics(preview: StudyOutputPreview | null, summary: Record<string, unknown>) {
    if (!preview) return []
    const rows: Array<{ label: string; value: string }> = []
    const channelSummary = isRecord(summary.channel_summary) ? summary.channel_summary : {}
    const timeRange = isRecord(summary.time_range) ? summary.time_range : {}
    const eventSummary = isRecord(summary.event_summary) ? summary.event_summary : {}
    const nChannels = numericMetric(summary.n_channels) ?? numericMetric(channelSummary.n_channels)

    if (preview.data_type === 'raw') {
      rows.push({ label: 'sfreq', value: formatMetricNumber(summary.sfreq, 'Hz') })
      if (nChannels !== null) rows.push({ label: 'channels', value: String(nChannels) })
      rows.push({ label: 'duration', value: formatSecondsMetric(summary.duration_seconds) })
      rows.push({ label: 'events', value: String(numericMetric(eventSummary.annotation_count) ?? 0) })
    } else if (preview.data_type === 'epochs') {
      rows.push({ label: 'epochs', value: String(numericMetric(summary.n_epochs) ?? 0) })
      if (nChannels !== null) rows.push({ label: 'channels', value: String(nChannels) })
      rows.push({ label: 'tmin', value: formatMetricNumber(summary.tmin, 's') })
      rows.push({ label: 'tmax', value: formatMetricNumber(summary.tmax, 's') })
    } else if (preview.data_type === 'evoked') {
      const eventNames = Array.isArray(summary.event_names) ? summary.event_names.length : 0
      rows.push({ label: 'events', value: String(eventNames) })
      if (nChannels !== null) rows.push({ label: 'channels', value: String(nChannels) })
      rows.push({ label: 'tmin', value: formatMetricNumber(timeRange.tmin, 's') })
      rows.push({ label: 'tmax', value: formatMetricNumber(timeRange.tmax, 's') })
    } else {
      rows.push({ label: 'type', value: preview.data_type || 'artifact' })
    }

    return rows.filter((row) => row.value !== '-')
  }

  function buildArtifactPreviewEvents(summary: Record<string, unknown>) {
    const eventSummary = isRecord(summary.event_summary) ? summary.event_summary : {}
    const source = Array.isArray(summary.event_counts)
      ? summary.event_counts
      : Array.isArray(eventSummary.annotation_counts)
        ? eventSummary.annotation_counts
        : []
    return source
      .map((item) => {
        if (!isRecord(item)) return null
        return { name: String(item.name || ''), count: Number(item.count || 0) }
      })
      .filter((item): item is { name: string; count: number } => Boolean(item?.name))
      .slice(0, 8)
  }

  function buildArtifactPreviewCurves(summary: Record<string, unknown>) {
    const sampledCurves = isRecord(summary.sampled_curves) ? summary.sampled_curves : {}
    const channels = Array.isArray(sampledCurves.channels) ? sampledCurves.channels : []
    return channels
      .map((item) => {
        if (!isRecord(item)) return ''
        const values = Array.isArray(item.values) ? item.values.length : 0
        return `${String(item.name || 'channel')} · ${values} 点`
      })
      .filter(Boolean)
      .slice(0, 6)
  }

  const artifactPreviewSummary = computed(() => getPreviewSummary(selectedArtifactPreview.value?.preview_json))
  const artifactPreviewMetrics = computed(() => buildArtifactPreviewMetrics(selectedArtifactPreview.value, artifactPreviewSummary.value))
  const artifactPreviewEvents = computed(() => buildArtifactPreviewEvents(artifactPreviewSummary.value))
  const artifactPreviewCurves = computed(() => buildArtifactPreviewCurves(artifactPreviewSummary.value))
  const artifactPreviewTitle = computed(() => {
    if (!selectedArtifactPreview.value) return '结果预览'
    return `${selectedArtifactPreview.value.data_type || 'derived'} · ${shortId(selectedArtifactPreview.value.study_output_id)}`
  })
  const artifactPreviewObserveTarget = computed(() => {
    if (!selectedArtifactPreview.value) return { path: '/observe', query: {} }
    return {
      path: selectedArtifactPreview.value.observe_route || '/observe',
      query: selectedArtifactPreview.value.observe_query || {},
    }
  })

  async function openArtifactPreview(artifact: StudyOutput) {
    if (!selectedStudyId.value) return
    const requestSeq = ++artifactPreviewSeq
    artifactPreviewOpen.value = true
    artifactPreviewLoading.value = true
    artifactPreviewError.value = ''
    selectedArtifactPreview.value = null
    try {
      const res = await pipelineApi.previewStudyOutput(selectedStudyId.value, artifact.id)
      if (requestSeq !== artifactPreviewSeq) return
      selectedArtifactPreview.value = res.data
      runArtifacts.value = runArtifacts.value.map((item) =>
        item.id === artifact.id ? { ...item, preview_json: res.data.preview_json } : item,
      )
    } catch (error) {
      if (requestSeq !== artifactPreviewSeq) return
      artifactPreviewError.value = describeError(error, 'Artifact preview 读取失败')
    } finally {
      if (requestSeq === artifactPreviewSeq) artifactPreviewLoading.value = false
    }
  }

  function resetArtifactPreview() {
    artifactPreviewSeq += 1
    selectedArtifactPreview.value = null
    artifactPreviewOpen.value = false
    artifactPreviewLoading.value = false
    artifactPreviewError.value = ''
  }

  function artifactLabel(artifact: StudyOutput) {
    const type = artifact.data_type || 'derived'
    const subject = artifact.bids_subject_id || (artifact.upstream_recording_ids?.[0] ? shortId(artifact.upstream_recording_ids[0]) : '')
    const name = artifact.display_name ? ` · ${artifact.display_name}` : (subject ? ` · ${subject}` : '')
    return `${type}${name}`
  }

  return {
    selectedArtifactPreview,
    artifactPreviewOpen,
    artifactPreviewLoading,
    artifactPreviewError,
    artifactPreviewSummary,
    artifactPreviewMetrics,
    artifactPreviewEvents,
    artifactPreviewCurves,
    artifactPreviewTitle,
    artifactPreviewObserveTarget,
    openArtifactPreview,
    resetArtifactPreview,
    artifactLabel,
  }
}
