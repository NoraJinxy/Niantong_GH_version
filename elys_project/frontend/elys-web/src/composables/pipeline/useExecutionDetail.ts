// 工作流编辑器 · 执行详情（Manifest / Lineage / 详情抽屉 tab）
//
// 从 PipelinePage.vue 抽出：执行详情抽屉的 tab 切换 + Manifest / Lineage 的懒加载。
// 不碰画布、不碰运行调度；依赖 activeExecutionId / selectedStudyId / describeError（options 传入）。
// 注意：运行态的 resetRunTracking / refreshRunState 会清空 / 懒触发这里的状态与 load 函数，
// 通过 PipelinePage 解构出的同名引用调用（单向：运行态 → 执行详情）。

import { ref, type Ref, type ComputedRef } from 'vue'
import type { PipelineExecutionLineage } from '@/types'
import { pipelineApi } from '@/api/pipelines'

export type ExecutionDetailTab = 'summary' | 'inputs' | 'jobs' | 'tasks' | 'artifacts' | 'manifest' | 'lineage'

interface ExecutionDetailOptions {
  activeExecutionId: Ref<string>
  selectedStudyId: ComputedRef<string>
  describeError: (error: unknown, fallback: string) => string
}

export function useExecutionDetail(options: ExecutionDetailOptions) {
  const { activeExecutionId, selectedStudyId, describeError } = options

  const activeExecutionManifest = ref<Record<string, unknown> | null>(null)
  const activeExecutionLineage = ref<PipelineExecutionLineage | null>(null)
  const executionDetailTab = ref<ExecutionDetailTab>('artifacts')
  const executionManifestLoading = ref(false)
  const executionManifestError = ref('')
  const executionLineageLoading = ref(false)
  const executionLineageError = ref('')

  function selectExecutionDetailTab(tab: ExecutionDetailTab) {
    executionDetailTab.value = tab
    if (tab === 'manifest') void loadExecutionManifest()
    if (tab === 'lineage') void loadExecutionLineage()
  }

  async function loadExecutionManifest(executionId = activeExecutionId.value) {
    const studyId = selectedStudyId.value
    if (!studyId || !executionId) return
    executionManifestLoading.value = true
    executionManifestError.value = ''
    try {
      const res = await pipelineApi.getExecutionManifest(studyId, executionId)
      if (activeExecutionId.value !== executionId) return
      activeExecutionManifest.value = res.data
    } catch (error) {
      if (activeExecutionId.value !== executionId) return
      executionManifestError.value = describeError(error, '运行 Manifest 读取失败')
    } finally {
      if (activeExecutionId.value === executionId) executionManifestLoading.value = false
    }
  }

  async function loadExecutionLineage(executionId = activeExecutionId.value) {
    const studyId = selectedStudyId.value
    if (!studyId || !executionId) return
    executionLineageLoading.value = true
    executionLineageError.value = ''
    try {
      const res = await pipelineApi.getExecutionLineage(studyId, executionId)
      if (activeExecutionId.value !== executionId) return
      activeExecutionLineage.value = res.data
    } catch (error) {
      if (activeExecutionId.value !== executionId) return
      executionLineageError.value = describeError(error, '运行 lineage 读取失败')
    } finally {
      if (activeExecutionId.value === executionId) executionLineageLoading.value = false
    }
  }

  return {
    activeExecutionManifest,
    activeExecutionLineage,
    executionDetailTab,
    executionManifestLoading,
    executionManifestError,
    executionLineageLoading,
    executionLineageError,
    selectExecutionDetailTab,
    loadExecutionManifest,
    loadExecutionLineage,
  }
}
