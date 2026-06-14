<template>
  <div class="obs-tabs">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.key"
      :to="tabTo(tab.path)"
      class="obs-tab"
      :class="{ 'is-active': tab.key === active, 'is-preview': tab.preview }"
      :title="tab.preview ? `${tab.label}：静态预览，功能未接入` : tab.label"
    >
      <span v-html="tab.icon"></span>
      {{ tab.label }}
    </RouterLink>
    <div style="flex: 1"></div>
    <slot name="meta" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

defineProps<{ active: string }>()

const route = useRoute()
// live 模式下把 studyId/study_output_id 透传到各页签，切页签不丢上下文
const ctxQuery = computed(() => {
  const q: Record<string, string> = {}
  const sid = route.query.studyId ?? route.query.study_id
  const oid = route.query.study_output_id
  if (typeof sid === 'string' && sid) q.studyId = sid
  if (typeof oid === 'string' && oid) q.study_output_id = oid
  return q
})
function tabTo(path: string) {
  return { path, query: ctxQuery.value }
}

const tabs = [
  {
    key: 'erp', path: '/observe/erp', label: '时域 ERP', preview: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  },
  {
    key: 'psd', path: '/observe/psd', label: '频域 PSD', preview: false,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  },
  {
    key: 'tfr', path: '/observe/tfr', label: '时频 TFR', preview: false,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="1"/></svg>',
  },
  {
    key: 'conn', path: '/observe/connectivity', label: '脑网络', preview: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><circle cx="4" cy="6" r="2"/><circle cx="20" cy="6" r="2"/><circle cx="20" cy="18" r="2"/><circle cx="4" cy="18" r="2"/><line x1="6" y1="6" x2="10" y2="11"/><line x1="18" y1="6" x2="14" y2="11"/><line x1="18" y1="18" x2="14" y2="13"/><line x1="6" y1="18" x2="10" y2="13"/></svg>',
  },
  {
    key: 'micro', path: '/observe/microstate', label: '微状态', preview: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
  },
  {
    key: 'source', path: '/observe/source', label: '溯源分析', preview: true,
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a8 8 0 00-8 8c0 4.4 4 7 4 9h8c0-2 4-4.6 4-9a8 8 0 00-8-8z"/></svg>',
  },
]
</script>
