// 工作流编辑器 · 异步任务事件流（取消 / 重试 / 拉取事件）
//
// 从 PipelinePage.vue 抽出：执行详情里的 AsyncTask 列表操作。依赖执行态
// （activeExecutionId / activeExecutionDetail）+ selectedStudyId / statusMessage +
// describeError / refreshRunState，经 options 传入；任务级 loading 与事件缓存自持。

import { reactive, type Ref, type ComputedRef } from 'vue'
import type { AsyncTask, TaskEvent, PipelineExecutionDetail } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { shortId } from './pipelineFormatters'
import { TASK_CANCELABLE_STATUSES, TASK_RETRYABLE_STATUSES } from './pipelineConstants'

interface ExecutionTasksOptions {
  selectedStudyId: ComputedRef<string>
  statusMessage: Ref<string>
  activeExecutionId: Ref<string>
  activeExecutionDetail: Ref<PipelineExecutionDetail | null>
  refreshRunState: (executionId?: string) => Promise<void> | void
  describeError: (error: unknown, fallback: string) => string
}

export function useExecutionTasks(options: ExecutionTasksOptions) {
  const { selectedStudyId, statusMessage, activeExecutionId, activeExecutionDetail, refreshRunState, describeError } = options

  const taskActionLoading = reactive<Record<string, 'cancel' | 'retry' | 'events'>>({})
  const taskEventsByTaskId = reactive<Record<string, TaskEvent[]>>({})

  function isPipelineExecutionTask(task: AsyncTask) {
    return task.resource_kind === 'pipeline_execution' || task.task_type === 'pipeline_execution'
  }

  function taskEventsForTask(task: AsyncTask) {
    return taskEventsByTaskId[task.id] || task.events || []
  }

  function canCancelTask(task: AsyncTask) {
    return TASK_CANCELABLE_STATUSES.includes(String(task.status))
  }

  function canRetryTask(task: AsyncTask) {
    return !isPipelineExecutionTask(task) && TASK_RETRYABLE_STATUSES.includes(String(task.status))
  }

  async function loadTaskEvents(task: AsyncTask) {
    const studyId = selectedStudyId.value
    if (!studyId || taskActionLoading[task.id]) return
    taskActionLoading[task.id] = 'events'
    try {
      const events = taskEventsForTask(task)
      const since = events.length ? events[events.length - 1].id : undefined
      const res = await pipelineApi.listTaskEvents(studyId, task.id, since)
      taskEventsByTaskId[task.id] = mergeTaskEvents(events, res.data.events)
      statusMessage.value = `已刷新任务事件：${taskEventsByTaskId[task.id].length} 条`
    } catch (error) {
      statusMessage.value = describeError(error, '任务事件刷新失败')
    } finally {
      delete taskActionLoading[task.id]
    }
  }

  async function cancelTask(task: AsyncTask) {
    const studyId = selectedStudyId.value
    if (!studyId || !canCancelTask(task) || taskActionLoading[task.id]) return
    taskActionLoading[task.id] = 'cancel'
    try {
      const res = await pipelineApi.cancelTask(studyId, task.id)
      updateActiveRunTask(res.data)
      taskEventsByTaskId[task.id] = res.data.events || []
      if (activeExecutionId.value) await refreshRunState(activeExecutionId.value)
      statusMessage.value = isPipelineExecutionTask(task)
        ? 'Pipeline Run 任务已取消；对应 Run 状态和运行锁已同步刷新'
        : '任务已取消'
    } catch (error) {
      statusMessage.value = describeError(error, '任务取消失败')
    } finally {
      delete taskActionLoading[task.id]
    }
  }

  async function retryTask(task: AsyncTask) {
    const studyId = selectedStudyId.value
    if (!studyId || !canRetryTask(task) || taskActionLoading[task.id]) return
    taskActionLoading[task.id] = 'retry'
    try {
      const res = await pipelineApi.retryTask(studyId, task.id)
      statusMessage.value = `任务重试已创建：${shortId(res.data.id)}`
    } catch (error) {
      statusMessage.value = describeError(error, '任务重试失败')
    } finally {
      delete taskActionLoading[task.id]
    }
  }

  function updateActiveRunTask(updatedTask: AsyncTask) {
    if (!activeExecutionDetail.value?.tasks) return
    activeExecutionDetail.value.tasks = activeExecutionDetail.value.tasks.map((task) =>
      task.id === updatedTask.id ? updatedTask : task,
    )
  }

  function mergeTaskEvents(existing: TaskEvent[], incoming: TaskEvent[]) {
    const byId = new Map<string, TaskEvent>()
    for (const event of [...existing, ...incoming]) byId.set(event.id, event)
    return Array.from(byId.values()).sort((left, right) =>
      String(left.created_at || '').localeCompare(String(right.created_at || '')) || left.id.localeCompare(right.id),
    )
  }

  return {
    taskActionLoading,
    taskEventsByTaskId,
    isPipelineExecutionTask,
    taskEventsForTask,
    canCancelTask,
    canRetryTask,
    loadTaskEvents,
    cancelTask,
    retryTask,
  }
}
