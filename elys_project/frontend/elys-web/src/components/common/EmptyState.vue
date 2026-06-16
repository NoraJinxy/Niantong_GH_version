<!-- 全站统一的空状态：图标 + 标题 + 说明 + 动作插槽，替代各页各写的 empty / study-empty / dataset-list-empty / inline-empty。
     自带 scoped 样式（只读全局 CSS 变量）。compact 给抽屉/小区域用；quiet 给「正常的空」（灰底、不强调）。 -->
<template>
  <div class="empty-state" :class="{ 'empty-state--compact': compact, 'empty-state--quiet': quiet }">
    <div v-if="icon" class="empty-state__icon"><AppIcon :name="icon" :size="iconSize" /></div>
    <strong v-if="title" class="empty-state__title">{{ title }}</strong>
    <p v-if="description" class="empty-state__desc">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__action"><slot /></div>
  </div>
</template>

<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'

withDefaults(
  defineProps<{
    icon?: string
    title?: string
    description?: string
    compact?: boolean
    quiet?: boolean
    iconSize?: number
  }>(),
  { icon: '', title: '', description: '', compact: false, quiet: false, iconSize: 26 },
)
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 200px;
  padding: var(--s-6, 32px) var(--s-5, 24px);
  text-align: center;
  color: var(--c-text-3);
}
.empty-state--compact {
  min-height: 140px;
  padding: var(--s-5, 24px) var(--s-4, 16px);
}
.empty-state--quiet {
  background: var(--c-bg-soft);
  border-radius: var(--r, 8px);
}
.empty-state__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 2px;
  color: var(--c-text-2);
  background: var(--c-bg-tint);
  border-radius: var(--r-pill, 999px);
}
.empty-state__title {
  color: var(--c-text);
  font-size: 15px;
  font-weight: 800;
}
.empty-state__desc {
  max-width: 320px;
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.6;
}
.empty-state__action {
  margin-top: var(--s-1, 4px);
}
</style>
