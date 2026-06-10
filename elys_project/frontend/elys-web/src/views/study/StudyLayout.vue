<template>
  <!-- 三个 tab 一律全屏撑满（不限版心）；pipeline tab 画布额外吃满剩余高度。--page-pad-x=0 与其余 live 页齐边。 -->
  <WorkbenchShell active-key="studies" active-top-key="studies" :show-sidebar="false" :narrow="false" :style="{ '--page-pad-x': '0px', '--page-pad-y': '8px' }">
    <div class="study-layout" :class="{ 'study-layout--full': activeTab === 'pipeline' }">
      <header class="study-layout__bar">
        <div class="study-layout__id">
          <RouterLink class="study-layout__crumb" :to="{ path: '/studies', query: { study: studyId } }">← 研究项列表</RouterLink>
          <h1>{{ study.currentStudy?.name || (study.loading ? '加载中…' : '研究项') }}</h1>
        </div>

        <nav class="study-tabs" role="tablist" aria-label="研究项视图">
          <RouterLink
            v-for="tab in STUDY_TABS"
            :key="tab.key"
            class="study-tab"
            :class="{ 'is-active': activeTab === tab.key }"
            :to="{ name: tab.name, params: { studyId } }"
          >
            {{ tab.label }}
          </RouterLink>
        </nav>

        <!-- 当前 tab 的工具条挂载点：工作流页用 Teleport 把「工作流选择器/新建」吊到这里 -->
        <div class="study-layout__extra"></div>
      </header>

      <div v-if="study.error" class="alert alert--error">{{ study.error }}</div>

      <router-view v-slot="{ Component }">
        <keep-alive :include="['PipelinePage']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { useStudyStore } from '@/stores/study'

// 3 个工作区 tab（概览已移到 /studies 列表页右栏）。默认落工作流。
const STUDY_TABS = [
  { key: 'data', label: '数据', name: 'StudyData' },
  { key: 'pipeline', label: '工作流', name: 'StudyPipeline' },
  { key: 'results', label: '结果', name: 'StudyResults' },
] as const

const route = useRoute()
const study = useStudyStore()

const studyId = computed(() => String(route.params.studyId || ''))
const activeTab = computed(() => (route.meta.studyTab as string) || 'pipeline')

// studyId 事实源 = URL 路径参数。容器负责把它写进 store 并拉详情，子页面只读 route.params。
watch(
  studyId,
  (id) => {
    if (!id) return
    study.setCurrent(id)
    void study.loadStudy(id)
  },
  { immediate: true },
)
</script>

<style scoped>
.study-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 14px;
  color: var(--c-text);
}
/* 工作流 tab：容器吃满视口剩余高度、画布按 flex 填充，
   修掉 .pipeline-page 硬算 100vh-header 没扣容器 bar 导致的下溢 */
.study-layout--full {
  height: calc(100vh - var(--header-h) - 2 * var(--page-pad-y, var(--s-5)));
  min-height: 0;
  gap: 8px;
  overflow: hidden;
}
/* 头部一行：左 ← 列表+标题+状态+code，右 tab bar，省垂直空间 */
.study-layout__bar {
  display: flex;
  align-items: center;
  gap: 10px 18px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--c-border);
}
.study-layout__extra {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 6px;
}
/* 非工作流 tab 时挂载点为空，不占位 */
.study-layout__extra:empty {
  display: none;
}
.study-layout__id {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding-bottom: 5px;
}
.study-layout__crumb {
  color: var(--c-text-3);
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
}
.study-layout__crumb:hover {
  color: var(--c-primary);
}
.study-layout__id h1 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
  color: var(--c-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.study-layout__id code {
  color: var(--c-text-3);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  white-space: nowrap;
}
.study-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}
.study-tab {
  padding: 8px 16px;
  margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  color: var(--c-text-2);
  font-weight: 700;
  font-size: 14px;
  text-decoration: none;
}
.study-tab:hover {
  color: var(--c-primary);
}
.study-tab.is-active {
  color: var(--c-primary);
  border-bottom-color: var(--c-primary);
}
.alert {
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
}
.alert--error {
  border: 1px solid var(--c-danger-soft);
  background: var(--c-danger-soft);
  color: var(--c-danger);
}
</style>
