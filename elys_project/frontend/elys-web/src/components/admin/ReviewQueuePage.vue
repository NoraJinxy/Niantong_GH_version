<template>
  <WorkbenchShell active-key="admin" active-top-key="admin" :show-sidebar="false">
    <div class="review-page">
      <header class="review-page__header">
        <div>
          <p class="eyebrow">管理员审核</p>
          <h1>{{ pageTitle }}</h1>
          <!-- 顶部富文本说明段：含 <strong>/<code> 等，由各页自管 -->
          <p><slot name="intro" /></p>
        </div>
        <div class="review-page__actions">
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

        <section class="review-strip" :aria-label="`${entityLabel}审核摘要`">
          <article class="strip-stat">
            <span>待审核</span>
            <strong>{{ pendingRequests.length }}</strong>
          </article>
        </section>

        <section class="review-list">
          <div v-if="loading" class="empty-state">正在加载...</div>
          <div v-else-if="!pendingRequests.length" class="empty-state">
            <strong>{{ emptyTitle }}</strong>
            <span>{{ emptyText }}</span>
          </div>

          <article
            v-for="req in pendingRequests"
            :key="req.id"
            class="review-card"
            :class="`review-card--${cardTone}`"
          >
            <header class="review-card__head">
              <div>
                <p class="eyebrow">{{ entityLabel }}</p>
                <h2>{{ entityHeading }}<span class="mono">{{ entityIdOf(req) }}</span></h2>
                <div class="review-meta">
                  <span>申请人 <span class="mono">{{ req.requested_by }}</span></span>
                  <span>·</span>
                  <span>{{ formatDateTime(req.requested_at) }}</span>
                </div>
              </div>
              <div class="review-actions">
                <button class="btn btn--primary" type="button" @click="openReviewModal(req, 'approved')">
                  {{ approveCardButtonText }}
                </button>
                <button class="btn btn--ghost" type="button" @click="openReviewModal(req, 'rejected')">
                  驳回
                </button>
              </div>
            </header>
            <div class="review-reason">
              <span>{{ reasonLabel }}</span>
              <p>{{ reasonOf(req) }}</p>
            </div>
          </article>
        </section>
      </div>
    </div>

    <!-- 审核弹窗 -->
    <ReviewDialog
      :open="reviewModal.open"
      :decision="reviewModal.decision"
      :submitting="reviewModal.submitting"
      :title="dialogCopy.title"
      :approve-eyebrow="dialogCopy.approveEyebrow"
      :reject-eyebrow="dialogCopy.rejectEyebrow"
      :approve-button-text="dialogCopy.approveButtonText"
      :reject-button-text="dialogCopy.rejectButtonText"
      @close="closeReviewModal"
      @submit="submitReview"
    >
      <template #approve-copy>
        <slot name="dialog-approve-copy" :request="reviewModal.request" />
      </template>
      <template #reject-copy>
        <slot name="dialog-reject-copy" :request="reviewModal.request" />
      </template>
    </ReviewDialog>
  </WorkbenchShell>
</template>

<script setup lang="ts">
// 管理员审核队列通用骨架：撤回 / 转公开两页的同构外壳。
// 差异点全部参数化：配色(cardTone)、文案、标识字段取值器、加载/提交注入。
import { computed, onMounted, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ReviewDialog from '@/components/admin/ReviewDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/composables/common/formatters'
import { friendlyError } from '@/composables/common/errors'

// 两页都只读取这些字段的交集；实体标识字段（dataset_version_id / asset_id）
// 通过 entityIdOf 取值器注入，所以这里不进接口。
interface ReviewRecord {
  id: string
  requested_by: string
  requested_at: string
  reason?: string | null
}

interface ReviewPayload {
  decision: 'approved' | 'rejected'
  admin_notes?: string | null
}

interface DialogCopy {
  title: string
  approveEyebrow: string
  rejectEyebrow: string
  approveButtonText: string
  rejectButtonText: string
}

const props = defineProps<{
  // 页面文案
  pageTitle: string
  emptyTitle: string
  emptyText: string
  cardTone: 'warning' | 'primary'
  entityLabel: string
  entityHeading: string
  reasonLabel: string
  approveCardButtonText: string
  // 行为注入
  load: () => Promise<ReviewRecord[]>
  submit: (id: string, payload: ReviewPayload) => Promise<unknown>
  entityIdOf: (req: ReviewRecord) => string
  reasonOf: (req: ReviewRecord) => string
  approveSuccessMsg: string
  rejectSuccessMsg: string
  // 弹窗文案
  dialogCopy: DialogCopy
}>()

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.roles?.includes('admin') ?? false)

const pendingRequests = ref<ReviewRecord[]>([])
const loading = ref(false)
const error = ref('')
const successMessage = ref('')

const reviewModal = ref<{
  open: boolean
  request: ReviewRecord | null
  decision: 'approved' | 'rejected'
  submitting: boolean
}>({
  open: false,
  request: null,
  decision: 'approved',
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
    pendingRequests.value = await props.load()
  } catch (err) {
    error.value = friendlyError(err, '加载待审核申请失败')
  } finally {
    loading.value = false
  }
}

function openReviewModal(req: ReviewRecord, decision: 'approved' | 'rejected') {
  reviewModal.value = {
    open: true,
    request: req,
    decision,
    submitting: false,
  }
}
function closeReviewModal() {
  if (reviewModal.value.submitting) return
  reviewModal.value.open = false
}

async function submitReview(notes: string) {
  const req = reviewModal.value.request
  if (!req) return
  reviewModal.value.submitting = true
  try {
    await props.submit(req.id, {
      decision: reviewModal.value.decision,
      admin_notes: notes || null,
    })
    successMessage.value = reviewModal.value.decision === 'approved'
      ? props.approveSuccessMsg
      : props.rejectSuccessMsg
    reviewModal.value.open = false
    await loadPending()
  } catch (err) {
    error.value = friendlyError(err, '审核提交失败')
  } finally {
    reviewModal.value.submitting = false
  }
}
</script>

<style scoped>
/* WorkbenchShell .page 已有 padding，去掉这里避免双倍 */
.review-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--c-text);
}
.review-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}
.review-page__header h1 {
  margin: 0;
  font-size: 26px;
  color: var(--c-text);
}
.review-page__header p {
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
.review-strip {
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
.review-list {
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
.review-card {
  border-radius: 10px;
  padding: 18px;
}
/* 撤回 = warning 系 */
.review-card--warning {
  border: 1px solid var(--c-warning-soft);
  background: var(--c-warning-soft);
}
.review-card--warning .review-meta,
.review-card--warning .review-reason span {
  color: var(--c-warning);
}
.review-card--warning .review-reason {
  border-top: 1px dashed var(--c-warning-soft);
}
/* 转公开 = primary 系 */
.review-card--primary {
  border: 1px solid var(--c-primary-soft, var(--c-border));
  background: var(--c-primary-soft, #eef4ff);
}
.review-card--primary .review-meta,
.review-card--primary .review-reason span {
  color: var(--c-primary);
}
.review-card--primary .review-reason {
  border-top: 1px dashed var(--c-border);
}
.review-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.review-card__head h2 {
  margin: 4px 0 0;
  font-size: 16px;
  color: var(--c-text);
}
.review-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
}
.review-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.review-reason {
  margin-top: 14px;
  padding-top: 12px;
}
.review-reason span {
  font-size: 12px;
  font-weight: 700;
}
.review-reason p {
  margin: 6px 0 0;
  color: var(--c-text);
  line-height: 1.6;
  white-space: pre-wrap;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
</style>
