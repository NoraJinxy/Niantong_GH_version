<template>
  <!--
    Phase UI (docs_v2/6-05): 统一的「技术信息」折叠区。
    所有平台内部对象（ID / DOI 字符串 / 文件统计 / 内部枚举）默认隐藏在这里，
    研究员主动展开才看到。
  -->
  <details class="tech-fold" :open="defaultOpen">
    <summary>
      <span class="tech-fold__icon" aria-hidden="true">▾</span>
      <span class="tech-fold__title">{{ title }}</span>
      <span v-if="hint" class="tech-fold__hint">— {{ hint }}</span>
    </summary>
    <div class="tech-fold__body">
      <slot />
    </div>
  </details>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  hint?: string
  defaultOpen?: boolean
}>()
</script>

<style scoped>
.tech-fold {
  margin-top: 20px;
  border-top: 1px dashed #cfd9e8;
  padding-top: 12px;
}
.tech-fold summary {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #8a98ad;
  font-size: 12px;
  user-select: none;
  list-style: none;
  padding: 4px 0;
}
.tech-fold summary::-webkit-details-marker {
  display: none;
}
.tech-fold__icon {
  display: inline-block;
  transition: transform 0.15s;
  font-size: 10px;
  color: #b6c3d6;
}
.tech-fold[open] .tech-fold__icon {
  transform: rotate(180deg);
}
.tech-fold__title {
  font-weight: 700;
  letter-spacing: 0.02em;
}
.tech-fold__hint {
  font-weight: 400;
  color: #b6c3d6;
}
.tech-fold__body {
  margin-top: 10px;
  padding: 12px 0 4px;
}
.tech-fold__body :deep(dl) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin: 0;
}
.tech-fold__body :deep(dl > div) {
  border: 1px solid #eef3fb;
  border-radius: 8px;
  background: #fafbfd;
  padding: 10px 12px;
}
.tech-fold__body :deep(dt) {
  margin: 0;
  color: #8a98ad;
  font-size: 11px;
}
.tech-fold__body :deep(dd) {
  margin: 4px 0 0;
  color: #33445f;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  word-break: break-all;
}
</style>
