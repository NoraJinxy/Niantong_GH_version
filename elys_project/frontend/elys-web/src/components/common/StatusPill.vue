<!-- 全站统一的状态药丸：一处定义配色，替代 Dashboard/Studies/Overview 各自重写的 status-pill / state-badge / stage-pill。
     tone 词表见 composables/common/statusTone.ts；标签可走 label 属性或默认插槽。自带 scoped 样式，只读全局 CSS 变量，不动 style.css。 -->
<template>
  <span class="status-pill" :class="`status-pill--${tone}`"><slot>{{ label }}</slot></span>
</template>

<script setup lang="ts">
import type { StatusTone } from '@/composables/common/statusTone'

withDefaults(defineProps<{ tone?: StatusTone; label?: string }>(), {
  tone: 'muted',
  label: '',
})
</script>

<style scoped>
/* 指标对齐全局 .status-pill（高 22px）：自给自足、不依赖全局样式渗入，同时与 PipelinePage 等处既有药丸一致。 */
.status-pill {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 10px;
  border-radius: var(--r-pill, 999px);
  background: var(--c-bg-tint);
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.status-pill--success { background: var(--c-success-soft); color: var(--c-success); }
.status-pill--warn { background: var(--c-warning-soft); color: var(--c-warning); }
.status-pill--danger { background: var(--c-danger-soft); color: var(--c-danger); }
.status-pill--info { background: var(--c-primary-soft); color: var(--c-primary); }
.status-pill--muted { background: var(--c-bg-tint); color: var(--c-text-3); }
</style>
