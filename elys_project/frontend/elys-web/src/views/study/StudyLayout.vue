<template>
  <!-- 研究项工作区 = 焦点页：去掉全局 banner 与「← 研究项列表」面包屑，收成一行精致顶栏
       （极简 logo 回列表 + 研究项身份 + tab 切换 + 用户）。三 tab 共用本布局；pipeline tab 画布吃满剩余高度。
       传 --header-h:0 / --page-pad:0 让 WorkbenchShell 的 .page 与 --full 高度按「无 banner」重算、顶栏齐视口顶。 -->
  <WorkbenchShell
    active-key="studies"
    active-top-key="studies"
    :show-sidebar="false"
    :show-topbar="false"
    :narrow="false"
    :style="{ '--page-pad-x': '0px', '--page-pad-y': '0px', '--header-h': '0px' }"
  >
    <div class="study-layout" :class="{ 'study-layout--full': activeTab === 'pipeline' }">
      <header class="study-layout__bar">
        <!-- 极简品牌 logo：替代全局 banner 与面包屑，点击回研究项列表 -->
        <RouterLink class="study-brand" to="/studies" title="念析 ELYS · 返回研究项列表">
          <span class="study-brand__logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></span>
        </RouterLink>

        <!-- 研究项身份：名称 + code + 状态药丸 -->
        <div class="study-layout__id">
          <h1>{{ studyName }}</h1>
          <code v-if="study.currentStudy?.code">{{ study.currentStudy.code }}</code>
          <StatusPill
            v-if="study.currentStudy"
            :tone="studyStatusTone(study.currentStudy.status)"
            :label="studyStatusLabel(study.currentStudy.status)"
          />
        </div>

        <div class="study-layout__spacer"></div>

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

        <!-- 用户身份 + 退出（替代被去掉的 banner 右侧） -->
        <div class="study-user" :title="userTitle">
          <span class="study-user__avatar">{{ userInitial }}</span>
          <span class="study-user__name">{{ userName }}</span>
          <button class="study-user__logout" type="button" title="退出登录" @click="auth.logout()">
            <AppIcon name="logout" :size="15" />
          </button>
        </div>
      </header>

      <div v-if="study.error" class="alert alert--error">{{ study.error }}</div>

      <div class="study-layout__body">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['PipelinePage']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </div>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import { useStudyStore } from '@/stores/study'
import { useAuthStore } from '@/stores/auth'
import { studyStatusLabel, studyStatusTone } from '@/composables/studies/studyFormatters'

// 3 个工作区 tab（概览已移到 /studies 列表页右栏）。默认落工作流。
const STUDY_TABS = [
  { key: 'data', label: '数据', name: 'StudyData' },
  { key: 'pipeline', label: '工作流', name: 'StudyPipeline' },
  { key: 'results', label: '结果', name: 'StudyResults' },
] as const

const route = useRoute()
const study = useStudyStore()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const studyId = computed(() => String(route.params.studyId || ''))
const activeTab = computed(() => (route.meta.studyTab as string) || 'pipeline')

const studyName = computed(() => study.currentStudy?.name || (study.loading ? '加载中…' : '研究项'))
const userName = computed(() => user.value?.full_name || user.value?.username || 'PI')
const userInitial = computed(() => (user.value?.full_name || user.value?.username || 'E').slice(0, 1).toUpperCase())
const userTitle = computed(() => {
  const roles = user.value?.roles || []
  return `${userName.value} · ${roles.length ? roles.join(' / ') : 'PI'}`
})

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
  color: var(--c-text);
}
/* 工作流 tab：容器吃满视口（顶栏已齐视口顶，--header-h/--page-pad 被父级清零），
   画布按 flex 填充，修掉 .pipeline-page 硬算高度时的下溢 */
.study-layout--full {
  height: calc(100vh - var(--header-h) - 2 * var(--page-pad-y, var(--s-5)));
  min-height: 0;
  overflow: hidden;
}

/* ===== 焦点顶栏：单行（logo + 身份 + tab + 用户），替代全局 banner ===== */
.study-layout__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
  padding: 7px 16px;
  border-bottom: 1px solid var(--c-border);
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

/* 研究项身份：名称 + code + 状态药丸 */
.study-layout__id {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.study-layout__id h1 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--c-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.study-layout__id code {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-family: var(--ff-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 12px;
  background: var(--c-bg-tint);
  padding: 2px 7px;
  border-radius: 999px;
  white-space: nowrap;
}

.study-layout__spacer {
  flex: 1 1 auto;
  min-width: 8px;
}

/* tab 切换：数据 / 工作流 / 结果（分段控件观感） */
.study-tabs {
  display: inline-flex;
  flex-shrink: 0;
  gap: 4px;
  background: var(--c-bg-tint);
  padding: 3px;
  border-radius: 10px;
}
.study-tab {
  padding: 6px 16px;
  border-radius: 8px;
  color: var(--c-text-2);
  font-weight: 600;
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
  transition: background var(--t-fast), color var(--t-fast);
}
.study-tab:hover {
  color: var(--c-text);
}
.study-tab.is-active {
  color: var(--c-primary);
  background: var(--c-bg);
  box-shadow: 0 1px 2px rgba(27, 41, 64, 0.1);
}

.study-layout__extra {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
/* 非工作流 tab 时挂载点为空，不占位 */
.study-layout__extra:empty {
  display: none;
}

/* 用户 chip + 退出 */
.study-user {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding-left: 4px;
}
.study-user__avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--c-brand-grad);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.study-user__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-2);
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.study-user__logout {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--c-text-3);
  cursor: pointer;
  transition: background var(--t-fast), color var(--t-fast);
}
.study-user__logout:hover {
  background: var(--c-bg-tint);
  color: var(--c-text);
}

/* 内容区：非工作流 tab 给内边距并随窗滚动；工作流 tab 吃满高度、画布自管 */
.study-layout__body {
  padding: 14px 16px 24px;
}
.study-layout--full .study-layout__body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.alert {
  margin: 8px 16px 0;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
}
.alert--error {
  border: 1px solid var(--c-danger-soft);
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

/* 窄屏：先让位用户名与 code，保住身份名称与 tab */
@media (max-width: 900px) {
  .study-user__name {
    display: none;
  }
  .study-layout__id code {
    display: none;
  }
}
</style>
