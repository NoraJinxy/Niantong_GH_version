// 数据集页 · 采集记录（recordings）
//
// 从 DatasetsPage.vue 抽出：所选数据集在研究项下的采集记录列表、按被试分组、
// 每条记录文件的懒加载与 2 桶拆分。依赖 catalog 的 selectedDatasetAsset 与页面
// recordsStudyContext（哪个 study / mount 下找记录），均经 options 注入。
// 触发时机的 watch（selectedDatasetAssetId / activeTab=data 等）仍留在页面统一编排。
//
// 工程债评审（日志/6_工程债评审260612「工程债评审与重构路线」§2.2 前端上帝组件）：
// DatasetsPage.vue 拆分批 4。

import { computed, ref, type ComputedRef } from 'vue'
import { recordingApi, type RecordingQaResponse, type RecordingQaReviewPayload } from '@/api/datasetAssets'
import type { DatasetAsset, DatasetFile, Recording, RecordingRelabelPayload, RecordingVersion } from '@/types'
import {
  fileBucketOf,
  formatChannelEvent,
  formatSourceFormat,
  getCurrentVersionLabel,
  getDateValue,
  getRecordingErrorMessage,
  getRecordingFilesErrorMessage,
  getRecordingUpdatedAt,
  isQaPassed,
  sumFileSize,
} from './datasetsFormatters'

export interface DatasetRecordingRow {
  id: string
  subject: string
  session: string | null
  task: string
  run: string | null
  sourceFormat: string
  currentVersionLabel: string
  currentVersionSeq: number | null
  hasCanonicalFif: boolean
  channelEventLabel: string
  qaStatus: string | null
  updatedAt: string | null
  fileSize: number | null
  datasetAssetId: string | null
}

export interface RecordsStudyContext {
  studyId: string
  studyName: string
  mountId?: string
  mountName?: string
}

interface DatasetRecordingsOptions {
  selectedDatasetAsset: ComputedRef<DatasetAsset | null>
  recordsStudyContext: ComputedRef<RecordsStudyContext | null>
}

export function useDatasetRecordings(options: DatasetRecordingsOptions) {
  const { selectedDatasetAsset, recordsStudyContext } = options

  const selectedAssetRecordings = ref<DatasetRecordingRow[]>([])
  const expandedRecordingIds = ref<string[]>([])
  const recordingFilesById = ref<Record<string, DatasetFile[]>>({})
  const recordingFilesLoading = ref<Record<string, boolean>>({})
  const recordingFilesError = ref<Record<string, string>>({})
  // 每条记录的「第几次上传」历史（含真实源文件名）。懒加载、按 version_seq 倒序。
  const recordingVersionsById = ref<Record<string, RecordingVersion[]>>({})
  const recordingVersionsLoading = ref<Record<string, boolean>>({})
  // 每条记录的质控（mock）报告，懒加载
  const recordingQaById = ref<Record<string, RecordingQaResponse>>({})
  const recordingQaLoading = ref<Record<string, boolean>>({})
  const isLoadingRecordings = ref(false)
  const recordingsError = ref('')

  // 原始数据格式提示（取记录里出现过的源格式，如 BrainVision / EDF）
  const uploadFormatHint = computed(() => {
    const formats = Array.from(
      new Set(selectedAssetRecordings.value.map((r) => r.sourceFormat).filter((f) => f && f !== '-')),
    )
    return formats.length ? ` · ${formats.join(' / ')}` : ''
  })

  // 按被试分组（按被试视图）
  const recordingsBySubject = computed(() => {
    const groups = new Map<string, { subject: string; recordings: DatasetRecordingRow[]; size: number }>()
    for (const recording of selectedAssetRecordings.value) {
      let group = groups.get(recording.subject)
      if (!group) {
        group = { subject: recording.subject, recordings: [], size: 0 }
        groups.set(recording.subject, group)
      }
      group.recordings.push(recording)
      group.size += recording.fileSize || 0
    }
    // 被试正序：sub-01、sub-02…（numeric 让内嵌数字按数值比，sub-2 < sub-10）。
    // 源列表按 updatedAt 倒序，分组若沿用插入序会变成「最新上传在最前」，与直觉相反。
    return Array.from(groups.values()).sort((a, b) =>
      a.subject.localeCompare(b.subject, undefined, { numeric: true, sensitivity: 'base' }),
    )
  })

  // 每条记录的文件按 2 桶 + 技术拆分（按被试视图每条记录的数据行）
  const recordingBucketsById = computed(() => {
    const out: Record<
      string,
      { upload: DatasetFile[]; fif: DatasetFile[]; tech: DatasetFile[]; uploadSize: number; fifSize: number }
    > = {}
    for (const [id, files] of Object.entries(recordingFilesById.value)) {
      const upload = files.filter((f) => fileBucketOf(f) === 'upload')
      const fif = files.filter((f) => fileBucketOf(f) === 'fif')
      const tech = files.filter((f) => fileBucketOf(f) === 'tech')
      out[id] = { upload, fif, tech, uploadSize: sumFileSize(upload), fifSize: sumFileSize(fif) }
    }
    return out
  })

  const recordingStats = computed(() => ({
    total: selectedAssetRecordings.value.length,
    withCanonicalFif: selectedAssetRecordings.value.filter((recording) => recording.hasCanonicalFif).length,
    qcPassed: selectedAssetRecordings.value.filter((recording) => isQaPassed(recording.qaStatus)).length,
  }))

  function normalizeRecording(recording: Recording): DatasetRecordingRow {
    return {
      id: recording.id,
      subject: recording.bids_subject_id || recording.subject_id || '-',
      session: recording.session || null,
      task: recording.task || '-',
      run: recording.run || null,
      sourceFormat: formatSourceFormat(recording.source_format),
      currentVersionLabel: getCurrentVersionLabel(recording),
      currentVersionSeq: recording.current_version_seq ?? null,
      hasCanonicalFif: Boolean(recording.fif_path || recording.current_version_id),
      channelEventLabel: formatChannelEvent(recording.n_channels, recording.n_events),
      qaStatus: recording.qa_status || null,
      updatedAt: getRecordingUpdatedAt(recording),
      fileSize: recording.file_size || null,
      datasetAssetId: recording.dataset_asset_id || null,
    }
  }

  async function loadSelectedAssetRecordings() {
    const asset = selectedDatasetAsset.value
    const context = recordsStudyContext.value
    recordingsError.value = ''
    selectedAssetRecordings.value = []
    expandedRecordingIds.value = []
    recordingFilesById.value = {}
    recordingFilesLoading.value = {}
    recordingFilesError.value = {}
    recordingVersionsById.value = {}
    recordingVersionsLoading.value = {}
    recordingQaById.value = {}
    recordingQaLoading.value = {}
    if (!asset || !context) return

    isLoadingRecordings.value = true
    try {
      const res = await recordingApi.list(context.studyId, {
        dataset_asset_id: asset.id,
        mount_id: context.mountId,
        mount_name: context.mountName,
      })
      selectedAssetRecordings.value = res.data.recordings
        .map(normalizeRecording)
        .sort((a, b) => getDateValue(b.updatedAt) - getDateValue(a.updatedAt))
    } catch (err: any) {
      selectedAssetRecordings.value = []
      recordingsError.value = getRecordingErrorMessage(err)
    } finally {
      isLoadingRecordings.value = false
    }
  }

  function resetRecordsView() {
    selectedAssetRecordings.value = []
    expandedRecordingIds.value = []
    recordingFilesById.value = {}
    recordingFilesLoading.value = {}
    recordingFilesError.value = {}
    recordingVersionsById.value = {}
    recordingVersionsLoading.value = {}
    recordingQaById.value = {}
    recordingQaLoading.value = {}
    recordingsError.value = ''
  }

  function isRecordingExpanded(recording: DatasetRecordingRow) {
    return expandedRecordingIds.value.includes(recording.id)
  }

  async function toggleRecordingExpanded(recording: DatasetRecordingRow) {
    if (isRecordingExpanded(recording)) {
      expandedRecordingIds.value = expandedRecordingIds.value.filter((id) => id !== recording.id)
      return
    }
    expandedRecordingIds.value = [...expandedRecordingIds.value, recording.id]
    await loadRecordingFiles(recording)
  }

  async function loadRecordingFiles(recording: DatasetRecordingRow, force = false) {
    const context = recordsStudyContext.value
    if (!context) return
    if (!force && recordingFilesById.value[recording.id]) return

    setRecordingFileLoading(recording.id, true)
    setRecordingFileError(recording.id, '')
    try {
      const res = await recordingApi.listFiles(context.studyId, recording.id)
      recordingFilesById.value = {
        ...recordingFilesById.value,
        [recording.id]: res.data.files,
      }
    } catch (err: any) {
      setRecordingFileError(recording.id, getRecordingFilesErrorMessage(err))
      recordingFilesById.value = {
        ...recordingFilesById.value,
        [recording.id]: [],
      }
    } finally {
      setRecordingFileLoading(recording.id, false)
    }
  }

  function setRecordingFileLoading(recordingId: string, value: boolean) {
    recordingFilesLoading.value = {
      ...recordingFilesLoading.value,
      [recordingId]: value,
    }
  }

  function setRecordingFileError(recordingId: string, value: string) {
    recordingFilesError.value = {
      ...recordingFilesError.value,
      [recordingId]: value,
    }
  }

  // 「调整归类」：改一条采集记录的 BIDS 实体（被试/会话/任务/轮次）。后端会物理重排派生层并排重。
  async function relabelRecording(recording: DatasetRecordingRow, payload: RecordingRelabelPayload) {
    const context = recordsStudyContext.value
    if (!context) throw new Error('缺少研究项上下文，无法调整归类')
    await recordingApi.relabel(context.studyId, recording.id, payload)
  }

  // 删除/排除一条采集记录（不可恢复）。调用方负责删除后刷新列表。
  async function deleteRecording(recording: DatasetRecordingRow) {
    const context = recordsStudyContext.value
    if (!context) throw new Error('缺少研究项上下文，无法删除记录')
    await recordingApi.remove(context.studyId, recording.id)
  }

  // 质控：读已有报告（懒加载）。无报告/失败时落空对象，抽屉据此显示「跑质控」。
  async function loadRecordingQa(recording: DatasetRecordingRow, force = false) {
    const context = recordsStudyContext.value
    if (!context) return
    if (!force && recordingQaById.value[recording.id]) return
    recordingQaLoading.value = { ...recordingQaLoading.value, [recording.id]: true }
    try {
      const res = await recordingApi.qaReport(context.studyId, recording.id)
      recordingQaById.value = { ...recordingQaById.value, [recording.id]: res.data }
    } catch {
      recordingQaById.value = { ...recordingQaById.value, [recording.id]: {} }
    } finally {
      recordingQaLoading.value = { ...recordingQaLoading.value, [recording.id]: false }
    }
  }

  // 把质控结果落地：更新抽屉报告 + 就地同步表格那行的 qaStatus（不整列刷新、不丢已加载的报告）。
  function applyQaResult(recordingId: string, res: RecordingQaResponse) {
    recordingQaById.value = { ...recordingQaById.value, [recordingId]: res }
    if (res.qa_status != null) {
      const row = selectedAssetRecordings.value.find((r) => r.id === recordingId)
      if (row) row.qaStatus = res.qa_status
    }
  }

  // 质控：生成 / 刷新 mock 报告。
  async function runRecordingQa(recording: DatasetRecordingRow) {
    const context = recordsStudyContext.value
    if (!context) throw new Error('缺少研究项上下文，无法运行质控')
    const res = await recordingApi.runQa(context.studyId, recording.id)
    applyQaResult(recording.id, res.data)
  }

  // 质控：人工复核（通过 accept / 驳回 reject / 暂存 hold）。
  async function reviewRecordingQa(recording: DatasetRecordingRow, payload: RecordingQaReviewPayload) {
    const context = recordsStudyContext.value
    if (!context) throw new Error('缺少研究项上下文，无法复核质控')
    const res = await recordingApi.reviewQa(context.studyId, recording.id, payload)
    applyQaResult(recording.id, res.data)
  }

  // 拉某条记录的「第几次上传」历史；按 version_seq 倒序（最新一次在前）。
  async function loadRecordingVersions(recording: DatasetRecordingRow, force = false) {
    const context = recordsStudyContext.value
    if (!context) return
    if (!force && recordingVersionsById.value[recording.id]) return

    recordingVersionsLoading.value = { ...recordingVersionsLoading.value, [recording.id]: true }
    try {
      const res = await recordingApi.listVersions(context.studyId, recording.id)
      recordingVersionsById.value = {
        ...recordingVersionsById.value,
        [recording.id]: [...res.data.versions].sort((a, b) => b.version_seq - a.version_seq),
      }
    } catch {
      // 版本接口不可用时静默退化：抽屉回退用「当前文件桶」展示一条「已上传」
      recordingVersionsById.value = { ...recordingVersionsById.value, [recording.id]: [] }
    } finally {
      recordingVersionsLoading.value = { ...recordingVersionsLoading.value, [recording.id]: false }
    }
  }

  return {
    selectedAssetRecordings,
    expandedRecordingIds,
    recordingFilesById,
    recordingFilesLoading,
    recordingFilesError,
    recordingVersionsById,
    recordingVersionsLoading,
    isLoadingRecordings,
    recordingsError,
    uploadFormatHint,
    recordingsBySubject,
    recordingBucketsById,
    recordingStats,
    loadSelectedAssetRecordings,
    resetRecordsView,
    isRecordingExpanded,
    toggleRecordingExpanded,
    loadRecordingFiles,
    loadRecordingVersions,
    relabelRecording,
    recordingQaById,
    recordingQaLoading,
    deleteRecording,
    loadRecordingQa,
    runRecordingQa,
    reviewRecordingQa,
  }
}
