// 工作流编辑器 · LoadData 数据源（数据集加载 / 解析预览 / 参数规范化 / 运行覆盖）
//
// 从 PipelinePage.vue 抽出 LoadData 节点的「逻辑层」。手选右栏 UI 在 LoadDataPanel.vue（独立组件），
// 本模块不碰它；PipelinePage 把这里的 studyDatasets / ensureLoadDataParams / loadingDatasets /
// datasetLoadError / onLoadDataParamsUpdate 解构后喂给 <LoadDataPanel>，template 零改。
//
// task #61：LoadData 永远走 explicit（上面板 Include/Exclude 只帮助缩小候选，Selected File 列表
// → dataset_ids 才是真正输入）。ensureLoadDataParams 固定 selection_mode='explicit' 是有意为之、非 bug，
// 否则未勾文件时后端返回挂载范围全集、污染下游 Epoch/ERP 事件下拉。
//
// buildRunSelectionOverridePayload 经 PipelinePage 装配传给 useRunControl（注入 pipelineApi.run 的 selection_override）。

import { computed, reactive, ref, type Ref, type ComputedRef } from 'vue'
import type {
  Recording,
  LoadDataDataInfo,
  LoadDataResolveRequest,
  PipelineGraphNode,
  PipelineDefinitionPayload,
  PipelineExecutionSelectionOverride,
} from '@/types'
import { datasetApi } from '@/api/datasets'
import { pipelineApi } from '@/api/pipelines'
import { LOAD_DATA_NODE_TYPE, NULL_FILTER_VALUE, DEFAULT_LOAD_DATA_QA_STATUS } from './pipelineConstants'

export type DatasetFilterValue = string | null

export interface LoadDataFilter {
  subjects: DatasetFilterValue[] | 'all'
  sessions: DatasetFilterValue[] | 'all'
  tasks: DatasetFilterValue[] | 'all'
  runs: DatasetFilterValue[] | 'all'
  qa_status: string[] | 'all'
  dataset_asset_id?: string | null
  dataset_asset_ids?: string[] | 'all'
  mount_id?: string | null
  mount_name?: string | null
  require_fif: boolean
}

export interface LoadDataParams {
  selection_mode: 'filter' | 'explicit'
  dataset_filter: LoadDataFilter
  dataset_ids: string[]
}

export type LoadDataExecutionOverride = PipelineExecutionSelectionOverride & {
  selection_mode: 'explicit'
  dataset_ids: string[]
  selector_json: Record<string, unknown>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

interface LoadDataOptions {
  definition: Ref<PipelineDefinitionPayload>
  selectedNode: ComputedRef<PipelineGraphNode | null>
  selectedStudyId: ComputedRef<string>
  describeError: (error: unknown, fallback: string) => string
  markDirty: () => void
  updateLiteGraphNode: (node: PipelineGraphNode) => void
}

export function useLoadData(options: LoadDataOptions) {
  const { definition, selectedNode, selectedStudyId, describeError, markDirty, updateLiteGraphNode } = options

  const studyDatasets = ref<Recording[]>([])
  const loadingDatasets = ref(false)
  const datasetLoadError = ref('')
  const loadDataResolveError = ref('')
  const loadDataResolving = ref(false)
  const resolvedLoadDataInfos = ref<LoadDataDataInfo[]>([])
  const loadDataResolveIssues = ref<string[]>([])
  const loadDataInfosByNodeId = reactive<Record<string, LoadDataDataInfo[]>>({})
  const eventLabelsLoading = ref(false)
  const loadDataExecutionOverrides = reactive<Record<string, LoadDataExecutionOverride>>({})
  let loadDataResolveSeq = 0

  const isLoadDataNode = computed(() => selectedNode.value?.type === LOAD_DATA_NODE_TYPE)

  // —— 参数比较辅助 ——
  function sameNullableStringArray(left: Array<string | null>, right: Array<string | null>) {
    if (left.length !== right.length) return false
    return left.every((item, index) => item === right[index])
  }

  function sameStringArray(left: string[], right: string[]) {
    if (left.length !== right.length) return false
    return left.every((item, index) => item === right[index])
  }

  function sameOptionalString(left?: string | null, right?: string | null) {
    return (left || null) === (right || null)
  }

  function sameFilterList(
    left: DatasetFilterValue[] | string[] | 'all',
    right: DatasetFilterValue[] | string[] | 'all',
  ) {
    if (left === 'all' || right === 'all') return left === right
    if (!Array.isArray(left) || !Array.isArray(right)) return false
    return sameNullableStringArray(left, right)
  }

  function sameLoadDataFilter(left: LoadDataFilter, right: LoadDataFilter) {
    return (
      sameFilterList(left.subjects, right.subjects) &&
      sameFilterList(left.sessions, right.sessions) &&
      sameFilterList(left.tasks, right.tasks) &&
      sameFilterList(left.runs, right.runs) &&
      sameFilterList(left.qa_status, right.qa_status) &&
      sameOptionalString(left.dataset_asset_id, right.dataset_asset_id) &&
      sameFilterList(left.dataset_asset_ids || 'all', right.dataset_asset_ids || 'all') &&
      sameOptionalString(left.mount_id, right.mount_id) &&
      sameOptionalString(left.mount_name, right.mount_name) &&
      left.require_fif === right.require_fif
    )
  }

  // —— 参数规范化（task#61 永远 explicit）——
  function normalizeEntityFilter(value: unknown): DatasetFilterValue[] | 'all' {
    if (value === undefined || value === null || value === '' || value === 'all') return 'all'
    const rawItems = Array.isArray(value) ? value : String(value).split(',')
    const items = rawItems
      .map((item) => {
        if (item === null) return null
        const text = String(item).trim()
        if (!text || text === 'all') return undefined
        return text === NULL_FILTER_VALUE ? null : text
      })
      .filter((item): item is DatasetFilterValue => item !== undefined)
    return items.length ? items : 'all'
  }

  function normalizeQaStatusFilter(value: unknown): string[] | 'all' {
    if (value === 'all') return 'all'
    const rawItems = Array.isArray(value) ? value : typeof value === 'string' ? value.split(',') : DEFAULT_LOAD_DATA_QA_STATUS
    const items = rawItems.map((item) => String(item).trim()).filter(Boolean)
    return items.length ? Array.from(new Set(items)) : [...DEFAULT_LOAD_DATA_QA_STATUS]
  }

  function normalizeStringListFilter(value: unknown): string[] | 'all' {
    if (value === undefined || value === null || value === '' || value === 'all') return 'all'
    const rawItems = Array.isArray(value) ? value : String(value).split(',')
    const items = rawItems.map((item) => String(item).trim()).filter(Boolean)
    return items.length ? Array.from(new Set(items)) : 'all'
  }

  function normalizeOptionalString(value: unknown): string | null {
    if (value === undefined || value === null) return null
    const text = String(value).trim()
    return text || null
  }

  function normalizeDatasetIds(value: unknown): string[] {
    if (!Array.isArray(value)) return []
    return Array.from(new Set(value.map((item) => String(item).trim()).filter(Boolean)))
  }

  function normalizeLoadDataFilter(value: Record<string, unknown>): LoadDataFilter {
    const filter: LoadDataFilter = {
      subjects: normalizeEntityFilter(value.subjects),
      sessions: normalizeEntityFilter(value.sessions),
      tasks: normalizeEntityFilter(value.tasks),
      runs: normalizeEntityFilter(value.runs),
      qa_status: normalizeQaStatusFilter(value.qa_status),
      require_fif: value.require_fif !== false,
    }
    const datasetAssetId = normalizeOptionalString(value.dataset_asset_id)
    if (datasetAssetId) filter.dataset_asset_id = datasetAssetId
    const datasetAssetIds = normalizeStringListFilter(value.dataset_asset_ids)
    if (datasetAssetIds !== 'all') filter.dataset_asset_ids = datasetAssetIds
    const mountId = normalizeOptionalString(value.mount_id)
    if (mountId) filter.mount_id = mountId
    const mountName = normalizeOptionalString(value.mount_name)
    if (mountName) filter.mount_name = mountName
    return filter
  }

  function hasCanonicalLoadDataParams(rawParams: Record<string, unknown>, params: LoadDataParams) {
    if (
      'subjects' in rawParams ||
      'sessions' in rawParams ||
      'tasks' in rawParams ||
      'runs' in rawParams ||
      rawParams.selection_mode !== params.selection_mode ||
      !sameStringArray(normalizeDatasetIds(rawParams.dataset_ids), params.dataset_ids)
    ) {
      return false
    }

    if (!isRecord(rawParams.dataset_filter)) return false
    const filter = normalizeLoadDataFilter(rawParams.dataset_filter)
    return sameLoadDataFilter(filter, params.dataset_filter)
  }

  function ensureLoadDataParams(node: PipelineGraphNode): LoadDataParams {
    const rawParams = isRecord(node.params) ? node.params : {}
    const datasetIds = normalizeDatasetIds(rawParams.dataset_ids)
    // LoadData 永远走 explicit 模式（task #61）：上面板的 Include/Exclude 只是"帮助选择"，
    // 真正决定输入数据的是 Selected File 列表 → dataset_ids。
    // 不再回退到 'filter' —— 否则未勾文件时后端会返回所有匹配数据集，导致 Epoch 误显示事件。
    const legacyFilter = {
      subjects: rawParams.subjects,
      sessions: rawParams.sessions,
      tasks: rawParams.tasks,
      runs: rawParams.runs,
    }
    const params: LoadDataParams = {
      selection_mode: 'explicit',
      dataset_filter: normalizeLoadDataFilter(isRecord(rawParams.dataset_filter) ? rawParams.dataset_filter : legacyFilter),
      dataset_ids: datasetIds,
    }

    if (!hasCanonicalLoadDataParams(rawParams, params)) {
      const nextParams: Record<string, unknown> = {
        ...rawParams,
        selection_mode: params.selection_mode,
        dataset_filter: params.dataset_filter,
        dataset_ids: params.dataset_ids,
      }
      delete nextParams.subjects
      delete nextParams.sessions
      delete nextParams.tasks
      delete nextParams.runs
      node.params = nextParams
    }

    return params
  }

  // —— 数据集加载 + 解析预览 ——
  function resetLoadDataResolveState() {
    loadDataResolveSeq += 1
    loadDataResolving.value = false
    loadDataResolveError.value = ''
    resolvedLoadDataInfos.value = []
    loadDataResolveIssues.value = []
  }

  function buildLoadDataResolveRequest(node: PipelineGraphNode): LoadDataResolveRequest {
    const params = ensureLoadDataParams(node)
    return {
      node_id: node.id,
      selection_mode: params.selection_mode,
      dataset_filter: params.dataset_filter as unknown as Record<string, unknown>,
      dataset_ids: params.dataset_ids,
    }
  }

  async function resolveLoadDataPreview() {
    const node = selectedNode.value
    const studyId = selectedStudyId.value
    if (!studyId || !node || node.type !== LOAD_DATA_NODE_TYPE) {
      resetLoadDataResolveState()
      return
    }

    const requestSeq = ++loadDataResolveSeq
    loadDataResolving.value = true
    loadDataResolveError.value = ''
    loadDataResolveIssues.value = []

    // dataset_ids 为空 → 不调后端：LoadData 没有"真正选中"的输入，cache 直接清成空。
    // 这样下游 Epoch / ERP 的 availableEventLabels 不会因为残留 cache 误显示事件。
    const datasetIds = Array.isArray(node.params?.dataset_ids)
      ? (node.params!.dataset_ids as unknown[]).filter(Boolean)
      : []
    if (datasetIds.length === 0) {
      resolvedLoadDataInfos.value = []
      loadDataInfosByNodeId[node.id] = []
      loadDataResolveIssues.value = []
      loadDataResolveError.value = ''
      loadDataResolving.value = false
      return
    }

    try {
      const res = await pipelineApi.resolveLoadData(studyId, buildLoadDataResolveRequest(node))
      if (requestSeq !== loadDataResolveSeq) return
      resolvedLoadDataInfos.value = res.data.data_infos
      loadDataInfosByNodeId[node.id] = res.data.data_infos
      loadDataResolveIssues.value = [...res.data.errors, ...res.data.warnings]
        .map((issue) => issue.message)
        .filter((message, index, list) => Boolean(message) && list.indexOf(message) === index)
      loadDataResolveError.value = res.data.valid ? '' : 'LoadData 解析未通过'
    } catch (error) {
      if (requestSeq !== loadDataResolveSeq) return
      resolvedLoadDataInfos.value = []
      loadDataResolveIssues.value = []
      loadDataResolveError.value = describeError(error, 'LoadData 解析失败')
    } finally {
      if (requestSeq === loadDataResolveSeq) loadDataResolving.value = false
    }
  }

  async function loadDatasets(studyId = selectedStudyId.value) {
    studyDatasets.value = []
    datasetLoadError.value = ''
    if (!studyId) {
      resetLoadDataResolveState()
      return
    }

    loadingDatasets.value = true
    try {
      const res = await datasetApi.list(studyId)
      studyDatasets.value = res.data.recordings
    } catch (error) {
      datasetLoadError.value = describeError(error, '数据集列表加载失败')
    } finally {
      loadingDatasets.value = false
      if (selectedNode.value?.type === LOAD_DATA_NODE_TYPE) void resolveLoadDataPreview()
    }
  }

  async function fetchEventLabelsForAllLoadData() {
    const studyId = selectedStudyId.value
    if (!studyId) return
    const loadDataNodes = definition.value.graph.nodes.filter((node) => node.type === LOAD_DATA_NODE_TYPE)
    if (!loadDataNodes.length) return

    // dataset_ids 为空的 LoadData 节点 → 直接 set cache=[]，不调后端
    // （否则 selection_mode 残留 filter 时，后端会返回 study 全集，污染下游事件下拉）
    for (const node of loadDataNodes) {
      const ids = Array.isArray(node.params?.dataset_ids)
        ? (node.params!.dataset_ids as unknown[]).filter(Boolean)
        : []
      if (ids.length === 0 && !loadDataInfosByNodeId[node.id]) {
        loadDataInfosByNodeId[node.id] = []
      }
    }

    const missingNodes = loadDataNodes.filter((node) => {
      if (loadDataInfosByNodeId[node.id]) return false
      const ids = Array.isArray(node.params?.dataset_ids)
        ? (node.params!.dataset_ids as unknown[]).filter(Boolean)
        : []
      return ids.length > 0
    })
    if (!missingNodes.length) return
    eventLabelsLoading.value = true
    try {
      await Promise.all(
        missingNodes.map(async (node) => {
          try {
            const res = await pipelineApi.resolveLoadData(studyId, buildLoadDataResolveRequest(node))
            loadDataInfosByNodeId[node.id] = res.data.data_infos
          } catch {
            // 静默失败：事件下拉为空，用户仍可手动输入
            loadDataInfosByNodeId[node.id] = []
          }
        }),
      )
    } finally {
      eventLabelsLoading.value = false
    }
  }

  // —— 运行覆盖 ——
  function loadDataFileIdsForOverride(nodeId: string, datasetIds: string[]) {
    if (selectedNode.value?.id !== nodeId) return []
    const ids = new Set(datasetIds)
    const fileIds = resolvedLoadDataInfos.value
      .filter((item) => ids.has(item.dataset_id))
      .flatMap((item) => [item.dataset_file_id, item.canonical_fif_file_id, item.source_file_id])
      .filter((item): item is string => Boolean(item))
    return Array.from(new Set(fileIds))
  }

  function makeLoadDataExecutionOverride(
    node: PipelineGraphNode,
    datasetIds: string[],
    source: 'manual_run_override' | 'legacy_pipeline_explicit',
  ): LoadDataExecutionOverride {
    const params = ensureLoadDataParams(node)
    const normalizedDatasetIds = normalizeDatasetIds(datasetIds)
    const datasetFileIds = loadDataFileIdsForOverride(node.id, normalizedDatasetIds)
    return {
      selection_mode: 'explicit',
      dataset_filter: params.dataset_filter as unknown as Record<string, unknown>,
      dataset_ids: normalizedDatasetIds,
      dataset_file_ids: datasetFileIds,
      selector_json: {
        source,
        node_id: node.id,
        pipeline_selection_mode: params.selection_mode,
        pipeline_dataset_filter: params.dataset_filter,
        resolved_dataset_ids: normalizedDatasetIds,
        dataset_file_ids: datasetFileIds,
      },
    }
  }

  function clearAllLoadDataExecutionOverrides() {
    Object.keys(loadDataExecutionOverrides).forEach((nodeId) => delete loadDataExecutionOverrides[nodeId])
  }

  function buildRunSelectionOverridePayload() {
    const payload: Record<string, PipelineExecutionSelectionOverride> = {}
    for (const node of definition.value.graph.nodes) {
      if (node.type !== LOAD_DATA_NODE_TYPE) continue
      const explicitOverride = loadDataExecutionOverrides[node.id]
      if (explicitOverride?.dataset_ids.length) {
        const source = explicitOverride.selector_json?.source === 'legacy_pipeline_explicit'
          ? 'legacy_pipeline_explicit'
          : 'manual_run_override'
        payload[node.id] = makeLoadDataExecutionOverride(node, explicitOverride.dataset_ids, source)
        continue
      }
      const params = ensureLoadDataParams(node)
      if (params.selection_mode === 'explicit' && params.dataset_ids.length) {
        payload[node.id] = makeLoadDataExecutionOverride(node, params.dataset_ids, 'legacy_pipeline_explicit')
      }
    }
    return payload
  }

  // —— LoadDataPanel 更新入口 ——
  function onLoadDataParamsUpdate(params: LoadDataParams) {
    const node = selectedNode.value
    if (!node || node.type !== LOAD_DATA_NODE_TYPE) return
    node.params = {
      ...node.params,
      selection_mode: params.selection_mode,
      dataset_filter: params.dataset_filter,
      dataset_ids: params.dataset_ids,
    }
    updateLiteGraphNode(node)
    void resolveLoadDataPreview()
    markDirty()
  }

  return {
    studyDatasets,
    loadingDatasets,
    datasetLoadError,
    loadDataResolveError,
    loadDataResolving,
    resolvedLoadDataInfos,
    loadDataResolveIssues,
    loadDataInfosByNodeId,
    eventLabelsLoading,
    loadDataExecutionOverrides,
    isLoadDataNode,
    ensureLoadDataParams,
    loadDatasets,
    resolveLoadDataPreview,
    fetchEventLabelsForAllLoadData,
    clearAllLoadDataExecutionOverrides,
    buildRunSelectionOverridePayload,
    onLoadDataParamsUpdate,
  }
}
