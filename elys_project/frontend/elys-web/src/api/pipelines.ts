import type {
  AsyncTask,
  StudyOutput,
  StudyOutputBatchUpdatePayload,
  StudyOutputCleanupRequest,
  StudyOutputListQuery,
  StudyOutputListResponse,
  StudyOutputPreview,
  StudyOutputPsd,
  StudyOutputPsdQuery,
  StudyOutputTfr,
  StudyOutputTfrQuery,
  StudyOutputTimeseries,
  StudyOutputTimeseriesQuery,
  StudyOutputUpdatePayload,
  LoadDataResolveRequest,
  LoadDataResolveResponse,
  NodeSpecListResponse,
  Pipeline,
  PipelineCreateRequest,
  PipelineInteraction,
  PipelineInteractionDecisionRequest,
  PipelineListResponse,
  PipelineJobListResponse,
  PipelineResumeResponse,
  PipelineExecution,
  PipelineExecutionCreateRequest,
  PipelineExecutionDetail,
  PipelineExecutionLineage,
  PipelineExecutionListResponse,
  PipelineExecutionRetryRequest,
  PipelineEditLock,
  PipelineUpdateRequest,
  PipelineValidationResponse,
  TaskEventListResponse,
} from '@/types'
import { api, dataApi, API_BASE_URL } from './client'

function appendListParam(params: URLSearchParams, key: string, values?: string[] | null) {
  if (!values || !values.length) return
  for (const value of values) {
    if (value === null || value === undefined || value === '') continue
    params.append(key, String(value))
  }
}

export const pipelineApi = {
  listNodeSpecs: () => api.get<NodeSpecListResponse>('/pipeline/nodes'),
  list: (studyId: string) => api.get<PipelineListResponse>(`/studies/${studyId}/pipelines`),
  create: (studyId: string, data: PipelineCreateRequest) =>
    api.post<Pipeline>(`/studies/${studyId}/pipelines`, data),
  get: (studyId: string, pipelineId: string | number) =>
    api.get<Pipeline>(`/studies/${studyId}/pipelines/${pipelineId}`),
  update: (studyId: string, pipelineId: string | number, data: PipelineUpdateRequest) =>
    api.put<Pipeline>(`/studies/${studyId}/pipelines/${pipelineId}`, data),
  remove: (studyId: string, pipelineId: string | number) =>
    api.delete<void>(`/studies/${studyId}/pipelines/${pipelineId}`),
  validate: (studyId: string, pipelineId: string | number) =>
    api.post<PipelineValidationResponse>(`/studies/${studyId}/pipelines/${pipelineId}/validate`),
  run: (studyId: string, pipelineId: string | number, data: PipelineExecutionCreateRequest) => {
    const payload: PipelineExecutionCreateRequest = { trigger: 'manual', ...data }
    // 触发运行时后端要：校验定义 → 解析 LoadData selection → 入队 Celery 任务。
    // 校验阶段会真访问 DB（resolve_load_data_selection），数据多时可能 10-20s。给宽裕的 120s。
    return api.post<PipelineExecution>(`/studies/${studyId}/pipelines/${pipelineId}/executions`, payload, {
      timeout: 120000,
    })
  },
  cancelExecution: (studyId: string, executionId: string) =>
    api.post<PipelineExecution>(`/studies/${studyId}/pipeline-executions/${executionId}/cancel`),
  retryExecution: (studyId: string, executionId: string, data: PipelineExecutionRetryRequest = { input_policy: 'reuse_snapshot' }) =>
    api.post<PipelineExecution>(`/studies/${studyId}/pipeline-executions/${executionId}/retry`, data),
  listExecutions: (studyId: string, pipelineId: string | number, limit = 20) =>
    api.get<PipelineExecutionListResponse>(`/studies/${studyId}/pipelines/${pipelineId}/executions`, { params: { limit } }),
  getExecution: (studyId: string, executionId: string) =>
    api.get<PipelineExecutionDetail>(`/studies/${studyId}/pipeline-executions/${executionId}`),
  getExecutionManifest: (studyId: string, executionId: string) =>
    api.get<Record<string, unknown>>(`/studies/${studyId}/pipeline-executions/${executionId}/manifest`),
  getExecutionLineage: (studyId: string, executionId: string) =>
    api.get<PipelineExecutionLineage>(`/studies/${studyId}/pipeline-executions/${executionId}/lineage`),
  listExecutionJobs: (studyId: string, executionId: string) =>
    api.get<PipelineJobListResponse>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs`),

  // === Derived Dataset 接口（替代旧 artifact 系列） ===
  /** 某次运行的结果列表（替代旧 listRunArtifacts） */
  listExecutionStudyOutputs: (studyId: string, executionId: string, includeDeleted = false) =>
    api.get<StudyOutputListResponse>(
      `/studies/${studyId}/pipeline-executions/${executionId}/outputs`,
      { params: { include_deleted: includeDeleted } },
    ),
  /** 跨运行列出研究项的结果（/results 页面用） */
  listStudyOutputs: (studyId: string, query: StudyOutputListQuery = {}) => {
    const params = new URLSearchParams()
    appendListParam(params, 'execution_ids', query.execution_ids)
    appendListParam(params, 'node_types', query.node_types)
    appendListParam(params, 'data_types', query.data_types)
    appendListParam(params, 'bids_subject_ids', query.bids_subject_ids)
    appendListParam(params, 'sessions', query.sessions)
    appendListParam(params, 'tasks', query.tasks)
    appendListParam(params, 'conditions', query.conditions)
    appendListParam(params, 'tags', query.tags)
    if (query.keep !== undefined) params.set('keep', String(query.keep))
    if (query.include_deleted) params.set('include_deleted', 'true')
    if (query.limit !== undefined) params.set('limit', String(query.limit))
    if (query.offset !== undefined) params.set('offset', String(query.offset))
    const qs = params.toString()
    return api.get<StudyOutputListResponse>(
      `/studies/${studyId}/outputs${qs ? `?${qs}` : ''}`,
    )
  },
  getStudyOutput: (studyId: string, datasetId: string) =>
    api.get<StudyOutput>(`/studies/${studyId}/outputs/${datasetId}`),
  /** 改名 / 改标签 / 改 retention */
  updateStudyOutput: (studyId: string, datasetId: string, payload: StudyOutputUpdatePayload) =>
    api.patch<StudyOutput>(`/studies/${studyId}/outputs/${datasetId}`, payload),
  /** 批量改：多选 ids + 一组改动 */
  batchUpdateStudyOutputs: (studyId: string, payload: StudyOutputBatchUpdatePayload) =>
    api.post<StudyOutputListResponse>(`/studies/${studyId}/outputs/batch-update`, payload),
  cleanupStudyOutputs: (studyId: string, data: StudyOutputCleanupRequest = {}) =>
    api.post<AsyncTask>(`/studies/${studyId}/outputs/cleanup`, data),
  previewStudyOutput: (studyId: string, datasetId: string, maxChannels?: number) =>
    api.get<StudyOutputPreview>(
      `/studies/${studyId}/outputs/${datasetId}/preview`,
      maxChannels ? { params: { max_channels: maxChannels } } : undefined,
    ),
  getStudyOutputTimeseries: (
    studyId: string,
    datasetId: string,
    query: StudyOutputTimeseriesQuery = {},
  ) =>
    api.get<StudyOutputTimeseries>(`/studies/${studyId}/outputs/${datasetId}/timeseries`, {
      params: {
        tmin: query.tmin,
        tmax: query.tmax,
        index: query.index,
        max_points: query.maxPoints,
        max_channels: query.maxChannels,
      },
    }),
  /** 时频热图：单通道 freq×time 功率矩阵（TfrPage 用） */
  getStudyOutputTfr: (
    studyId: string,
    datasetId: string,
    query: StudyOutputTfrQuery = {},
  ) =>
    api.get<StudyOutputTfr>(`/studies/${studyId}/outputs/${datasetId}/tfr`, {
      params: {
        channel: query.channel,
        max_freqs: query.maxFreqs,
        max_times: query.maxTimes,
      },
    }),
  /** 功率谱：单通道 频率→功率(dB) 折线（PsdPage 用） */
  getStudyOutputPsd: (
    studyId: string,
    datasetId: string,
    query: StudyOutputPsdQuery = {},
  ) =>
    api.get<StudyOutputPsd>(`/studies/${studyId}/outputs/${datasetId}/psd`, {
      params: {
        channel: query.channel,
        max_freqs: query.maxFreqs,
      },
    }),
  downloadStudyOutput: (studyId: string, datasetId: string) =>
    dataApi.get<Blob>(`/studies/${studyId}/outputs/${datasetId}/download`, { responseType: 'blob' }),

  getNodeInteraction: (studyId: string, executionId: string, jobId: string) =>
    api.get<PipelineInteraction>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/interaction`),
  submitNodeDecision: (studyId: string, executionId: string, jobId: string, data: PipelineInteractionDecisionRequest) =>
    api.post<PipelineInteraction>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/decision`, data),
  resumeNode: (studyId: string, executionId: string, jobId: string) =>
    api.post<PipelineResumeResponse>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/resume`),
  resolveLoadData: (studyId: string, data: LoadDataResolveRequest) =>
    api.post<LoadDataResolveResponse>(`/studies/${studyId}/pipeline/load-data/resolve`, data),
  getTask: (studyId: string, taskId: string) =>
    api.get<AsyncTask>(`/studies/${studyId}/tasks/${taskId}`),
  listTaskEvents: (studyId: string, taskId: string, since?: string) =>
    api.get<TaskEventListResponse>(`/studies/${studyId}/tasks/${taskId}/events`, { params: since ? { since } : {} }),
  taskEventsStreamUrl: (studyId: string, taskId: string, since?: string) => {
    const params = new URLSearchParams()
    if (since) params.set('since', since)
    const query = params.toString()
    return `${API_BASE_URL}/studies/${studyId}/tasks/${taskId}/events/stream${query ? `?${query}` : ''}`
  },
  cancelTask: (studyId: string, taskId: string) =>
    api.post<AsyncTask>(`/studies/${studyId}/tasks/${taskId}/cancel`),
  retryTask: (studyId: string, taskId: string) =>
    api.post<AsyncTask>(`/studies/${studyId}/tasks/${taskId}/retry`),
  acquireEditLock: (studyId: string, pipelineId: string | number) =>
    api.post<PipelineEditLock>(`/studies/${studyId}/pipelines/${pipelineId}/edit-lock`),
  refreshEditLock: (studyId: string, pipelineId: string | number) =>
    api.post<PipelineEditLock>(`/studies/${studyId}/pipelines/${pipelineId}/edit-lock/refresh`),
  releaseEditLock: (studyId: string, pipelineId: string | number) =>
    api.delete<void>(`/studies/${studyId}/pipelines/${pipelineId}/edit-lock`),
}
