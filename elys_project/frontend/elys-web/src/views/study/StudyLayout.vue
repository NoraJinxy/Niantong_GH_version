<template>
  <!-- 研究项工作区：仅「工作流(pipeline)」tab 进焦点模式——去全局 banner + 去「← 研究项列表」面包屑，
       收成一行精致顶栏（极简 logo 回列表 + 名称 + tab），画布吃满视口；
       「数据 / 结果」tab 维持原样（全局 banner + 面包屑）。 -->
  <WorkbenchShell
    active-key="studies"
    active-top-key="studies"
    :show-sidebar="false"
    :show-topbar="!isPipeline"
    :narrow="false"
    :style="shellStyle"
  >
    <div class="study-layout" :class="{ 'study-layout--full': isPipeline }">
      <header class="study-layout__bar" :class="{ 'study-layout__bar--focus': isPipeline }">
        <!-- 焦点模式：极简品牌 logo（替代全局 banner 与面包屑，点击回研究项列表） -->
        <RouterLink v-if="isPipeline" class="study-brand" to="/studies" title="念析 ELYS · 返回研究项列表">
          <span class="study-brand__logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></span>
        </RouterLink>

        <div class="study-layout__id">
          <!-- 常规模式（数据 / 结果）保留面包屑 -->
          <RouterLink
            v-if="!isPipeline"
            class="study-layout__crumb"
            :to="{ path: '/studies', query: { study: studyId } }"
          >← 研究项列表</RouterLink>
          <h1>{{ studyName }}</h1>
        </div>

        <!-- 焦点模式用弹性间隔把 tab 推到右侧 -->
        <div v-if="isPipeline" class="study-layout__spacer"></div>

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
const isPipeline = computed(() => activeTab.value === 'pipeline')

const studyName = computed(() => study.currentStudy?.name || (study.loading ? '加载中…' : '研究项'))

// 焦点模式（工作流）清零 banner 高度与页边距让顶栏齐视口顶、画布吃满；其余 tab 用常规页边距。
const shellStyle = computed(() =>
  isPipeline.value
    ? { '--page-pad-x': '0px', '--page-pad-y': '0px', '--header-h': '0px' }
    : { '--page-pad-x': '0px', '--page-pad-y': '8px' },
)

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
  padding-left: 0; /* 焦点模式顶栏/画布齐左边，自管内边距 */
  overflow: hidden;
}
/* 头部一行：左 ← 列表+标题，右 tab bar，省垂直空间 */
.study-layout__bar {
  display: flex;
  align-items: center;
  gap: 10px 18px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--c-border);
}
/* 焦点顶栏（仅工作流）：单行精致条，齐视口顶、加底色与轻边 */
.study-layout__bar--focus {
  gap: 12px;
  flex-wrap: nowrap;
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: saturate(160%) blur(12px);
  -webkit-backdrop-filter: saturate(160%) blur(12px);
  position: sticky;
  top: 0;
  z-index: 20;
}

/* 极简品牌 logo：点击回研究项列表（取代被去掉的面包屑 + banner 导航） */
.study-brand {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  text-decoration: none;
}
.study-brand__logo {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--c-brand-grad);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(27, 41, 64, 0.14);
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}
.study-brand:hover .study-brand__logo {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(27, 41, 64, 0.2);
}
.study-brand__logo svg {
  width: 62%;
  height: 62%;
}

.study-layout__spacer {
  flex: 1 1 auto;
  min-width: 8px;
}

.study-layout__extra {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 6px;
}
/* 焦点模式顶栏垂直居中，无需底部留白 */
.study-layout__bar--focus .study-layout__extra {
  padding-bottom: 0;
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
.study-layout__bar--focus .study-layout__id {
  padding-bottom: 0;
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
  flex-shrink: 0;
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
