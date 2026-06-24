<template>
  <div v-if="visible" class="cdo">
    <div class="cdo-title">绘图缓存 <span class="cdo-dim">debug</span></div>
    <div class="cdo-row"><span>内存命中</span><b>{{ s.memory }}</b></div>
    <div class="cdo-row"><span>IndexedDB</span><b>{{ s.indexeddb }}</b></div>
    <div class="cdo-row"><span>网络</span><b>{{ s.network }}</b></div>
    <div class="cdo-row"><span>命中率</span><b>{{ hitRate }}%</b></div>
    <div class="cdo-row"><span>内存条目</span><b>{{ s.entries }}</b></div>
    <div class="cdo-row"><span>二进制累计</span><b>{{ kb }} KB</b></div>
    <div class="cdo-last" :class="'src-' + s.lastSource">最近：{{ srcLabel }}</div>
  </div>
</template>

<script setup lang="ts">
// 缓存调试浮层：仅开发模式或 URL 带 ?debug 时显示，发布默认隐藏（决策 e / 06 §6）。
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { cacheStats } from '@/composables/observe/plotCache'

const route = useRoute()
const s = cacheStats

const visible = computed(() => Boolean((import.meta as { env?: { DEV?: boolean } }).env?.DEV) || route.query.debug != null)
const hitRate = computed(() => {
  const tot = s.memory + s.indexeddb + s.network
  return tot ? Math.round(((s.memory + s.indexeddb) / tot) * 100) : 0
})
const kb = computed(() => Math.round(s.bytes / 1024))
const srcLabel = computed(
  () => ({ memory: '内存', indexeddb: 'IndexedDB', network: '网络', '': '—' } as Record<string, string>)[s.lastSource] || '—',
)
</script>

<style scoped>
.cdo {
  position: fixed;
  right: 10px;
  bottom: 10px;
  z-index: 50;
  width: 150px;
  padding: 8px 10px;
  border-radius: var(--r-sm, 6px);
  background: rgba(20, 32, 52, 0.86);
  color: #e8edf5;
  font-family: var(--ff-mono, monospace);
  font-size: 10.5px;
  line-height: 1.7;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
  pointer-events: none;
}
.cdo-title { font-weight: 700; margin-bottom: 3px; }
.cdo-dim { opacity: 0.55; font-weight: 400; }
.cdo-row { display: flex; justify-content: space-between; }
.cdo-row b { font-weight: 700; }
.cdo-last { margin-top: 3px; padding-top: 3px; border-top: 1px solid rgba(255, 255, 255, 0.15); }
.src-memory { color: #6ee7b7; }
.src-indexeddb { color: #7dd3fc; }
.src-network { color: #fbbf24; }
</style>
