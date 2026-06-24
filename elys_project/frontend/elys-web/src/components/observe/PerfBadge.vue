<template>
  <div v-if="keys.length" class="perf-badge" title="临时性能探针：各阶段自挂载起的毫秒（测完会移除）">
    <span v-for="k in keys" :key="k" class="perf-badge__item">{{ k }} <strong>{{ perf[k] }}</strong></span>
    <span class="perf-badge__u">ms</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ perf: Record<string, number> }>()
const keys = computed(() => Object.keys(props.perf))
</script>

<style scoped>
.perf-badge {
  position: fixed; bottom: 8px; right: 10px; z-index: 9999;
  display: inline-flex; align-items: center; gap: 9px;
  padding: 3px 10px; font-size: 11px; font-variant-numeric: tabular-nums;
  color: var(--c-text-2); background: var(--c-surface);
  border: 1px solid var(--c-border); border-radius: 999px; box-shadow: 0 1px 5px rgba(0, 0, 0, .1);
  pointer-events: none;
}
.perf-badge__item strong { font-weight: 600; color: var(--c-text); }
.perf-badge__u { opacity: .6; }
</style>
