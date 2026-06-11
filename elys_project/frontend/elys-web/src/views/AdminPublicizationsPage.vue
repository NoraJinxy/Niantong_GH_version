<template>
  <WorkbenchShell active-key="admin" active-top-key="admin" :show-sidebar="false">
    <div class="publicizations-page">
      <header class="publicizations-page__header">
        <div>
          <p class="eyebrow">管理员审核</p>
          <h1>数据集转公开申请</h1>
          <p>
            处理数据集负责人提交的「转公开」申请（可见范围 <strong>共享 → 公开</strong>，先审后开）。
            通过后数据集对<strong>全平台注册用户</strong>可读，且不可逆；驳回则保持<strong>共享</strong>。
            <br />
            调试期默认 <strong>auto-approve</strong>（owner 申请即自动通过、`decision='auto'`），此处通常没有待审项；
            上线开启人工审核策略后，待审申请会出现在这里。
          </p>
        </div>
        <div class="publicizations-page__actions">
          <button class="btn btn--ghost" type="button" :disabled="loading" @click="loadPending">
            <AppIcon name="refresh" :size="16" />
            刷新
          </button>
        </div>
      </header>

      <div v-if="!isAdmin" class="alert alert--error">
        当前账号没有平台管理员角色，无法访问此页面。
      </div>

      <div v-else>
        <div v-if="error" class="alert alert--error">{{ error }}</div>
        <div v-if="successMessage" class="alert alert--success">{{ successMessage }}</div>

        <section class="publicizations-strip" aria-label="转公开审核摘要">
          <article class="strip-stat">
            <span>待审核</span>
            <strong>{{ pendingRequests.length }}</strong>
          </article>
        </section>

        <section class="publicizations-list">
          <div v-if="loading" class="empty-state">正在加载...</div>
          <div v-else-if="!pendingRequests.length" class="empty-state">
            <strong>没有待审核的转公开申请</strong>
            <span>新的申请会出现在这里（调试期通常自动通过，不进此队列）。</span>
          </div>

          <article
            v-for="req in pendingRequests"
            :key="req.id"
            class="publicization-card"
          >
            <header class="publicization-card__head">
              <div>
                <p class="eyebrow">转公开申请</p>
                <h2>数据集：<span class="mono">{{ req.asset_id }}</span></h2>
                <div class="publicization-meta">
                  <span>申请人 <span class="mono">{{ req.requested_by }}</span></span>
                  <span>·</span>
                  <span>{{ formatDateTime(req.requested_at) }}</span>
                </div>
              </div>
              <div class="publicization-actions">
                <button class="btn btn--primary" type="button" @click="openReviewModal(req, 'approved')">
                  通过公开
                </button>
                <button class="btn btn--ghost" type="button" @click="openReviewModal(req, 'rejected')">
                  驳回
                </button>
              </div>
            </header>
            <div class="publicization-reason">
              <span>申请理由</span>
              <p>{{ req.reason || '（未填写）' }}</p>
            </div>
          </article>
        </section>
      </div>
    </div>

    <!-- 审核弹窗 -->
    <div v-if="reviewModal.open" class="modal-backdrop" role="presentation" @click.self="closeReviewModal">
      <form class="modal-card review-modal" @submit.prevent="submitReview">
        <header>
          <div>
            <p class="eyebrow">{{ reviewModal.decision === 'approved' ? '审核通过 — 转公开生效（不可逆）' : '驳回转公开 — 保持共享' }}</p>
            <h2>转公开申请审核</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeReviewModal">x</button>
        </header>
        <p class="modal-copy">
          <span v-if="reviewModal.decision === 'approved'">
            通过后数据集可见范围升为<strong>公开</strong>，全平台注册用户可读，且<strong>不可逆</strong>。
            申请理由：<em>{{ reviewModal.request?.reason || '（未填写）' }}</em>
          </span>
          <span v-else>
            驳回后数据集保持<strong>共享</strong>。建议在备注里说明驳回理由（仅审计留痕）。
          </span>
        </p>
        <label>
          <span>管理员备注 (可选)</span>
          <textarea
            v-model.trim="reviewModal.notes"
            rows="4"
            placeholder="审核备注，写入审计日志"
            maxlength="2000"
          />
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeReviewModal">取消</button>
          <button
            class="btn"
            :class="reviewModal.decision === 'approved' ? 'btn--primary' : 'btn--danger'"
            type="submit"
            :disabled="reviewModal.submitting"
          >
            {{ reviewModal.submitting ? '提交中...' : (reviewModal.decision === 'approved' ? '确认通过公开' : '确认驳回') }}
          </button>
        </footer>
      </form>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { datasetPublicizationApi } from '@/api/datasetVersions'
import { useAuthStore } from '@/stores/auth'
import type { DatasetPublicizationRequestRecord } from '@/types'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.roles?.includes('admin') ?? false)

const pendingRequests = ref<DatasetPublicizationRequestRecord[]>([])
const loading = ref(false)
const error = ref('')
const successMessage = ref('')

const reviewModal = ref<{
  open: boolean
  request: DatasetPublicizationRequestRecord | null
  decision: 'approved' | 'rejected'
  notes: string
  submitting: boolean
}>({
  open: false,
  request: null,
  decision: 'approved',
  notes: '',
  submitting: false,
})

onMounted(() => {
  if (isAdmin.value) void loadPending()
})

async function loadPending() {
  if (!isAdmin.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await datasetPublicizationApi.listPending()
    pendingRequests.value = res.data
  } catch (err) {
    error.value = friendlyError(err, '加载待审核申请失败')
  } finally {
    loading.value = false
  }
}

function openReviewModal(req: DatasetPublicizationRequestRecord, decision: 'approved' | 'rejected') {
  reviewModal.value = {
    open: true,
    request: req,
    decision,
    notes: '',
    submitting: false,
  }
}
function closeReviewModal() {
  if (reviewModal.value.submitting) return
  reviewModal.value.open = false
}

async function submitReview() {
  const req = reviewModal.value.request
  if (!req) return
  reviewModal.value.submitting = true
  try {
    await datasetPublicizationApi.review(req.id, {
      decision: reviewModal.value.decision,
      admin_notes: reviewModal.value.notes || null,
    })
    successMessage.value = reviewModal.value.decision === 'approved'
      ? '已通过，数据集可见范围已升为公开'
      : '已驳回转公开申请，数据集保持共享'
    reviewModal.value.open = false
    await loadPending()
  } catch (err) {
    error.value = friendlyError(err, '审核提交失败')
  } finally {
    reviewModal.value.submitting = false
  }
}

function friendlyError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return `${fallback}：${detail}`
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | string
    const msg = typeof first === 'string' ? first : first?.msg
    if (msg) return `${fallback}：${msg}`
  }
  const message = err instanceof Error ? err.message : ''
  return message || fallback
}

function formatDateTime(value?: string | null): string {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
</script>

<style scoped>
/* WorkbenchShell .page 已有 padding，去掉这里避免双倍 */
.publicizations-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--c-text);
}
.publicizations-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.publicizations-page__header h1 {
  margin: 0;
  font-size: 26px;
  color: var(--c-text);
}
.publicizations-page__header p {
  margin: 8px 0 0;
  max-width: 760px;
  color: var(--c-text-2);
  line-height: 1.7;
}
.eyebrow {
  margin: 0 0 6px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0 14px;
  font-weight: 700;
  cursor: pointer;
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.btn--primary {
  background: var(--c-primary);
  color: #fff;
}
.btn--ghost {
  border-color: var(--c-border);
  background: #fff;
  color: var(--c-text-2);
}
.btn--danger {
  background: var(--c-danger);
  color: #fff;
}
.alert {
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
}
.alert--error {
  border: 1px solid var(--c-danger-soft);
  background: var(--c-danger-soft);
  color: var(--c-danger);
}
.alert--success {
  border: 1px solid var(--c-success-soft);
  background: var(--c-success-soft);
  color: var(--c-success);
}
.publicizations-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.strip-stat {
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}
.strip-stat span {
  display: block;
  color: var(--c-text-3);
  font-size: 13px;
}
.strip-stat strong {
  display: block;
  margin-top: 8px;
  color: var(--c-text);
  font-size: 28px;
}
.publicizations-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 1px dashed var(--c-border-2);
  border-radius: 8px;
  background: #fff;
  padding: 36px;
  color: var(--c-text-3);
}
.empty-state strong {
  color: var(--c-text);
}
.publicization-card {
  border: 1px solid var(--c-primary-soft, var(--c-border));
  border-radius: 10px;
  background: var(--c-primary-soft, #eef4ff);
  padding: 18px;
}
.publicization-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.publicization-card__head h2 {
  margin: 4px 0 0;
  font-size: 16px;
  color: var(--c-text);
}
.publicization-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  color: var(--c-primary);
  font-size: 12px;
}
.publicization-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.publicization-reason {
  margin-top: 14px;
  border-top: 1px dashed var(--c-border);
  padding-top: 12px;
}
.publicization-reason span {
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
}
.publicization-reason p {
  margin: 6px 0 0;
  color: var(--c-text);
  line-height: 1.6;
  white-space: pre-wrap;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

/* modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.45);
  padding: 24px;
}
.modal-card {
  width: min(560px, 100%);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.25);
}
.review-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px;
}
.review-modal header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.review-modal h2 {
  margin: 0;
  font-size: 18px;
  color: var(--c-text);
}
.modal-copy {
  margin: 0;
  color: var(--c-text-2);
  line-height: 1.6;
  font-size: 14px;
}
.modal-copy em {
  font-style: normal;
  color: var(--c-text);
  font-weight: 600;
}
.icon-button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: #fff;
  color: var(--c-text-2);
  cursor: pointer;
}
.review-modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--c-text-2);
  font-weight: 700;
}
.review-modal textarea {
  width: 100%;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--c-text);
  font: inherit;
  outline: none;
  resize: vertical;
}
.review-modal footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
