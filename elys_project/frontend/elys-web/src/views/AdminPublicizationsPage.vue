<template>
  <ReviewQueuePage
    page-title="数据集转公开申请"
    empty-title="没有待审核的转公开申请"
    empty-text="新的申请会出现在这里（调试期通常自动通过，不进此队列）。"
    card-tone="primary"
    entity-label="转公开申请"
    entity-heading="数据集："
    reason-label="申请理由"
    approve-card-button-text="通过公开"
    approve-success-msg="已通过，数据集可见范围已升为公开"
    reject-success-msg="已驳回转公开申请，数据集保持共享"
    :load="load"
    :submit="submit"
    :entity-id-of="entityIdOf"
    :reason-of="reasonOf"
    :dialog-copy="dialogCopy"
  >
    <template #intro>
      处理数据集负责人提交的「转公开」申请（可见范围 <strong>共享 → 公开</strong>，先审后开）。
      通过后数据集对<strong>全平台注册用户</strong>可读，且不可逆；驳回则保持<strong>共享</strong>。
      <br />
      调试期默认 <strong>auto-approve</strong>（owner 申请即自动通过、`decision='auto'`），此处通常没有待审项；
      上线开启人工审核策略后，待审申请会出现在这里。
    </template>

    <template #dialog-approve-copy="{ request }">
      通过后数据集可见范围升为<strong>公开</strong>，全平台注册用户可读，且<strong>不可逆</strong>。
      申请理由：<em>{{ request?.reason || '（未填写）' }}</em>
    </template>
    <template #dialog-reject-copy>
      驳回后数据集保持<strong>共享</strong>。建议在备注里说明驳回理由（仅审计留痕）。
    </template>
  </ReviewQueuePage>
</template>

<script setup lang="ts">
// 管理员「数据集转公开」审核页 —— ReviewQueuePage 的薄壳，只配文案 + 接 datasetPublicizationApi。
import ReviewQueuePage from '@/components/admin/ReviewQueuePage.vue'
import { datasetPublicizationApi } from '@/api/datasetVersions'
import type { DatasetPublicizationRequestRecord } from '@/types'

const load = () => datasetPublicizationApi.listPending().then((r) => r.data)
const submit = (id: string, payload: { decision: 'approved' | 'rejected'; admin_notes?: string | null }) =>
  datasetPublicizationApi.review(id, payload)
const entityIdOf = (req: DatasetPublicizationRequestRecord) => req.asset_id
const reasonOf = (req: DatasetPublicizationRequestRecord) => req.reason || '（未填写）'

const dialogCopy = {
  title: '转公开申请审核',
  approveEyebrow: '审核通过 — 转公开生效（不可逆）',
  rejectEyebrow: '驳回转公开 — 保持共享',
  approveButtonText: '确认通过公开',
  rejectButtonText: '确认驳回',
}
</script>
