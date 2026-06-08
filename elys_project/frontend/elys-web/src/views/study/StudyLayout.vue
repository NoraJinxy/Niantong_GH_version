<template>
  <WorkbenchShell active-key="studies" active-top-key="studies" :show-sidebar="false" :narrow="isNarrow">
    <div class="study-layout">
      <header class="study-layout__head">
        <RouterLink class="study-layout__crumb" :to="{ path: '/studies', query: { study: studyId } }">← 研究项列表</RouterLink>
        <div class="study-layout__title">
          <h1>{{ study.currentStudy?.name || (study.loading ? '加载中…' : '研究项') }}</h1>
          <span
            v-if="study.currentStudy"
            class="status-pill"
            :class="statusPillClass(study.currentStudy.status)"
          >
            {{ statusLabel(study.currentStudy.status) }}
          </span>
        </div>
        <p v-if="study.currentStudy" class="study-layout__sub">
          <code>{{ study.currentStudy.code }}</code>
          <span v-if="study.currentStudy.description"> · {{ study.currentStudy.description }}</span>
        </p>
      </header>

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
  { key: 'workflow', label: '工作流·运行', name: 'StudyWorkflow' },
  { key: 'results', label: '结果', name: 'StudyResults' },
] as const

const route = useRoute()
const study = useStudyStore()

const studyId = computed(() => String(route.params.studyId || ''))
const activeTab = computed(() => (route.meta.studyTab as string) || 'workflow')
// 工作流是宽画布、不限版心；其余 tab 限宽（交给 WorkbenchShell 的 .page--narrow）
const isNarrow = computed(() => activeTab.value !== 'workflow')

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

function statusLabel(status: string | null | undefined) {
  const labels: Record<string, string> = {
    active: '活跃',
    archived: '已归档',
    trashed: '回收站',
    deleted: '已删除',
  }
  return status ? labels[status] || status : '未知'
}
function statusPillClass(status: string | null | undefined) {
  if (status === 'active') return 'status-pill--success'
  if (status === 'deleted' || status === 'trashed') return 'status-pill--danger'
  return 'status-pill--muted'
}
</script>

<style scoped>
.study-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--c-text);
}
.study-layout__crumb {
  color: var(--c-text-3);
  font-size: 13px;
  text-decoration: none;
}
.study-layout__crumb:hover {
  color: var(--c-primary);
}
.study-layout__title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}
.study-layout__title h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.25;
  color: var(--c-text);
  overflow-wrap: anywhere;
}
.study-layout__sub {
  margin: 6px 0 0;
  color: var(--c-text-2);
  font-size: 13px;
}
.study-layout__sub code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.study-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  border-bottom: 1px solid var(--c-border);
}
.study-tab {
  padding: 10px 16px;
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
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
}
.status-pill--success {
  background: var(--c-success-soft);
  color: var(--c-success);
}
.status-pill--muted {
  background: var(--c-bg-tint);
  color: var(--c-text-3);
}
.status-pill--danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
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
