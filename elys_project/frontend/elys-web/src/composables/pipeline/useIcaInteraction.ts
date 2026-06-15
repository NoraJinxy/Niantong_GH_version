// 工作流编辑器 · ICA 成分人工剔除交互
//
// 半自动节点（eeg/ica/apply）暂停 → 人工勾选要剔除的成分 → 提交决策 → 恢复运行。
// 依赖运行态核心（selectedJob / activeExecutionId / latestPipelineExecution / refreshRunState /
// startRunPolling / isTerminalRunStatus）+ selectedStudyId / statusMessage / describeError，经 options 传入。
// resetIcaInteractionState 被运行态核心的 onResetTracking 回调调用、loadSelectedIcaInteraction 被
// PipelinePage 的 watch 调用，均通过解构出的同名引用（单向：运行态 → ICA）。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { PipelineExecution, PipelineIcaComponentPreview, PipelineInteraction, PipelineJob } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { ICA_APPLY_NODE_TYPE } from './pipelineConstants'

interface IcaInteractionOptions {
  selectedJob: ComputedRef<PipelineJob | null>
  selectedStudyId: ComputedRef<string>
  activeExecutionId: Ref<string>
  latestPipelineExecution: Ref<PipelineExecution | null>
  statusMessage: Ref<string>
  describeError: (error: unknown, fallback: string) => string
  refreshRunState: (executionId?: string) => Promise<void>
  isTerminalRunStatus: (status: string) => boolean
  startRunPolling: (executionId?: string) => void
}

export function useIcaInteraction(options: IcaInteractionOptions) {
  const {
    selectedJob,
    selectedStudyId,
    activeExecutionId,
    latestPipelineExecution,
    statusMessage,
    describeError,
    refreshRunState,
    isTerminalRunStatus,
    startRunPolling,
  } = options

  const icaInteraction = ref<PipelineInteraction | null>(null)
  const icaExcludedComponents = ref<number[]>([])
  const icaInteractionLoading = ref(false)
  const icaDecisionSubmitting = ref(false)
  const icaResuming = ref(false)
  const icaInteractionError = ref('')
  let icaInteractionSeq = 0

  const showIcaInteractionPanel = computed(
    () => selectedJob.value?.node_type === ICA_APPLY_NODE_TYPE && selectedJob.value.status === 'waiting_user_input',
  )
  const icaInteractionComponents = computed(() => icaInteraction.value?.components || [])

  // 跳到富 ICA 审阅台（地形图 / 时序 / 频谱），带 job 上下文以便就地提交剔除决策；
  // ICA 结果 id 从交互 preview_json.datasets[].ica_artifact_id 取，取不到则返回空（不显示入口）。
  const icaReviewerHref = computed(() => {
    const studyId = selectedStudyId.value
    const executionId = activeExecutionId.value
    const job = selectedJob.value
    const interaction = icaInteraction.value
    if (!studyId || !executionId || !job || !interaction) return ''
    const datasets = (interaction.preview_json as { datasets?: Array<{ ica_artifact_id?: string | null }> } | null)?.datasets
    const outputId = Array.isArray(datasets) ? datasets.find((d) => d && d.ica_artifact_id)?.ica_artifact_id || '' : ''
    if (!outputId) return ''
    const query = new URLSearchParams({
      studyId,
      study_output_id: String(outputId),
      executionId,
      jobId: job.id,
      decisionVersion: String(interaction.decision_version || 1),
    })
    return `/ica?${query.toString()}`
  })

  function resetIcaInteractionState() {
    icaInteractionSeq += 1
    icaInteraction.value = null
    icaExcludedComponents.value = []
    icaInteractionLoading.value = false
    icaInteractionError.value = ''
  }

  async function loadSelectedIcaInteraction() {
    const job = selectedJob.value
    const studyId = selectedStudyId.value
    const executionId = activeExecutionId.value
    if (!studyId || !executionId || !job || !showIcaInteractionPanel.value) {
      resetIcaInteractionState()
      return
    }

    const requestSeq = ++icaInteractionSeq
    icaInteractionLoading.value = true
    icaInteractionError.value = ''
    try {
      const res = await pipelineApi.getNodeInteraction(studyId, executionId, job.id)
      if (requestSeq !== icaInteractionSeq) return
      icaInteraction.value = res.data
      icaExcludedComponents.value = [...(res.data.decision?.excluded_components || [])]
    } catch (error) {
      if (requestSeq !== icaInteractionSeq) return
      icaInteraction.value = null
      icaExcludedComponents.value = []
      icaInteractionError.value = describeError(error, 'ICA 交互信息读取失败')
    } finally {
      if (requestSeq === icaInteractionSeq) icaInteractionLoading.value = false
    }
  }

  function toggleIcaComponent(index: number, event: Event) {
    const checked = Boolean((event.target as HTMLInputElement | null)?.checked)
    const set = new Set(icaExcludedComponents.value)
    if (checked) set.add(index)
    else set.delete(index)
    icaExcludedComponents.value = [...set].sort((left, right) => left - right)
  }

  async function submitIcaDecision() {
    const studyId = selectedStudyId.value
    const executionId = activeExecutionId.value
    const job = selectedJob.value
    const interaction = icaInteraction.value
    if (!studyId || !executionId || !job || !interaction) return

    icaDecisionSubmitting.value = true
    icaInteractionError.value = ''
    try {
      const res = await pipelineApi.submitNodeDecision(studyId, executionId, job.id, {
        excluded_components: icaExcludedComponents.value,
        decision_version: interaction.decision_version,
      })
      icaInteraction.value = res.data
      icaExcludedComponents.value = [...(res.data.decision?.excluded_components || [])]
      await refreshRunState(executionId)
      statusMessage.value = 'ICA 决策已提交'
    } catch (error) {
      icaInteractionError.value = describeError(error, 'ICA 决策提交失败')
    } finally {
      icaDecisionSubmitting.value = false
    }
  }

  async function resumeIcaNode() {
    const studyId = selectedStudyId.value
    const executionId = activeExecutionId.value
    const job = selectedJob.value
    if (!studyId || !executionId || !job) return

    icaResuming.value = true
    icaInteractionError.value = ''
    try {
      const res = await pipelineApi.resumeNode(studyId, executionId, job.id)
      latestPipelineExecution.value = res.data.execution
      activeExecutionId.value = res.data.execution.id
      await refreshRunState(res.data.execution.id)
      if (!isTerminalRunStatus(latestPipelineExecution.value?.status || '')) startRunPolling(res.data.execution.id)
      statusMessage.value = `ICA 节点已继续：运行 #${res.data.execution.execution_seq}`
    } catch (error) {
      icaInteractionError.value = describeError(error, 'ICA 节点继续失败')
    } finally {
      icaResuming.value = false
    }
  }

  function icaComponentLabel(component: PipelineIcaComponentPreview) {
    return component.label || `IC${String(component.index).padStart(3, '0')}`
  }

  function icaComponentMetric(component: PipelineIcaComponentPreview) {
    const parts: string[] = []
    if (typeof component.std === 'number') parts.push(`std ${component.std.toExponential(2)}`)
    if (typeof component.max_abs === 'number') parts.push(`max ${component.max_abs.toExponential(2)}`)
    if (Array.isArray(component.top_channels) && component.top_channels.length) {
      parts.push(component.top_channels.slice(0, 3).join(', '))
    }
    return parts.join(' · ') || 'component preview'
  }

  return {
    icaInteraction,
    icaExcludedComponents,
    icaInteractionLoading,
    icaDecisionSubmitting,
    icaResuming,
    icaInteractionError,
    showIcaInteractionPanel,
    icaInteractionComponents,
    icaReviewerHref,
    resetIcaInteractionState,
    loadSelectedIcaInteraction,
    toggleIcaComponent,
    submitIcaDecision,
    resumeIcaNode,
    icaComponentLabel,
    icaComponentMetric,
  }
}
