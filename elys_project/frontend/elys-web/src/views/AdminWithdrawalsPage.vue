<template>
  <ReviewQueuePage
    page-title="数据集撤回申请"
    empty-title="没有待审核的撤回申请"
    empty-text="新的申请会出现在这里。"
    card-tone="warning"
    entity-label="撤回申请"
    entity-heading="版本编号："
    reason-label="撤回原因"
    approve-card-button-text="通过撤回"
    approve-success-msg="已通过撤回，版本已变为已撤回状态"
    reject-success-msg="已驳回撤回申请，版本回到已发布状态"
    :load="load"
    :submit="submit"
    :entity-id-of="entityIdOf"
    :reason-of="reasonOf"
    :dialog-copy="dialogCopy"
  >
    <template #intro>
      处理数据集负责人提交的撤回申请。审核通过后版本将变为
      <strong>已撤回</strong>（终态），已有挂载和引用保留但禁止新引用；
      拒绝则版本回到<strong>已发布</strong>状态。审核动作不可撤销。
    </template>

    <template #dialog-approve-copy="{ request }">
      通过后版本进入<strong>已撤回</strong>状态（终态）。
      原始撤回理由：<em>{{ request?.reason }}</em>
    </template>
    <template #dialog-reject-copy>
      驳回后版本回到<strong>已发布</strong>状态，原申请人提交的撤回理由会被清空。
      建议在备注里说明驳回理由（申请人看不到，仅审计留痕）。
    </template>
  </ReviewQueuePage>
</template>

<script setup lang="ts">
// 管理员「数据集撤回」审核页 —— ReviewQueuePage 的薄壳，只配文案 + 接 datasetWithdrawalApi。
import ReviewQueuePage from '@/components/admin/ReviewQueuePage.vue'
import { datasetWithdrawalApi } from '@/api/datasetVersions'
import type { DatasetWithdrawalRequestRecord } from '@/types'

const load = () => datasetWithdrawalApi.listPending().then((r) => r.data)
const submit = (id: string, payload: { decision: 'approved' | 'rejected'; admin_notes?: string | null }) =>
  datasetWithdrawalApi.review(id, payload)
const entityIdOf = (req: DatasetWithdrawalRequestRecord) => req.dataset_version_id
const reasonOf = (req: DatasetWithdrawalRequestRecord) => req.reason

const dialogCopy = {
  title: '撤回申请审核',
  approveEyebrow: '审核通过 — 撤回生效',
  rejectEyebrow: '驳回撤回 — 版本恢复为已发布',
  approveButtonText: '确认通过',
  rejectButtonText: '确认驳回',
}
</script>
