import type {
  DatasetPublicizationRequestRecord,
  DatasetVersion,
  DatasetVersionPublishRequest,
  DatasetVersionPublishResponse,
  DatasetVersionWithdrawRequest,
  DatasetWithdrawalRequestRecord,
  EmergencyTakedownRequest,
  PublicizationReviewRequest,
  WithdrawalReviewRequest,
} from '@/types'
import { api } from './client'

// Phase 3 (docs_v2/3-25) - 数据集版本生命周期 API
export const datasetVersionApi = {
  publish: (versionId: string, payload: DatasetVersionPublishRequest) =>
    api.post<DatasetVersionPublishResponse>(`/dataset-versions/${versionId}/publish`, payload),

  requestWithdrawal: (versionId: string, payload: DatasetVersionWithdrawRequest) =>
    api.post<DatasetWithdrawalRequestRecord>(
      `/dataset-versions/${versionId}/withdraw-request`,
      payload,
    ),

  emergencyTakedown: (versionId: string, payload: EmergencyTakedownRequest) =>
    api.post<DatasetWithdrawalRequestRecord>(
      `/dataset-versions/${versionId}/emergency-takedown`,
      payload,
    ),

  // 丢弃已发布资产上的 v+1 未发布版本（仅负责人；非纯未发布则后端 409）
  discardDraft: (versionId: string) =>
    api.delete<void>(`/dataset-versions/${versionId}`),
}

export const datasetWithdrawalApi = {
  listPending: () =>
    api.get<DatasetWithdrawalRequestRecord[]>(`/dataset-withdrawals/pending`),

  review: (requestId: string, payload: WithdrawalReviewRequest) =>
    api.post<DatasetWithdrawalRequestRecord>(`/dataset-withdrawals/${requestId}/review`, payload),
}

// 转公开审核（3-25 §4.2，shared → public）：admin 端点。owner 申请走 datasetAssetApi.requestPublicization。
export const datasetPublicizationApi = {
  listPending: () =>
    api.get<DatasetPublicizationRequestRecord[]>(`/dataset-publicizations/pending`),

  review: (requestId: string, payload: PublicizationReviewRequest) =>
    api.post<DatasetPublicizationRequestRecord>(`/dataset-publicizations/${requestId}/review`, payload),
}

// 工具：把后端 DatasetVersion 的状态翻成中文显示标签
export function datasetVersionStateLabel(state: string | undefined | null): string {
  switch (state) {
    case 'unpublished':
      return '未发布'
    case 'published':
      return '已发布'
    case 'withdraw_requested':
      return '撤回审核中'
    case 'withdrawn':
      return '已撤回'
    default:
      return state || '未知'
  }
}

export function datasetVersionStateClass(state: string | undefined | null): string {
  switch (state) {
    case 'unpublished':
      return 'state-unpublished'
    case 'published':
      return 'state-published'
    case 'withdraw_requested':
      return 'state-pending'
    case 'withdrawn':
      return 'state-withdrawn'
    default:
      return 'state-unknown'
  }
}
