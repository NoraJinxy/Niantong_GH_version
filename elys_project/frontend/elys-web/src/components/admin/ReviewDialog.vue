<template>
  <div
    v-if="open"
    class="modal-backdrop"
    role="presentation"
    @click.self="emitClose"
  >
    <form class="modal-card review-modal" @submit.prevent="emitSubmit">
      <header>
        <div>
          <p class="eyebrow">{{ decision === 'approved' ? approveEyebrow : rejectEyebrow }}</p>
          <h2>{{ title }}</h2>
        </div>
        <button class="icon-button" type="button" aria-label="关闭" @click="emitClose">x</button>
      </header>
      <p class="modal-copy">
        <!-- 富文本说明：approve/reject 各走具名 slot（含 <strong>/<em> 与动态理由）。
             父层未给 slot 时回落到纯文本 prop。 -->
        <span v-if="decision === 'approved'">
          <slot name="approve-copy">{{ approveCopy }}</slot>
        </span>
        <span v-else>
          <slot name="reject-copy">{{ rejectCopy }}</slot>
        </span>
      </p>
      <label>
        <span>管理员备注 (可选)</span>
        <textarea
          v-model.trim="notes"
          rows="4"
          placeholder="审核备注，写入审计日志"
          maxlength="2000"
        />
      </label>
      <footer>
        <button class="btn btn--ghost" type="button" @click="emitClose">取消</button>
        <button
          class="btn"
          :class="decision === 'approved' ? 'btn--primary' : 'btn--danger'"
          type="submit"
          :disabled="submitting"
        >
          {{ submitting ? '提交中...' : (decision === 'approved' ? approveButtonText : rejectButtonText) }}
        </button>
      </footer>
    </form>
  </div>
</template>

<script setup lang="ts">
// 受控审核弹窗：所有差异（标题、眉标、按钮文案、说明富文本）由父层传入；
// 组件内部不区分撤回 / 转公开，只持有备注 notes 的本地状态。
import { ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    decision: 'approved' | 'rejected'
    submitting: boolean
    title: string
    approveEyebrow: string
    rejectEyebrow: string
    approveButtonText: string
    rejectButtonText?: string
    approveCopy?: string
    rejectCopy?: string
  }>(),
  {
    rejectButtonText: '确认驳回',
    approveCopy: '',
    rejectCopy: '',
  },
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', notes: string): void
}>()

const notes = ref('')

// 弹窗每次打开时清空备注（与原页 openReviewModal 重置 notes 行为一致）。
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) notes.value = ''
  },
)

function emitClose() {
  if (props.submitting) return
  emit('close')
}

function emitSubmit() {
  emit('submit', notes.value)
}
</script>

<style scoped>
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
.eyebrow {
  margin: 0 0 6px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
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
.modal-copy :deep(em) {
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
