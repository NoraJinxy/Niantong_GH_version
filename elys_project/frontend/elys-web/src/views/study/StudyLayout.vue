<template>
  <!-- 研究项工作区（数据 / 工作流 / 结果）三 tab 统一焦点模式：
       去全局 banner + 去面包屑，收成一行精致顶栏（极简 logo 回列表 + 名称 + tab）；
       画布满屏（study-layout--full）仅工作流 tab 需要。 -->
  <WorkbenchShell
    active-key="studies"
    active-top-key="studies"
    :show-sidebar="false"
    :show-topbar="false"
    :narrow="false"
    :style="shellStyle"
  >
    <div class="study-layout" :class="{ 'study-layout--full': isPipeline }">
      <header class="study-layout__bar study-layout__bar--focus">
        <!-- 退出工作区：工作区一律由 dashboard/studies 用新标签页打开，故 logo 升级成明显的「退出」件——
             优先聚焦打开它的来源标签页并关闭本页；来源已关 / 直达进来时，兜底在本页跳回来源列表。 -->
        <button
          type="button"
          class="study-brand study-exit"
          :title="exitTitle"
          :aria-label="exitTitle"
          @click="exitWorkspace"
        >
          <span class="study-exit__arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg></span>
          <span class="study-exit__text">{{ backLabel }}</span>
          <span class="study-brand__logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></span>
        </button>

        <div class="study-layout__id">
          <h1>{{ studyName }}</h1>
        </div>

        <!-- 弹性间隔把 tab 推到右侧 -->
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
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { useStudyStore } from '@/stores/study'

// 3 个工作区 tab（概览已移到 /studies 列表页右栏）。默认落工作流。
const STUDY_TABS = [
  { key: 'data', label: '数据', name: 'StudyData' },
  { key: 'pipeline', label: '工作流', name: 'StudyPipeline' },
  { key: 'results', label: '结果', name: 'StudyResults' },
] as const

const route = useRoute()
const router = useRouter()
const study = useStudyStore()

const studyId = computed(() => String(route.params.studyId || ''))
const activeTab = computed(() => (route.meta.studyTab as string) || 'pipeline')
const isPipeline = computed(() => activeTab.value === 'pipeline')

const studyName = computed(() => study.currentStudy?.name || (study.loading ? '加载中…' : '研究项'))

// —— 退出工作区 ——
// 工作区由 dashboard/studies 用新标签页打开（rel="opener" 保住 window.opener）。
// 来源页用 ?from=dashboard|studies 标明身份；进入工作区时存进 sessionStorage（per-tab，跨刷新 / 跨 tab 切换不丢），
// 供来源标签页已关 / 直达进来时的兜底跳转。
const WS_FROM_KEY = 'elys:workspace-from'

// 取「能用的来源标签页」：window.opener 存在、未关闭、且同源可访问。跨域访问 opener 会抛错，吞掉当 null。
function usableOpener(): Window | null {
  try {
    const opener = window.opener as Window | null
    if (opener && !opener.closed) return opener
  } catch {
    /* 跨域 opener：读 .closed 即抛，按不可用处理 */
  }
  return null
}

function fallbackPath(): string {
  return sessionStorage.getItem(WS_FROM_KEY) === 'dashboard' ? '/dashboard' : '/studies'
}

// 浏览器只允许脚本关闭「由脚本/链接打开的标签页」。工作区都满足，故优先聚焦来源页并自关；
// 否则（直达 URL、来源页已关）退化为本页跳回来源列表。
const canCloseTab = ref(false)
const originFrom = ref<'dashboard' | 'studies'>('studies') // 来源页：onMounted 按 ?from 定，默认研究项列表
// 按钮文案直接报目的地：返回工作台 / 返回研究项（都 5 字等宽，切来源不抖动）
const backLabel = computed(() => (originFrom.value === 'dashboard' ? '返回工作台' : '返回研究项'))
// tooltip 报全称 + 是否会关页
const exitTitle = computed(() => {
  const dest = originFrom.value === 'dashboard' ? '工作台' : '研究项列表'
  return canCloseTab.value ? `返回${dest}（关闭此标签页）` : `返回${dest}`
})

function exitWorkspace() {
  const opener = usableOpener()
  if (opener) {
    try {
      opener.focus()
    } catch {
      /* 聚焦失败不致命，继续关页 */
    }
    window.close()
    // 部分浏览器只许关「window.open 打开」的标签页，对链接打开的会拒绝 close。
    // 兜底：若 150ms 后本页还在（close 被拒），就退化为在本页跳回来源列表，绝不卡死。
    window.setTimeout(() => {
      void router.push(fallbackPath())
    }, 150)
    return
  }
  void router.push(fallbackPath())
}

onMounted(() => {
  const from = route.query.from
  if (from === 'dashboard' || from === 'studies') sessionStorage.setItem(WS_FROM_KEY, from)
  else sessionStorage.removeItem(WS_FROM_KEY)
  originFrom.value = sessionStorage.getItem(WS_FROM_KEY) === 'dashboard' ? 'dashboard' : 'studies'
  canCloseTab.value = Boolean(usableOpener())
})

// 三 tab 统一焦点模式：清零全局 banner 高度与页边距，让精致顶栏齐视口顶。
const shellStyle = { '--page-pad-x': '0px', '--page-pad-y': '0px', '--header-h': '0px' }

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

/* 退出工作区按钮：箭头 + 品牌 logo + 「退出」字，幽灵按钮质感、悬停染色，比裸 logo 更像可点的退出件 */
.study-brand {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
  text-decoration: none;
  /* button 复位 */
  border: 1px solid transparent;
  background: transparent;
  padding: 4px 10px 4px 6px;
  border-radius: 10px;
  cursor: pointer;
  color: var(--c-text-2);
  transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast);
}
.study-brand:hover {
  background: var(--c-primary-soft, rgba(37, 99, 235, 0.08));
  border-color: var(--c-border);
  color: var(--c-primary);
}
.study-exit__arrow {
  display: inline-flex;
  width: 16px;
  height: 16px;
  margin-right: -2px;
  transition: transform var(--t-fast);
}
.study-exit__arrow svg {
  width: 100%;
  height: 100%;
}
.study-brand:hover .study-exit__arrow {
  transform: translateX(-2px);
}
.study-exit__text {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
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
