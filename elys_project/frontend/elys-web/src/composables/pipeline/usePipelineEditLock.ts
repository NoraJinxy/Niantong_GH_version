// 工作流编辑器 · 编辑锁（获取 / 续期 / 释放）
//
// 从 PipelinePage.vue 抽出的乐观编辑锁：防多人同时改同一工作流。完全独立——
// 只依赖 selectedStudyId / currentPipeline / statusMessage / describeError（options 传入），
// 不碰运行态、不碰画布，是执行态大簇里最干净的一块。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { Pipeline, PipelineEditLock } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { formatDateTime } from './pipelineFormatters'

interface PipelineEditLockOptions {
  selectedStudyId: ComputedRef<string>
  currentPipeline: Ref<Pipeline | null>
  statusMessage: Ref<string>
  describeError: (error: unknown, fallback: string) => string
}

export function usePipelineEditLock(options: PipelineEditLockOptions) {
  const { selectedStudyId, currentPipeline, statusMessage, describeError } = options

  const pipelineEditLock = ref<PipelineEditLock | null>(null)
  const pipelineEditLockLoading = ref(false)
  const pipelineEditLockError = ref('')

  const pipelineEditLockSummary = computed(() => {
    if (pipelineEditLockError.value) return pipelineEditLockError.value
    if (!currentPipeline.value) return '保存工作流后可获取编辑锁。'
    if (!pipelineEditLock.value) return '尚未获取编辑锁；保存时后端仍会检查他人锁。'
    return `编辑锁由 ${pipelineEditLock.value.locked_by || '未知用户'} 持有，过期 ${formatDateTime(pipelineEditLock.value.expires_at)}`
  })

  const canUsePipelineEditLockActions = computed(() =>
    Boolean(selectedStudyId.value && currentPipeline.value && !pipelineEditLockLoading.value),
  )

  async function acquirePipelineEditLock() {
    if (!selectedStudyId.value || !currentPipeline.value || pipelineEditLockLoading.value) return
    pipelineEditLockLoading.value = true
    pipelineEditLockError.value = ''
    try {
      const res = await pipelineApi.acquireEditLock(selectedStudyId.value, currentPipeline.value.id)
      pipelineEditLock.value = res.data
      statusMessage.value = `已获取编辑锁，过期 ${formatDateTime(res.data.expires_at)}`
    } catch (error) {
      pipelineEditLockError.value = describeError(error, '编辑锁获取失败')
      statusMessage.value = pipelineEditLockError.value
    } finally {
      pipelineEditLockLoading.value = false
    }
  }

  async function refreshPipelineEditLock() {
    if (!selectedStudyId.value || !currentPipeline.value || pipelineEditLockLoading.value) return
    pipelineEditLockLoading.value = true
    pipelineEditLockError.value = ''
    try {
      const res = await pipelineApi.refreshEditLock(selectedStudyId.value, currentPipeline.value.id)
      pipelineEditLock.value = res.data
      statusMessage.value = `编辑锁已续期，过期 ${formatDateTime(res.data.expires_at)}`
    } catch (error) {
      pipelineEditLockError.value = describeError(error, '编辑锁续期失败')
      statusMessage.value = pipelineEditLockError.value
    } finally {
      pipelineEditLockLoading.value = false
    }
  }

  async function releasePipelineEditLock() {
    if (!selectedStudyId.value || !currentPipeline.value || pipelineEditLockLoading.value) return
    pipelineEditLockLoading.value = true
    pipelineEditLockError.value = ''
    try {
      await pipelineApi.releaseEditLock(selectedStudyId.value, currentPipeline.value.id)
      pipelineEditLock.value = null
      statusMessage.value = '编辑锁已释放'
    } catch (error) {
      pipelineEditLockError.value = describeError(error, '编辑锁释放失败')
      statusMessage.value = pipelineEditLockError.value
    } finally {
      pipelineEditLockLoading.value = false
    }
  }

  return {
    pipelineEditLock,
    pipelineEditLockLoading,
    pipelineEditLockError,
    pipelineEditLockSummary,
    canUsePipelineEditLockActions,
    acquirePipelineEditLock,
    refreshPipelineEditLock,
    releasePipelineEditLock,
  }
}
