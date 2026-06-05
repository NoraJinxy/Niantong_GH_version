<template>
  <div class="obs-tabs">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.to"
      :to="tab.to"
      class="obs-tab"
      :class="{ 'is-active': tab.key === active, 'is-preview': true }"
      :title="`${tab.label}：静态预览，功能未接入`"
    >
      <span v-html="tab.icon"></span>
      {{ tab.label }}
    </RouterLink>
    <div style="flex: 1"></div>
    <slot name="meta" />
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

defineProps<{ active: string }>()

const tabs = [
  {
    key: 'erp', to: '/observe/erp', label: '时域 ERP',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  },
  {
    key: 'psd', to: '/observe/psd', label: '频域 PSD',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  },
  {
    key: 'tfr', to: '/observe/tfr', label: '时频 TFR',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="1"/></svg>',
  },
  {
    key: 'conn', to: '/observe/connectivity', label: '脑网络',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><circle cx="4" cy="6" r="2"/><circle cx="20" cy="6" r="2"/><circle cx="20" cy="18" r="2"/><circle cx="4" cy="18" r="2"/><line x1="6" y1="6" x2="10" y2="11"/><line x1="18" y1="6" x2="14" y2="11"/><line x1="18" y1="18" x2="14" y2="13"/><line x1="6" y1="18" x2="10" y2="13"/></svg>',
  },
  {
    key: 'micro', to: '/observe/microstate', label: '微状态',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
  },
  {
    key: 'source', to: '/observe/source', label: '溯源分析',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a8 8 0 00-8 8c0 4.4 4 7 4 9h8c0-2 4-4.6 4-9a8 8 0 00-8-8z"/></svg>',
  },
]
</script>
