// 工作流编辑器 · 产物管理（改名 / 标签 / 保留 / 下载 / 清理）
//
// 从 PipelinePage.vue 抽出：执行详情抽屉里对 StudyOutput 结果的行内操作。
// 依赖运行态（runArtifacts/activeExecutionId）+ 产物预览（selectedArtifactPreview/resetArtifactPreview）
// + 执行详情（executionDetailTab/loadExecutionLineage）+ selectedStudyId/statusMessage/describeError，经 options 传入。

import { reactive, ref, type Ref, type ComputedRef } from 'vue'
import type { StudyOutput, StudyOutputPreview } from '@/types'
import { pipelineApi } from '@/api/pipelines'
import { shortId, formatArtifactRetention } from './pipelineFormatters'
import type { ExecutionDetailTab } from './useExecutionDetail'

export type ArtifactAction = 'pin' | 'unpin' | 'hide' | 'download'

interface ArtifactActionsOptions {
  selectedStudyId: ComputedRef<string>
  statusMessage: Ref<string>
  describeError: (error: unknown, fallback: string) => string
  runArtifacts: Ref<StudyOutput[]>
  activeExecutionId: Ref<string>
  selectedArtifactPreview: Ref<StudyOutputPreview | null>
  resetArtifactPreview: () => void
  executionDetailTab: Ref<ExecutionDetailTab>
  loadExecutionLineage: (executionId?: string) => Promise<void>
}

export function useArtifactActions(options: ArtifactActionsOptions) {
  const {
    selectedStudyId,
    statusMessage,
    describeError,
    runArtifacts,
    activeExecutionId,
    selectedArtifactPreview,
    resetArtifactPreview,
    executionDetailTab,
    loadExecutionLineage,
  } = options

  const artifactActionLoading = reactive<Record<string, ArtifactAction | 'cleanup'>>({})
  const artifactCleanupLoading = ref(false)
  const editingDisplayId = ref('')
  const displayNameDraft = ref('')
  const tagDrafts = reactive<Record<string, string>>({})

  function derivedRetentionPillClass(artifact: StudyOutput): string {
    if (artifact.deleted_at) return 'status-pill--deleted'
    if (artifact.keep) return 'status-pill--current'
    if (artifact.cache_eligible) return 'status-pill--cached'
    return 'status-pill--temporary'
  }

  function startEditDisplayName(artifact: StudyOutput) {
    editingDisplayId.value = artifact.id
    displayNameDraft.value = artifact.display_name || ''
  }

  function cancelEditDisplayName() {
    editingDisplayId.value = ''
    displayNameDraft.value = ''
  }

  async function commitDisplayName(artifact: StudyOutput) {
    if (editingDisplayId.value !== artifact.id) return
    const studyId = selectedStudyId.value
    const next = displayNameDraft.value.trim()
    const previous = (artifact.display_name || '').trim()
    editingDisplayId.value = ''
    if (!studyId || next === previous) return
    try {
      const res = await pipelineApi.updateStudyOutput(studyId, artifact.id, {
        display_name: next || null,
      })
      runArtifacts.value = runArtifacts.value.map((item) =>
        item.id === artifact.id ? { ...item, display_name: res.data.display_name } : item,
      )
      statusMessage.value = '结果名称已更新'
    } catch (error) {
      statusMessage.value = describeError(error, '改名失败')
    }
  }

  function tagDraftFor(id: string): string {
    return tagDrafts[id] || ''
  }

  function setTagDraft(id: string, value: string) {
    tagDrafts[id] = value
  }

  async function commitTagDraft(artifact: StudyOutput) {
    const studyId = selectedStudyId.value
    const draft = (tagDrafts[artifact.id] || '').trim()
    if (!studyId || !draft) return
    const tags = [...(artifact.tags || [])]
    if (!tags.includes(draft)) tags.push(draft)
    try {
      const res = await pipelineApi.updateStudyOutput(studyId, artifact.id, { tags })
      runArtifacts.value = runArtifacts.value.map((item) =>
        item.id === artifact.id ? { ...item, tags: res.data.tags } : item,
      )
      tagDrafts[artifact.id] = ''
    } catch (error) {
      statusMessage.value = describeError(error, '加标签失败')
    }
  }

  async function removeDerivedTag(artifact: StudyOutput, tag: string) {
    const studyId = selectedStudyId.value
    if (!studyId) return
    const tags = (artifact.tags || []).filter((item) => item !== tag)
    try {
      const res = await pipelineApi.updateStudyOutput(studyId, artifact.id, { tags })
      runArtifacts.value = runArtifacts.value.map((item) =>
        item.id === artifact.id ? { ...item, tags: res.data.tags } : item,
      )
    } catch (error) {
      statusMessage.value = describeError(error, '移除标签失败')
    }
  }

  async function setArtifactRetentionAction(artifact: StudyOutput, action: ArtifactAction) {
    const studyId = selectedStudyId.value
    if (!studyId || artifactActionLoading[artifact.id]) return
    artifactActionLoading[artifact.id] = action
    try {
      const reason = `frontend_${action}`
      const payload: { keep?: boolean; deleted?: boolean } =
        action === 'pin' ? { keep: true } : action === 'unpin' ? { keep: false } : { deleted: true }
      const res = await pipelineApi.updateStudyOutput(studyId, artifact.id, {
        ...payload,
        reason,
      })
      const updated = res.data as StudyOutput
      if (action === 'hide') {
        runArtifacts.value = runArtifacts.value.filter((item) => item.id !== artifact.id)
        if (selectedArtifactPreview.value?.study_output_id === artifact.id) resetArtifactPreview()
      } else {
        runArtifacts.value = runArtifacts.value.map((item) => (item.id === artifact.id ? { ...item, ...updated } : item))
      }
      if (activeExecutionId.value) {
        if (executionDetailTab.value === 'lineage') void loadExecutionLineage(activeExecutionId.value)
        statusMessage.value = artifactActionStatusText(action, updated)
      }
    } catch (error) {
      statusMessage.value = describeError(error, '结果操作失败')
    } finally {
      delete artifactActionLoading[artifact.id]
    }
  }

  function isArtifactActionLoading(artifact: StudyOutput, action: ArtifactAction) {
    return artifactActionLoading[artifact.id] === action
  }

  async function cleanupCachedArtifacts() {
    const studyId = selectedStudyId.value
    if (!studyId || artifactCleanupLoading.value) return
    artifactCleanupLoading.value = true
    try {
      const res = await pipelineApi.cleanupStudyOutputs(studyId, {
        dry_run: false,
        limit: 500,
        reason: 'frontend_cleanup_cached_derived',
      })
      statusMessage.value = `清理任务已创建：${shortId(res.data.id)}`
    } catch (error) {
      statusMessage.value = describeError(error, '清理任务创建失败')
    } finally {
      artifactCleanupLoading.value = false
    }
  }

  async function downloadArtifact(artifact: StudyOutput) {
    const studyId = selectedStudyId.value
    if (!studyId || artifactActionLoading[artifact.id]) return
    artifactActionLoading[artifact.id] = 'download'
    try {
      const res = await pipelineApi.downloadStudyOutput(studyId, artifact.id)
      const blob = res.data
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = artifactDownloadName(artifact)
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      statusMessage.value = `已下载结果：${shortId(artifact.id)}`
    } catch (error) {
      statusMessage.value = describeError(error, '结果下载失败')
    } finally {
      delete artifactActionLoading[artifact.id]
    }
  }

  function artifactActionStatusText(action: ArtifactAction, artifact?: StudyOutput | null) {
    if (action === 'pin') return `输出已设为保留：${formatArtifactRetention(artifact)}`
    if (action === 'unpin') return `输出已设为不保留：${formatArtifactRetention(artifact)}`
    if (action === 'download') return '输出已下载'
    return '输出已删除'
  }

  function artifactDownloadName(artifact: StudyOutput) {
    if (artifact.display_name && artifact.display_name.trim()) {
      return artifact.display_name.trim().replace(/[\\/:*?"<>|]/g, '_')
    }
    if (artifact.logical_path) {
      const tail = String(artifact.logical_path).split('/').pop()
      if (tail) return tail
    }
    const extension = artifact.data_type === 'figure' ? '.png' : ''
    return `derived-${shortId(artifact.id)}${extension}`
  }

  return {
    artifactActionLoading,
    artifactCleanupLoading,
    editingDisplayId,
    displayNameDraft,
    tagDrafts,
    derivedRetentionPillClass,
    startEditDisplayName,
    cancelEditDisplayName,
    commitDisplayName,
    tagDraftFor,
    setTagDraft,
    commitTagDraft,
    removeDerivedTag,
    setArtifactRetentionAction,
    isArtifactActionLoading,
    cleanupCachedArtifacts,
    downloadArtifact,
  }
}
