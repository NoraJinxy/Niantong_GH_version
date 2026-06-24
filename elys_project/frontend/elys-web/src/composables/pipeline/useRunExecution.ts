// 工作流编辑器 · 运行态核心（执行加载 / 轮询 / 状态刷新 / 重置）
//
// 五向耦合的中心，用「回调注入」解耦，避免散参数透传：
//   - applyRunStateToCanvas：把运行态映射到画布节点配色（画布域）
//   - onResetTracking：重置时清执行详情 / 任务 / 产物预览 / ICA（PipelinePage 薄包装其它 composable）
//   - onRunStateRefreshed：刷新后按当前 tab 懒加载执行详情 Manifest / Lineage
// 承重墙状态（selectedNode / statusMessage）+ selectedStudyId / currentPipeline + 产物/任务 helper 经 options 传入。

import { computed, onUnmounted, ref, type Ref, type ComputedRef } from 'vue'
import type {
  Pipeline,
  PipelineExecution,
  PipelineExecutionDetail,
  PipelineGraphNode,
  PipelineJob,
  StudyOutput,
} from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { EXECUTION_POLL_INTERVAL_MS } from './pipelineConstants'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

interface RunExecutionOptions {
  selectedStudyId: ComputedRef<string>
  currentPipeline: Ref<Pipeline | null>
  selectedNode: ComputedRef<PipelineGraphNode | null>
  statusMessage: Ref<string>
  describeError: (error: unknown, fallback: string) => string
  applyRunStateToCanvas: () => void
  onResetTracking: () => void
  onRunStateRefreshed: (executionId: string) => void
  artifactCountForJob: (jobId: string) => number
  jobErrorMessage: (job: PipelineJob) => string
}

export function useRunExecution(options: RunExecutionOptions) {
  const {
    selectedStudyId,
    currentPipeline,
    selectedNode,
    statusMessage,
    describeError,
    applyRunStateToCanvas,
    onResetTracking,
    onRunStateRefreshed,
    artifactCountForJob,
    jobErrorMessage,
  } = options

  const latestPipelineExecution = ref<PipelineExecution | null>(null)
  const activeExecutionId = ref('')
  const activeExecutionDetail = ref<PipelineExecutionDetail | null>(null)
  const executionJobs = ref<PipelineJob[]>([])
  const runArtifacts = ref<StudyOutput[]>([])
  const runPolling = ref(false)
  const runPollingError = ref('')

  let executionPollTimer: number | null = null
  let executionPollSeq = 0

  const latestPipelineExecutionIssues = computed(() => {
    const errors = latestPipelineExecution.value?.error_json?.errors
    if (!Array.isArray(errors)) return []
    return errors
      .map((item) => (isRecord(item) ? String(item.message || item.code || '') : String(item)))
      .filter(Boolean)
      .slice(0, 3)
  })
  // 运行警告（如 Epoch 跳过了上游没有的条件）：读 result_json.warnings（severity=warning）。
  // 后端已按「一个节点一条」聚合，这里整条显示；最多 3 条防刷屏（更多看 Manifest tab 的「警告 N」）。
  const latestPipelineExecutionWarnings = computed(() => {
    const warnings = latestPipelineExecution.value?.result_json?.warnings
    if (!Array.isArray(warnings)) return []
    return warnings
      .map((item) => (isRecord(item) ? String(item.message || item.code || '') : String(item)))
      .filter(Boolean)
      .slice(0, 3)
  })
  const executionJobByNodeId = computed(() => {
    const map = new Map<string, PipelineJob>()
    for (const job of executionJobs.value) map.set(job.node_id, job)
    return map
  })
  const runArtifactsByJobId = computed(() => {
    const map = new Map<string, StudyOutput[]>()
    for (const artifact of runArtifacts.value) {
      const jobId = artifact.produced_by_job_id
      if (!jobId) continue
      const items = map.get(jobId) || []
      items.push(artifact)
      map.set(jobId, items)
    }
    return map
  })
  const executionPanelJobRows = computed(() =>
    [...executionJobs.value].sort((left, right) => left.topo_index - right.topo_index || left.node_id.localeCompare(right.node_id)),
  )
  const selectedJob = computed(() => (selectedNode.value ? executionJobByNodeId.value.get(selectedNode.value.id) || null : null))
  const selectedNodeArtifacts = computed(() => (selectedJob.value ? runArtifactsByJobId.value.get(selectedJob.value.id) || [] : []))
  const selectedNodeArtifactCount = computed(() => (selectedJob.value ? artifactCountForJob(selectedJob.value.id) : 0))
  const selectedJobError = computed(() => (selectedJob.value ? jobErrorMessage(selectedJob.value) : ''))

  function isTerminalRunStatus(status: string) {
    return ['completed', 'failed', 'waiting_user_input', 'canceled'].includes(status)
  }

  function stopRunPolling(invalidate = true) {
    if (executionPollTimer !== null) {
      window.clearTimeout(executionPollTimer)
      executionPollTimer = null
    }
    runPolling.value = false
    if (invalidate) executionPollSeq += 1
  }

  function resetRunTracking() {
    stopRunPolling()
    activeExecutionId.value = ''
    activeExecutionDetail.value = null
    latestPipelineExecution.value = null
    executionJobs.value = []
    runArtifacts.value = []
    runPollingError.value = ''
    onResetTracking()
    applyRunStateToCanvas()
  }

  // 运行状态轮询的渐进退避间隔：前几拍快（秒级完成的缓存命中运行能立刻看到、
  // 不必干等一个完整的 1.5s 间隔），之后回落到常规间隔，避免长任务（如新算 TFR
  // 16s）高频轮询压后端。pollCount 为「已完成的轮询次数」。
  function nextRunPollDelay(pollCount: number): number {
    if (pollCount <= 2) return 300
    if (pollCount <= 5) return 700
    return EXECUTION_POLL_INTERVAL_MS
  }

  function startRunPolling(executionId = activeExecutionId.value) {
    if (!executionId) return
    stopRunPolling(false)
    runPolling.value = true
    let pollCount = 0
    const tick = async () => {
      await refreshRunState(executionId)
      if (activeExecutionId.value !== executionId || !runPolling.value) return
      if (isTerminalRunStatus(latestPipelineExecution.value?.status || '')) {
        stopRunPolling(false)
        return
      }
      pollCount += 1
      executionPollTimer = window.setTimeout(tick, nextRunPollDelay(pollCount))
    }
    // 立即发起首拍：①已是终态（inline 模式 / 秒杀完成）能瞬间收尾；②让画布立刻
    // 反映「运行中」、用户不必盯着没反应的界面干等 1.5s。后续按退避节奏继续。
    executionPollTimer = window.setTimeout(tick, 0)
  }

  async function refreshRunState(executionId = activeExecutionId.value) {
    const studyId = selectedStudyId.value
    if (!studyId || !executionId) return
    const requestSeq = ++executionPollSeq
    try {
      const [executionRes, jobsRes, artifactsRes] = await Promise.all([
        pipelineApi.getExecution(studyId, executionId),
        pipelineApi.listExecutionJobs(studyId, executionId),
        pipelineApi.listExecutionStudyOutputs(studyId, executionId),
      ])
      if (requestSeq !== executionPollSeq || activeExecutionId.value !== executionId) return
      activeExecutionDetail.value = executionRes.data
      latestPipelineExecution.value = executionRes.data
      executionJobs.value = jobsRes.data.jobs
      runArtifacts.value = artifactsRes.data.study_outputs
      runPollingError.value = ''
      applyRunStateToCanvas()
      onRunStateRefreshed(executionId)
      if (isTerminalRunStatus(executionRes.data.status)) stopRunPolling(false)
    } catch (error) {
      if (requestSeq !== executionPollSeq || activeExecutionId.value !== executionId) return
      runPollingError.value = describeError(error, '运行状态刷新失败')
    }
  }

  async function loadPipelineExecutionById(executionId: string, pipeline: Pipeline) {
    const studyId = selectedStudyId.value
    if (!studyId || !executionId) return false
    const requestSeq = ++executionPollSeq
    activeExecutionId.value = executionId
    try {
      const [executionRes, jobsRes, artifactsRes] = await Promise.all([
        pipelineApi.getExecution(studyId, executionId),
        pipelineApi.listExecutionJobs(studyId, executionId),
        pipelineApi.listExecutionStudyOutputs(studyId, executionId),
      ])
      if (requestSeq !== executionPollSeq || activeExecutionId.value !== executionId) return true
      if (String(executionRes.data.pipeline_id) !== String(pipeline.id)) {
        resetRunTracking()
        return false
      }
      activeExecutionDetail.value = executionRes.data
      latestPipelineExecution.value = executionRes.data
      executionJobs.value = jobsRes.data.jobs
      runArtifacts.value = artifactsRes.data.study_outputs
      runPollingError.value = ''
      statusMessage.value = `已定位运行 #${executionRes.data.execution_seq}`
      applyRunStateToCanvas()
      if (!isTerminalRunStatus(executionRes.data.status)) startRunPolling(executionId)
      return true
    } catch {
      resetRunTracking()
      return false
    }
  }

  async function loadPipelineExecutions(pipeline = currentPipeline.value, targetExecutionId = '') {
    resetRunTracking()
    if (!selectedStudyId.value || !pipeline) return
    if (targetExecutionId) {
      const found = await loadPipelineExecutionById(targetExecutionId, pipeline)
      if (found) return
      statusMessage.value = '未找到指定运行，已显示当前工作流最新运行'
    }
    try {
      const res = await pipelineApi.listExecutions(selectedStudyId.value, pipeline.id, 1)
      latestPipelineExecution.value = res.data.executions[0] || null
      if (latestPipelineExecution.value) {
        activeExecutionId.value = latestPipelineExecution.value.id
        await refreshRunState(latestPipelineExecution.value.id)
        if (!isTerminalRunStatus(latestPipelineExecution.value.status)) startRunPolling(latestPipelineExecution.value.id)
      }
    } catch {
      resetRunTracking()
    }
  }

  // 组件卸载时清掉挂起的轮询 setTimeout：tick 链只在运行进入终态时自停，
  // 页面提前卸载（离开工作流页）后 tick 会继续重排，再次进入页面会叠加幽灵轮询链。
  onUnmounted(() => stopRunPolling())

  return {
    latestPipelineExecution,
    activeExecutionId,
    activeExecutionDetail,
    executionJobs,
    runArtifacts,
    runPolling,
    runPollingError,
    latestPipelineExecutionIssues,
    latestPipelineExecutionWarnings,
    executionJobByNodeId,
    runArtifactsByJobId,
    executionPanelJobRows,
    selectedJob,
    selectedNodeArtifacts,
    selectedNodeArtifactCount,
    selectedJobError,
    loadPipelineExecutions,
    loadPipelineExecutionById,
    refreshRunState,
    startRunPolling,
    stopRunPolling,
    resetRunTracking,
    isTerminalRunStatus,
  }
}
