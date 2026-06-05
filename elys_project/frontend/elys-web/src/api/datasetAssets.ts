import type {
  AsyncTask,
  DatasetAsset,
  DatasetBootstrapRequest,
  DatasetBootstrapResponse,
  DatasetAssetCreateRequest,
  DatasetAssetListResponse,
  DatasetAssetTaskRequest,
  DatasetAssetUpdateRequest,
  DatasetFileListResponse,
  DatasetFileTreeResponse,
  RecordingListResponse,
  RecordingVersionListResponse,
  StudyDatasetMount,
  StudyDatasetMountCreateRequest,
  StudyDatasetMountListResponse,
  StudyDatasetMountUpdateRequest,
} from '@/types'
import { api, dataApi } from './client'

export interface DatasetAssetListParams {
  status?: string
  visibility?: string
  owner_id?: string
  keyword?: string
}

export interface DatasetFileListParams {
  version_label?: string
  file_role?: string
}

export interface RecordingListParams {
  dataset_asset_id?: string
  mount_id?: string
  mount_name?: string
  subject?: string
  session?: string
  task?: string
  run?: string
  qa_status?: string
}

export const datasetAssetApi = {
  list: (params: DatasetAssetListParams = {}) =>
    api.get<DatasetAssetListResponse>('/dataset-assets', { params }),
  create: (data: DatasetAssetCreateRequest) =>
    api.post<DatasetAsset>('/dataset-assets', data),
  bootstrap: (data: DatasetBootstrapRequest) =>
    api.post<DatasetBootstrapResponse>('/dataset-assets/bootstrap', data),
  update: (assetId: string, data: DatasetAssetUpdateRequest) =>
    api.patch<DatasetAsset>(`/dataset-assets/${assetId}`, data),
  listFiles: (assetId: string, params: DatasetFileListParams = {}) =>
    dataApi.get<DatasetFileListResponse>(`/dataset-assets/${assetId}/files`, { params }),
  // Phase 3 (docs_v2/3-25): 列出某个 asset 的所有版本
  listVersions: (assetId: string) =>
    api.get<{ versions: import('@/types').DatasetVersion[] }>(`/dataset-assets/${assetId}/versions`),
  // Phase 3 (docs_v2/3-25): 已发布过版本的 asset 创建新 draft（v+1）
  createDraftVersion: (assetId: string) =>
    api.post<import('@/types').DatasetVersion>(`/dataset-assets/${assetId}/versions`),
  getRawBidsTree: (assetId: string, params: Pick<DatasetFileListParams, 'version_label'> = {}) =>
    dataApi.get<DatasetFileTreeResponse>(`/dataset-assets/${assetId}/bids-tree`, { params }),
  buildRawBids: (assetId: string, data: DatasetAssetTaskRequest = {}) =>
    api.post<AsyncTask>(`/dataset-assets/${assetId}/raw-bids-build`, data),
  rebuildCanonicalFif: (assetId: string, data: DatasetAssetTaskRequest = {}) =>
    api.post<AsyncTask>(`/dataset-assets/${assetId}/canonical-fif-rebuild`, data),
}

export const studyDatasetMountApi = {
  list: (studyId: string) =>
    api.get<StudyDatasetMountListResponse>(`/studies/${studyId}/datasets/mounts`),
  create: (studyId: string, data: StudyDatasetMountCreateRequest) =>
    api.post<StudyDatasetMount>(`/studies/${studyId}/datasets/mounts`, data),
  update: (studyId: string, mountId: string, data: StudyDatasetMountUpdateRequest) =>
    api.patch<StudyDatasetMount>(`/studies/${studyId}/datasets/mounts/${mountId}`, data),
  remove: (studyId: string, mountId: string) =>
    api.delete<StudyDatasetMount>(`/studies/${studyId}/datasets/mounts/${mountId}`),
}

export const recordingApi = {
  list: (studyId: string, params: RecordingListParams = {}) =>
    dataApi.get<RecordingListResponse>(`/studies/${studyId}/recordings`, { params }),
  listVersions: (studyId: string, recordingId: string) =>
    dataApi.get<RecordingVersionListResponse>(`/studies/${studyId}/recordings/${recordingId}/versions`),
  listFiles: (studyId: string, recordingId: string) =>
    dataApi.get<DatasetFileListResponse>(`/studies/${studyId}/recordings/${recordingId}/files`),
}

