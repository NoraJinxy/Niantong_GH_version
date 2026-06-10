import type {
  AsyncTask,
  DatasetAsset,
  DatasetBootstrapRequest,
  DatasetBootstrapResponse,
  DatasetAssetCreateRequest,
  DatasetAssetListResponse,
  DatasetAssetOpenVisibilityRequest,
  DatasetAssetTaskRequest,
  DatasetAssetUpdateRequest,
  DatasetFileListResponse,
  DatasetFileTreeResponse,
  DatasetMember,
  DatasetMemberAddRequest,
  DatasetMemberListResponse,
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
  // 可见范围「开放」：只升不降（private<shared<public），要求资产≥1 已发布版本，仅负责人
  openVisibility: (assetId: string, data: DatasetAssetOpenVisibilityRequest) =>
    api.post<DatasetAsset>(`/dataset-assets/${assetId}/open-visibility`, data),
  // 整体删除资产：仅纯未发布资产可删（无任何已发布/已撤回版本），仅负责人，否则后端 409
  remove: (assetId: string) =>
    api.delete<void>(`/dataset-assets/${assetId}`),
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

// 共享态邀请制授权（dataset_members，按用户授权）；均仅负责人
export const datasetMemberApi = {
  list: (assetId: string) =>
    api.get<DatasetMemberListResponse>(`/dataset-assets/${assetId}/members`),
  // #14：data.user_identifier 可为用户名 / 邮箱 / 用户 UUID，后端统一解析
  add: (assetId: string, data: DatasetMemberAddRequest) =>
    api.post<DatasetMember>(`/dataset-assets/${assetId}/members`, data),
  remove: (assetId: string, userId: string) =>
    api.delete<void>(`/dataset-assets/${assetId}/members/${userId}`),
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

