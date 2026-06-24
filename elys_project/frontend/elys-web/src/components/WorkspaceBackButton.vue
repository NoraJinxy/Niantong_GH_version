<template>
  <button type="button" class="ws-back" :title="exitTitle" :aria-label="exitTitle" @click="exit">
    <span class="ws-back__arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></span>
    <span class="ws-back__text">{{ backLabel }}</span>
  </button>
</template>

<script setup lang="ts">
// 「返回工作区」按钮 —— 复用 StudyLayout 退出工作区的语义：优先聚焦打开本页的来源标签页并关闭本页；
// 来源已关 / 关页被拒（链接打开的标签页在 SPA 里多不可脚本关闭）/ 直达进来时，兜底在本页跳回。
// 观察页（时域/频域/时频）由工作流/结果用新标签页打开，故同样需要这个「返回」件。
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{
  // 兜底落点（关页失败 / 无来源时）。不传则按 query.studyId 跳该研究项工作流，再退到列表。
  fallback?: string
  label?: string
}>()

const WS_FROM_KEY = 'elys:workspace-from'

const route = useRoute()
const router = useRouter()

const canCloseTab = ref(false)
const originFrom = ref<'dashboard' | 'studies'>('studies')

function usableOpener(): Window | null {
  try {
    const opener = window.opener as Window | null
    if (opener && !opener.closed) return opener
  } catch {
    /* 跨域 opener：读 .closed 即抛，按不可用处理 */
  }
  return null
}

const studyId = computed(() => String(route.query.studyId ?? route.query.study_id ?? ''))

function fallbackPath(): string {
  if (props.fallback) return props.fallback
  if (studyId.value) return `/studies/${studyId.value}/pipeline`
  return sessionStorage.getItem(WS_FROM_KEY) === 'dashboard' ? '/dashboard' : '/studies'
}

const backLabel = computed(
  () => props.label ?? (originFrom.value === 'dashboard' ? '返回工作台' : '返回研究项'),
)
const exitTitle = computed(() =>
  canCloseTab.value ? `${backLabel.value}（关闭此标签页）` : backLabel.value,
)

function exit() {
  const opener = usableOpener()
  if (opener) {
    try {
      opener.focus()
    } catch {
      /* 聚焦失败不致命，继续关页 */
    }
    window.close()
    window.setTimeout(() => {
      void router.push(fallbackPath())
    }, 150)
    return
  }
  void router.push(fallbackPath())
}

onMounted(() => {
  originFrom.value = sessionStorage.getItem(WS_FROM_KEY) === 'dashboard' ? 'dashboard' : 'studies'
  canCloseTab.value = Boolean(usableOpener())
})
</script>

<style scoped>
.ws-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  border: 1px solid transparent;
  background: transparent;
  padding: 5px 10px 5px 6px;
  border-radius: 9px;
  cursor: pointer;
  color: var(--c-text-2);
  transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast);
}
.ws-back:hover {
  background: var(--c-primary-soft, rgba(37, 99, 235, 0.08));
  border-color: var(--c-border);
  color: var(--c-primary);
}
.ws-back__arrow {
  display: inline-flex;
  width: 16px;
  height: 16px;
  transition: transform var(--t-fast);
}
.ws-back__arrow svg {
  width: 100%;
  height: 100%;
}
.ws-back:hover .ws-back__arrow {
  transform: translateX(-2px);
}
.ws-back__text {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
</style>
