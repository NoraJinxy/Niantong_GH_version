<!-- 通用页头：标题 + 副标题 + 右侧操作区插槽。Studies / Datasets 页头同构，抽此一处统一。
     复用全局 .page__header/.page__title/.page__subtitle 的排版；自带操作区布局与窄屏折叠(760px，与两页原断点一致)。
     flush=true 给「父容器已用 flex gap 控间距」的页(如 Studies)清掉底部外边距。Dashboard 的问候式页头特殊，不接入。 -->
<template>
  <div class="page__header page-header" :class="{ 'page-header--flush': flush }">
    <div class="page-header__heading">
      <h1 class="page__title">{{ title }}</h1>
      <p v-if="subtitle" class="page__subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions"><slot name="actions" /></div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title: string; subtitle?: string; flush?: boolean }>(), {
  subtitle: '',
  flush: false,
})
</script>

<style scoped>
/* scoped 选择器带 [data-v] 比全局 .page__header(单类) 优先级高，故这里能稳定覆盖 align/margin */
.page-header {
  align-items: flex-start;
  margin-bottom: var(--s-5);
}
.page-header--flush {
  margin-bottom: 0;
}
.page-header__heading {
  min-width: 0;
}
.page-header__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  flex-shrink: 0;
}
@media (max-width: 760px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
