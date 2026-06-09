// 工作流编辑器 · 草稿自动暂存 / 恢复（localStorage）
//
// 从 PipelinePage.vue 抽出：编辑期 debounce 写入草稿、切回页面静默恢复、过期清理。
// 依赖承重墙 definition + 编辑元数据（name/desc/study/pipeline/currentPipeline）+ 共享标志
// （dirty/statusMessage/hydrating），均以 Ref/ComputedRef 通过 options 传入、保持响应式；
// syncDefinitionToLiteGraph 是恢复草稿后让 LiteGraph 重绘的回调。

import { ref, type Ref, type ComputedRef } from 'vue'
import type { Pipeline, PipelineDefinitionPayload } from '@/types'
import { DRAFT_LS_PREFIX, DRAFT_STORAGE_VERSION } from './pipelineConstants'

interface PipelineDraft {
  storageVersion: number
  studyId: string
  pipelineId: string
  definition: PipelineDefinitionPayload
  name: string
  description: string
  savedAt: string
  // 远程版本快照（用于检测后端是否被他人改过 → 草稿过期）
  baselineUpdatedAt: string | null
}

interface DraftPersistenceOptions {
  definition: Ref<PipelineDefinitionPayload>
  pipelineName: Ref<string>
  pipelineDescription: Ref<string>
  selectedStudyId: ComputedRef<string>
  selectedPipelineId: Ref<string>
  currentPipeline: Ref<Pipeline | null>
  dirty: Ref<boolean>
  statusMessage: Ref<string>
  hydrating: Ref<boolean>
  syncDefinitionToLiteGraph: () => void
}

export function useDraftPersistence(options: DraftPersistenceOptions) {
  const {
    definition,
    pipelineName,
    pipelineDescription,
    selectedStudyId,
    selectedPipelineId,
    currentPipeline,
    dirty,
    statusMessage,
    hydrating,
    syncDefinitionToLiteGraph,
  } = options

  let draftSaveTimer: number | null = null
  const draftJustRestored = ref(false)

  function draftStorageKey(studyId: string, pipelineId: string): string {
    return `${DRAFT_LS_PREFIX}${studyId}-${pipelineId || 'new'}`
  }

  /** 防抖写入 localStorage（800ms 内多次 markDirty 只写一次）。 */
  function scheduleDraftSave() {
    if (hydrating.value) return
    if (!selectedStudyId.value) return
    if (draftSaveTimer !== null) window.clearTimeout(draftSaveTimer)
    draftSaveTimer = window.setTimeout(() => {
      draftSaveTimer = null
      const key = draftStorageKey(selectedStudyId.value, selectedPipelineId.value || 'new')
      const draft: PipelineDraft = {
        storageVersion: DRAFT_STORAGE_VERSION,
        studyId: selectedStudyId.value,
        pipelineId: selectedPipelineId.value || 'new',
        definition: definition.value,
        name: pipelineName.value,
        description: pipelineDescription.value,
        savedAt: new Date().toISOString(),
        baselineUpdatedAt: currentPipeline.value?.updated_at || null,
      }
      try {
        localStorage.setItem(key, JSON.stringify(draft))
      } catch {
        // localStorage 满 / 浏览器禁用 → 静默失败
      }
    }, 800)
  }

  /** 删除当前 (study, pipeline) 的暂存草稿。 */
  function clearDraft(studyId?: string, pipelineId?: string) {
    const sid = studyId ?? selectedStudyId.value
    const pid = pipelineId ?? selectedPipelineId.value
    if (!sid) return
    try {
      localStorage.removeItem(draftStorageKey(sid, pid || 'new'))
    } catch {
      // ignore
    }
  }

  /** 尝试从 localStorage 恢复草稿。返回是否成功恢复。
   *
   * 触发时机：加载远程 pipeline 完成后 / 新建空 pipeline 后。
   * 跳过条件：draft 不存在 / 格式版本不匹配 / baselineUpdatedAt 与当前远程版本不一致（草稿过期）。
   */
  function tryRestoreDraft(): boolean {
    if (!selectedStudyId.value) return false
    const key = draftStorageKey(selectedStudyId.value, selectedPipelineId.value || 'new')
    let raw: string | null = null
    try {
      raw = localStorage.getItem(key)
    } catch {
      return false
    }
    if (!raw) return false
    let draft: PipelineDraft | null = null
    try {
      draft = JSON.parse(raw) as PipelineDraft
    } catch {
      // 解析失败 → 清掉脏数据
      try { localStorage.removeItem(key) } catch { /* ignore */ }
      return false
    }
    if (!draft || draft.storageVersion !== DRAFT_STORAGE_VERSION) return false
    const currentBaseline = currentPipeline.value?.updated_at || null
    if (draft.baselineUpdatedAt !== currentBaseline) {
      // 远程版本变了，草稿过期 → 清掉避免误覆盖
      try { localStorage.removeItem(key) } catch { /* ignore */ }
      return false
    }
    // 应用草稿
    hydrating.value = true
    definition.value = draft.definition
    pipelineName.value = draft.name
    pipelineDescription.value = draft.description
    hydrating.value = false
    dirty.value = true
    draftJustRestored.value = true
    // 让 LiteGraph 重绘
    syncDefinitionToLiteGraph()
    // 状态提示（4 秒后自动清）
    const minutesAgo = Math.max(0, Math.round((Date.now() - new Date(draft.savedAt).getTime()) / 60000))
    statusMessage.value = minutesAgo > 0
      ? `已恢复 ${minutesAgo} 分钟前的未保存草稿`
      : '已恢复刚刚的未保存草稿'
    window.setTimeout(() => { draftJustRestored.value = false }, 4000)
    return true
  }

  return { draftJustRestored, scheduleDraftSave, clearDraft, tryRestoreDraft }
}
