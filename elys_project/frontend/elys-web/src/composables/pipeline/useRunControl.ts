// 工作流编辑器 · 运行控制（运行对话框 + 创建 / 取消 / 重试 + 准入判定）
//
// 编排运行流程，依赖运行态核心（useRunExecution 的解构）+ 承重墙 + 保存域，经 options 传入。
// 不直接碰画布（运行后的画布刷新由运行态核心 refreshRunState 内部触发）。
// LoadData 覆盖逻辑作回调 buildRunSelectionOverridePayload 注入，本体留在 PipelinePage / 后续 LoadData 批次。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { Pipeline, PipelineExecution, PipelineExecutionSelectionOverride } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { EXECUTION_CANCELABLE_STATUSES, EXECUTION_RETRYABLE_STATUSES } from './pipelineConstants'
import { formatPipelineStatus, shortId, formatDateTime } from './pipelineFormatters'

interface RunControlOptions {
  selectedStudyId: ComputedRef<string>
  currentPipeline: Ref<Pipeline | null>
  statusMessage: Ref<string>
  dirty: Ref<boolean>
  canSave: ComputedRef<boolean>
  saving: Ref<boolean>
  runningPipeline: Ref<boolean>
  describeError: (error: unknown, fallback: string) => string
  // 运行态核心（useRunExecution 解构）
  latestPipelineExecution: Ref<PipelineExecution | null>
  activeExecutionId: Ref<string>
  refreshRunState: (executionId?: string) => Promise<void>
  startRunPolling: (executionId?: string) => void
  stopRunPolling: (invalidate?: boolean) => void
  resetRunTracking: () => void
  isTerminalRunStatus: (status: string) => boolean
  // 回调
  savePipeline: () => Promise<void>
  buildRunSelectionOverridePayload: () => Record<string, PipelineExecutionSelectionOverride>
}

export function useRunControl(options: RunControlOptions) {
  const {
    selectedStudyId,
    currentPipeline,
    statusMessage,
    dirty,
    canSave,
    saving,
    runningPipeline,
    describeError,
    latestPipelineExecution,
    activeExecutionId,
    refreshRunState,
    startRunPolling,
    stopRunPolling,
    resetRunTracking,
    isTerminalRunStatus,
    savePipeline,
    buildRunSelectionOverridePayload,
  } = options

  const runDialogOpen = ref(false)
  const executionActionLoading = ref<'cancel' | 'retry' | ''>('')
  const runDrawerOpen = ref(false)

  const currentPipelineStatus = computed(() => currentPipeline.value?.status || 'draft')
  const runDisabledReason = computed(() => {
    if (!selectedStudyId.value) return '请选择研究项'
    if (!canSave.value) return '请填写工作流名称'
    if (saving.value) return '正在保存工作流'
    if (runningPipeline.value) return '正在创建运行'
    return ''
  })
  const canOpenRunDialog = computed(() =>
    Boolean(selectedStudyId.value && canSave.value && !saving.value && !runningPipeline.value),
  )
  const canSubmitRun = computed(() => canOpenRunDialog.value)
  const canCancelLatestExecution = computed(() =>
    Boolean(latestPipelineExecution.value && EXECUTION_CANCELABLE_STATUSES.includes(String(latestPipelineExecution.value.status))),
  )
  const canRetryLatestExecution = computed(() =>
    Boolean(latestPipelineExecution.value && EXECUTION_RETRYABLE_STATUSES.includes(String(latestPipelineExecution.value.status))),
  )
  const latestExecutionActionHint = computed(() => {
    if (!latestPipelineExecution.value) return ''
    if (canCancelLatestExecution.value) return '可取消当前排队、运行或等待人工确认的运行；取消会释放运行锁。'
    if (canRetryLatestExecution.value) return '可从失败或已取消的运行创建一个新的运行，旧运行不会被覆盖。'
    return '当前运行状态不支持取消或重试。'
  })
  const runLockSummary = computed(() => {
    const result = latestPipelineExecution.value?.result_json || {}
    const lockId = result.run_lock_id || result.lock_id
    const expiresAt = result.run_lock_expires_at || result.lock_expires_at
    if (!lockId) return '当前没有可显示的运行锁。'
    return `运行锁 ${shortId(String(lockId))}${expiresAt ? ` · 过期 ${formatDateTime(String(expiresAt))}` : ''}`
  })

  function openRunDialog() {
    if (!canOpenRunDialog.value) return
    runDialogOpen.value = true
  }

  function closeRunDialog() {
    if (runningPipeline.value) return
    runDialogOpen.value = false
  }

  async function submitRunDialog() {
    if (!canSubmitRun.value) return
    runDialogOpen.value = false
    await runPipeline()
  }

  async function runPipeline() {
    if (!selectedStudyId.value) return
    if (dirty.value || !currentPipeline.value) {
      await savePipeline()
    }
    if (!currentPipeline.value || dirty.value) return

    runningPipeline.value = true
    statusMessage.value = '正在运行工作流...'
    resetRunTracking()
    try {
      const selectionOverride = buildRunSelectionOverridePayload()
      const res = await pipelineApi.run(selectedStudyId.value, currentPipeline.value.id, {
        ...(Object.keys(selectionOverride).length ? { selection_override: selectionOverride } : {}),
      })
      latestPipelineExecution.value = res.data
      activeExecutionId.value = res.data.id
      await refreshRunState(res.data.id)
      if (latestPipelineExecution.value && !isTerminalRunStatus(latestPipelineExecution.value.status)) startRunPolling(res.data.id)
      statusMessage.value =
        latestPipelineExecution.value?.status === 'completed'
          ? `运行完成：运行 #${latestPipelineExecution.value.execution_seq}，解析 ${latestPipelineExecution.value.dataset_count} 个数据集`
          : latestPipelineExecution.value?.status === 'waiting_user_input'
            ? `等待人工确认：运行 #${latestPipelineExecution.value.execution_seq}`
          : latestPipelineExecution.value?.status === 'running' || latestPipelineExecution.value?.status === 'queued'
            ? `运行中：运行 #${latestPipelineExecution.value.execution_seq}`
            : `运行失败：运行 #${latestPipelineExecution.value?.execution_seq || res.data.execution_seq}，请查看底部错误`
    } catch (error) {
      statusMessage.value = describeError(error, '运行失败')
    } finally {
      runningPipeline.value = false
    }
  }

  async function cancelLatestExecution() {
    const studyId = selectedStudyId.value
    const execution = latestPipelineExecution.value
    if (!studyId || !execution || !canCancelLatestExecution.value || executionActionLoading.value) return
    executionActionLoading.value = 'cancel'
    try {
      const res = await pipelineApi.cancelExecution(studyId, execution.id)
      latestPipelineExecution.value = res.data
      activeExecutionId.value = res.data.id
      await refreshRunState(res.data.id)
      stopRunPolling(false)
      statusMessage.value = `运行 #${res.data.execution_seq} 已取消，运行锁已释放或进入后端释放流程`
    } catch (error) {
      statusMessage.value = describeError(error, '运行取消失败')
    } finally {
      executionActionLoading.value = ''
    }
  }

  async function retryLatestExecution() {
    const studyId = selectedStudyId.value
    const execution = latestPipelineExecution.value
    if (!studyId || !execution || !canRetryLatestExecution.value || executionActionLoading.value) return
    executionActionLoading.value = 'retry'
    try {
      const res = await pipelineApi.retryExecution(studyId, execution.id, { input_policy: 'reuse_snapshot' })
      latestPipelineExecution.value = res.data
      activeExecutionId.value = res.data.id
      resetRunTracking()
      latestPipelineExecution.value = res.data
      activeExecutionId.value = res.data.id
      await refreshRunState(res.data.id)
      if (latestPipelineExecution.value && !isTerminalRunStatus(latestPipelineExecution.value.status)) startRunPolling(res.data.id)
      statusMessage.value = `已从运行 #${execution.execution_seq} 创建重试运行：运行 #${res.data.execution_seq}`
    } catch (error) {
      statusMessage.value = describeError(error, '运行重试失败')
    } finally {
      executionActionLoading.value = ''
    }
  }

  return {
    runDialogOpen,
    executionActionLoading,
    runDrawerOpen,
    currentPipelineStatus,
    runDisabledReason,
    canOpenRunDialog,
    canSubmitRun,
    canCancelLatestExecution,
    canRetryLatestExecution,
    latestExecutionActionHint,
    runLockSummary,
    openRunDialog,
    closeRunDialog,
    submitRunDialog,
    runPipeline,
    cancelLatestExecution,
    retryLatestExecution,
  }
}
