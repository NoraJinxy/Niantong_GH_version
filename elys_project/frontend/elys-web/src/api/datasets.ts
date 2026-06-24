import type {
  DatasetQaMockRunResponse,
  DatasetQaResponse,
  DatasetQaReviewRequest,
  DatasetQaReviewResponse,
  RecordingListResponse,
  RecordingUploadResponse,
} from '@/types'
import { dataApi } from './client'

export interface UploadDatasetPayload {
  subject: string
  task: string
  session?: string
  run?: string
  files: File[]
  replaceExisting?: boolean
  datasetAssetId?: string
  mountName?: string
}

export interface UploadDatasetOptions {
  onProgress?: (percent: number, loaded: number, total: number) => void
  onUploadComplete?: () => void
}

function getUploadFileName(file: File) {
  const withRelativePath = file as File & { elysRelativePath?: string; webkitRelativePath?: string }
  return withRelativePath.elysRelativePath || withRelativePath.webkitRelativePath || file.name
}

export const datasetApi = {
  list: (studyId: string) =>
    dataApi.get<RecordingListResponse>(`/studies/${studyId}/recordings`),

  getQa: (studyId: string, recordingId: string) =>
    dataApi.get<DatasetQaResponse>(`/studies/${studyId}/recordings/${recordingId}/qa`),

  runMockQa: (studyId: string, recordingId: string) =>
    dataApi.post<DatasetQaMockRunResponse>(`/studies/${studyId}/recordings/${recordingId}/qa/mock-run`),

  reviewQa: (studyId: string, recordingId: string, payload: DatasetQaReviewRequest) =>
    dataApi.post<DatasetQaReviewResponse>(`/studies/${studyId}/recordings/${recordingId}/qa/review`, payload),

  upload: (studyId: string, payload: UploadDatasetPayload, options: UploadDatasetOptions = {}) => {
    const formData = new FormData()
    let uploadCompleteNotified = false
    formData.append('subject', payload.subject)
    formData.append('task', payload.task)
    if (payload.session) formData.append('session', payload.session)
    if (payload.run) formData.append('run', payload.run)
    if (payload.replaceExisting) formData.append('replace_existing', 'true')
    if (payload.datasetAssetId) formData.append('dataset_asset_id', payload.datasetAssetId)
    if (payload.mountName) formData.append('mount_name', payload.mountName)
    payload.files.forEach((file) => formData.append('files', file, getUploadFileName(file)))

    return dataApi.post<RecordingUploadResponse>(
      `/studies/${studyId}/recordings/import`,
      formData,
      {
        timeout: 30 * 60 * 1000,
        onUploadProgress: (event) => {
          const fallbackTotal = payload.files.reduce((sum, file) => sum + file.size, 0)
          const total = event.total || fallbackTotal
          if (!total) return
          const percent = Math.min(100, Math.round((event.loaded / total) * 100))
          options.onProgress?.(percent, event.loaded, total)
          if (event.loaded >= total && !uploadCompleteNotified) {
            uploadCompleteNotified = true
            options.onUploadComplete?.()
          }
        },
      },
    )
  },
}
