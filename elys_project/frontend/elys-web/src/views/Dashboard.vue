<template>
  <!-- 内容与主页 .hero__inner 横向完全对齐：--content-w=1200(版心=主页) + --page-pad-x=0(去掉 .page 左右内边距，内容满 1200、与主页内容齐边)。均只覆盖本页。 -->
  <WorkbenchShell active-key="dashboard" active-top-key="dashboard" :show-sidebar="false" :narrow="true" :style="{ '--content-w': '1200px', '--page-pad-x': '0px' }">
    <div class="page__header dashboard-header">
      <div>
        <h1 class="page__title">{{ greeting }}，{{ user?.full_name || user?.username || 'PI' }}</h1>
        <p class="dashboard-date">{{ todayLabel }}</p>
        <p class="dashboard-status" :class="dashboardStatusTone">
          <span class="dashboard-status__dot"></span>
          {{ dashboardStatusText }}
        </p>
      </div>
      <div class="dashboard-actions">
        <button class="btn btn--icon" type="button" :disabled="loading" title="刷新" aria-label="刷新" @click="loadDashboard">
          <span v-if="loading" class="spinner spinner--dark"></span>
          <AppIcon v-else name="refresh" :size="16" />
        </button>
        <button
          v-if="errorMessage"
          class="btn btn--primary dashboard-primary-action"
          type="button"
          :disabled="loading"
          @click="loadDashboard"
        >
          <span v-if="loading" class="spinner"></span>
          <AppIcon v-else name="refresh" :size="16" />
          重新加载
        </button>
        <RouterLink v-else class="btn btn--primary dashboard-primary-action" to="/studies">
          <AppIcon name="plus" :size="16" />
          开始新分析
        </RouterLink>
      </div>
    </div>

    <div v-if="errorMessage" class="alert alert--danger dashboard-alert mb-4">
      <AppIcon name="admin" :size="18" />
      <div class="alert__body">{{ errorMessage }}</div>
      <button class="btn btn--sm" type="button" :disabled="loading" @click="loadDashboard">刷新</button>
    </div>

    <div v-if="warningMessage" class="alert alert--warning dashboard-alert mb-4">
      <AppIcon name="clock" :size="18" />
      <div class="alert__body">{{ warningMessage }}</div>
      <button class="btn btn--sm" type="button" :disabled="loading" @click="loadDashboard">刷新</button>
    </div>

    <!-- UI Phase (docs_v2/6-05) P1-1: 需要处理 警示横幅 -->
    <div v-if="!errorMessage && attentionBanner" class="attention-banner" :class="`attention-banner--${attentionBanner.tone}`">
      <div class="attention-banner__icon"><IconLine :name="attentionBanner.icon" :size="28" /></div>
      <div class="attention-banner__body">
        <strong>{{ attentionBanner.title }}</strong>
        <span>{{ attentionBanner.description }}</span>
      </div>
      <div class="attention-banner__actions">
        <RouterLink
          v-for="action in attentionBanner.actions"
          :key="action.label"
          class="attention-banner__action"
          :to="action.to"
        >{{ action.label }}</RouterLink>
      </div>
    </div>

    <template v-if="!errorMessage">
      <section class="page-stat-strip mb-4" aria-label="核心对象摘要">
        <RouterLink class="page-stat" to="/datasets">
          <span class="page-stat__label">数据集</span>
          <strong class="page-stat__value">{{ datasetAssetStat }}<small v-if="datasetAssetsLoaded">个</small></strong>
          <span class="page-stat__hint">{{ datasetAssetSummary }}</span>
        </RouterLink>

        <RouterLink class="page-stat" to="/studies">
          <span class="page-stat__label">研究</span>
          <strong class="page-stat__value">{{ studyTotal }}<small>个</small></strong>
          <span class="page-stat__hint">{{ studySummary }}</span>
        </RouterLink>

        <RouterLink class="page-stat" to="/studies">
          <span class="page-stat__label">分析流程</span>
          <strong class="page-stat__value">{{ pipelineTotal }}<small>个</small></strong>
          <span class="page-stat__hint">{{ pipelineSummary }}</span>
        </RouterLink>

        <RouterLink class="page-stat" to="/studies">
          <span class="page-stat__label">分析任务</span>
          <strong class="page-stat__value">{{ executionTotal }}<small>条</small></strong>
          <span class="page-stat__hint">{{ executionSummary }}</span>
        </RouterLink>
      </section>

      <section class="dashboard-grid mb-5">
        <div class="dashboard-panel">
          <div class="section-head">
            <div>
              <h2>我的研究</h2>
              <p>继续你的研究，快速回到数据、分析和待办。</p>
            </div>
            <RouterLink v-if="recentStudies.length" class="btn btn--sm" to="/studies">查看全部</RouterLink>
          </div>

          <div v-if="loading && !studies.length" class="empty">
            <div class="empty__icon"><span class="spinner spinner--dark"></span></div>
            正在加载工作台...
          </div>

          <div v-else-if="!recentStudies.length" class="empty dashboard-empty">
            <div class="empty__icon"><AppIcon :name="studyEmptyState.icon" :size="26" /></div>
            <strong>{{ studyEmptyState.title }}</strong>
            <p>{{ studyEmptyState.description }}</p>
            <RouterLink
              v-if="studyEmptyState.action"
              class="btn btn--primary btn--sm"
              :to="studyEmptyState.action.to"
            >
              <AppIcon :name="studyEmptyState.action.icon" :size="14" />
              {{ studyEmptyState.action.label }}
            </RouterLink>
          </div>

          <div v-else class="study-list">
            <RouterLink
              v-for="study in recentStudies"
              :key="study.id"
              class="study-row"
              :to="`/studies/${study.id}`"
            >
              <span class="status-dot" :class="`is-${study.status}`"></span>
              <div class="study-row__content">
                <div class="study-row__title">
                  <strong>{{ study.name }}</strong>
                  <span v-if="study.code" class="study-code">{{ study.code }}</span>
                </div>
                <p>{{ study.description || '暂无描述' }}</p>
                <div class="study-stage">
                  <span class="study-stage__seg" :class="{ 'is-on': studyStage(study.id) >= 0 }"></span>
                  <span class="study-stage__seg" :class="{ 'is-on': studyStage(study.id) >= 1 }"></span>
                  <span class="study-stage__seg" :class="{ 'is-on': studyStage(study.id) >= 2 }"></span>
                  <span class="study-stage__text" :class="{ 'is-attention': studyMetrics(study.id).attentionExecutionCount }">{{ studyStageLabel(study.id) }}</span>
                </div>
              </div>
              <div class="study-row__meta">
                <span class="state-badge" :class="`is-${study.status}`">{{ statusLabel(study.status) }}</span>
                <span>{{ formatShortDate(study.updated_at || study.created_at) }}</span>
              </div>
            </RouterLink>
          </div>
        </div>

        <aside class="dashboard-panel live-runs">
          <div class="section-head live-runs__head">
            <div>
              <h2><span class="live-dot" :class="{ 'is-attention': attentionExecutions.length }"></span>进行中</h2>
              <p>{{ executionQueueSummary }}</p>
            </div>
            <button class="btn btn--sm" type="button" @click="activeExecutionsExpanded = !activeExecutionsExpanded">
              <AppIcon name="clock" :size="14" />
              {{ activeExecutionsExpanded ? '收起' : '展开' }}
            </button>
          </div>

          <div v-if="activeExecutionsExpanded" class="run-list">
            <div v-if="loading && !dashboardExecutions.length" class="run-empty">
              <span class="spinner spinner--dark"></span>
              正在读取运行记录...
            </div>

            <div
              v-else-if="!executionQueueItems.length"
              class="run-empty dashboard-empty dashboard-empty--compact dashboard-empty--quiet"
            >
              <div class="run-empty__icon"><AppIcon :name="executionEmptyState.icon" :size="22" /></div>
              <strong>{{ executionEmptyState.title }}</strong>
              <p>{{ executionEmptyState.description }}</p>
            </div>

            <RouterLink
              v-for="execution in executionQueueItems"
              v-else
              :key="execution.id"
              class="run-row"
              :class="{ 'is-attention': isAttentionExecutionStatus(execution.status) }"
              :to="pipelineExecutionRoute(execution)"
            >
              <span class="run-row__dot" :class="`is-${execution.status}`"></span>
              <div class="run-row__body">
                <div class="run-row__title">
                  <strong>{{ pipelineNameForExecution(execution) }}</strong>
                  <span>运行 #{{ execution.execution_seq }}</span>
                </div>
                <p>{{ executionQueueDetail(execution) }}</p>
                <div v-if="execution.status === 'running'" class="run-progress" aria-hidden="true">
                  <span></span>
                </div>
              </div>
              <span v-if="isAttentionExecutionStatus(execution.status)" class="run-row__action">{{ executionActionLabel(execution.status) }}</span>
              <span class="run-row__time">{{ formatShortDate(execution.started_at) }}</span>
            </RouterLink>
            <p v-if="hiddenQueueExecutionCount > 0" class="run-list__more">
              还有 {{ hiddenQueueExecutionCount }} 条运行，可进入工作流查看。
            </p>
          </div>
        </aside>
      </section>

      <section class="dashboard-panel activity-panel">
        <div class="section-head">
          <div>
            <h2>最近动态</h2>
            <p>数据、研究和分析的最新变化。</p>
          </div>
        </div>
        <div v-if="!activityItems.length" class="empty dashboard-empty dashboard-empty--quiet">
          <div class="empty__icon"><AppIcon name="clock" :size="26" /></div>
          <strong>暂无最近活动</strong>
          <p>导入、创建或运行后会显示在这里。</p>
        </div>
        <div v-else class="activity-timeline">
          <RouterLink
            v-for="item in activityItems"
            :key="item.id"
            class="activity-line"
            :class="[`is-sev-${item.severity || 'info'}`, item.groupKind ? 'is-group' : '']"
            :to="item.to"
          >
            <span class="activity-line__mark" :class="[`is-${item.tone}`, `is-sev-${item.severity || 'info'}`]"></span>
            <div class="activity-line__body">
              <div class="activity-line__main">
                <span class="activity-line__type" :class="`is-${item.tone}`">{{ item.objectType }}</span>
                <strong class="activity-line__title">{{ item.objectName }}</strong>
                <span class="activity-line__action">{{ item.actionLabel }}</span>
                <span class="activity-line__time" :title="formatAbsoluteTime(item.time)">{{ formatRelativeTime(item.time) }}</span>
              </div>
              <div v-if="item.studyName || item.groupSummary" class="activity-line__sub">
                <span v-if="item.studyName" class="activity-line__chip">
                  归属 <strong>{{ item.studyName }}</strong>
                </span>
                <span v-if="item.groupSummary" class="activity-line__summary">{{ item.groupSummary }}</span>
              </div>
            </div>
          </RouterLink>
        </div>
      </section>
    </template>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import { storeToRefs } from 'pinia'
import { dashboardApi } from '@/api/dashboard'
import { datasetAssetApi } from '@/api/datasetAssets'
import { pipelineApi } from '@/api/pipelines'
import { studyApi } from '@/api/studies'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { useAuthStore } from '@/stores/auth'
import type {
  DashboardActiveExecution,
  DashboardRecentActivityItem,
  DashboardRecentStudy,
  DashboardSummaryResponse,
  DatasetAsset,
  Pipeline,
  PipelineExecution,
  Study,
} from '@/types'

const MAX_SNAPSHOT_STUDIES = 3
const MAX_EXECUTION_PIPELINES = 4
const EXECUTION_QUEUE_DISPLAY_LIMIT = 5
const ACTIVITY_LIMIT = 8
const BLOCKING_STUDY_ERROR_MESSAGE = '研究项列表加载失败，请刷新后重试'
const SUMMARY_WARNING_MESSAGE = '部分摘要暂不可用，刷新后重试'
const ATTENTION_EXECUTION_STATUSES = ['waiting_user_input', 'failed']
const ACTIVE_EXECUTION_STATUSES = ['queued', 'running', 'waiting_user_input', 'pending']
const EXECUTION_STATUS_PRIORITY: Record<string, number> = {
  waiting_user_input: 0,
  failed: 1,
  running: 2,
  queued: 3,
  pending: 4,
}

interface ActivityItem {
  id: string
  objectType: '数据集' | '研究' | '分析流程' | '分析'
  objectName: string
  actionLabel: string
  time: string | null
  to: RouteLocationRaw
  tone: 'dataset' | 'study' | 'pipeline' | 'run'
  priority: number
  // 上下文
  studyId?: string | null
  studyName?: string | null
  pipelineName?: string | null
  executionSeq?: number | null
  severity?: 'info' | 'success' | 'warn' | 'error'
  // 折叠组(bootstrap = "创建数据集并配对研究项", execution_lifecycle = 多次状态合一)
  groupKind?: 'bootstrap' | 'execution_lifecycle' | 'dataset_import_batch' | null
  groupSummary?: string | null
  // 前端二次聚合用：记录被合并的子条目数 + 前几条样本名
  collapsedCount?: number
  collapsedSamples?: string[]
}

const ACTIVITY_COLLAPSE_WINDOW_MS = 5 * 60 * 1000

interface StudyMetrics {
  pipelineCount: number
  executionCount: number
  attentionExecutionCount: number
}

type DashboardStudyItem = Study | DashboardRecentStudy
type DashboardExecutionItem = PipelineExecution | DashboardActiveExecution

interface DashboardAction {
  label: string
  to: RouteLocationRaw
  icon: string
}

interface DashboardEmptyState {
  title: string
  description: string
  icon: string
  action?: DashboardAction
}

const auth = useAuthStore()
const { user } = storeToRefs(auth)

const loading = ref(false)
const errorMessage = ref('')
const warnings = ref<string[]>([])
const dashboardSummary = ref<DashboardSummaryResponse | null>(null)
const studies = ref<Study[]>([])
const datasetAssets = ref<DatasetAsset[]>([])
const datasetAssetsLoaded = ref(false)
const pipelineItems = ref<Pipeline[]>([])
const loadedPipelineStudyCount = ref(0)
const recentExecutions = ref<PipelineExecution[]>([])
const activeExecutionsExpanded = ref(true)

const warningMessage = computed(() => (warnings.value.length ? SUMMARY_WARNING_MESSAGE : ''))
const studyTotal = computed(() => dashboardSummary.value?.counts.studies ?? studies.value.length)
const pipelineTotal = computed(() => dashboardSummary.value?.counts.pipelines ?? pipelineItems.value.length)
const executionTotal = computed(() => dashboardSummary.value?.counts.executions ?? recentExecutions.value.length)
const activeStudyCount = computed(() =>
  dashboardSummary.value?.states.studies.active ?? studies.value.filter((study) => study.status === 'active').length,
)
const archivedStudyCount = computed(() =>
  dashboardSummary.value?.states.studies.archived ??
  studies.value.filter((study) => study.status === 'archived').length,
)
const recentStudies = computed<DashboardStudyItem[]>(() => {
  if (dashboardSummary.value) return dashboardSummary.value.recent_studies
  return [...studies.value]
    .sort((a, b) => timestamp(b.updated_at || b.created_at) - timestamp(a.updated_at || a.created_at))
    .slice(0, 5)
})
const workingDatasetAssetCount = computed(() =>
  dashboardSummary.value?.states.datasets.working ??
  datasetAssets.value.filter((asset) => asset.status === 'working').length,
)
const activeDatasetAssetCount = computed(() =>
  dashboardSummary.value?.states.datasets.active ??
  datasetAssets.value.filter((asset) => asset.status === 'active').length,
)
const errorDatasetAssetCount = computed(() =>
  dashboardSummary.value?.states.datasets.error ??
  datasetAssets.value.filter((asset) => isDatasetAssetErrorStatus(asset.status)).length,
)
const hasNoDatasetAssets = computed(() => {
  if (dashboardSummary.value) return dashboardSummary.value.counts.datasets === 0
  return datasetAssetsLoaded.value && !datasetAssets.value.length
})
const hasDatasetAssets = computed(() => {
  if (dashboardSummary.value) return dashboardSummary.value.counts.datasets > 0
  return datasetAssetsLoaded.value && datasetAssets.value.length > 0
})
const hasNoPipelineSnapshot = computed(() => {
  if (dashboardSummary.value) return studyTotal.value > 0 && pipelineTotal.value === 0
  return studies.value.length > 0 && loadedPipelineStudyCount.value > 0 && !pipelineItems.value.length
})
const hasPipelinesWithoutExecutions = computed(() => pipelineTotal.value > 0 && executionTotal.value === 0)
const datasetAssetStat = computed(() => {
  if (dashboardSummary.value) return dashboardSummary.value.counts.datasets
  if (!datasetAssetsLoaded.value) return '--'
  return datasetAssets.value.length
})
const datasetAssetSummary = computed(() => {
  if (!datasetAssetsLoaded.value) return '读取中'
  const parts: string[] = []
  if (activeDatasetAssetCount.value) parts.push(`${activeDatasetAssetCount.value} 份就绪`)
  if (workingDatasetAssetCount.value) parts.push(`${workingDatasetAssetCount.value} 份准备中`)
  if (errorDatasetAssetCount.value) parts.push(`${errorDatasetAssetCount.value} 份异常`)
  return parts.length ? parts.join(' · ') : '暂无数据'
})
const activePipelineCount = computed(() =>
  dashboardSummary.value?.states.pipelines.active ??
  pipelineItems.value.filter((pipeline) => pipeline.status === 'active').length,
)
const draftPipelineCount = computed(() =>
  dashboardSummary.value?.states.pipelines.draft ??
  pipelineItems.value.filter((pipeline) => pipeline.status === 'draft').length,
)
const studySummary = computed(() => {
  const parts = [`${activeStudyCount.value} 项进行中`]
  if (archivedStudyCount.value) parts.push(`${archivedStudyCount.value} 项已归档`)
  return parts.join(' · ')
})
const pipelineSummary = computed(() => {
  const parts = [`${activePipelineCount.value} 个就绪`]
  if (draftPipelineCount.value) parts.push(`${draftPipelineCount.value} 个草稿`)
  return parts.join(' · ')
})
const dashboardExecutions = computed<DashboardExecutionItem[]>(() => dashboardSummary.value?.active_executions ?? recentExecutions.value)
const waitingUserInputExecutions = computed(() => dashboardExecutions.value.filter((execution) => execution.status === 'waiting_user_input'))
const failedExecutions = computed(() => dashboardExecutions.value.filter((execution) => execution.status === 'failed'))
const attentionExecutions = computed(() =>
  [...dashboardExecutions.value]
    .filter((execution) => isAttentionExecutionStatus(execution.status))
    .sort(compareExecutionsByPriority),
)
const activeExecutions = computed(() =>
  [...dashboardExecutions.value]
    .filter((execution) => isActiveExecutionStatus(execution.status))
    .sort(compareExecutionsByPriority),
)
const prioritizedExecutions = computed(() =>
  [...dashboardExecutions.value]
    .filter((execution) => isAttentionExecutionStatus(execution.status) || isActiveExecutionStatus(execution.status))
    .sort(compareExecutionsByPriority),
)
const executionQueueItems = computed(() => prioritizedExecutions.value.slice(0, EXECUTION_QUEUE_DISPLAY_LIMIT))
const waitingUserInputExecutionCount = computed(() =>
  dashboardSummary.value?.states.executions.waiting_user_input ?? waitingUserInputExecutions.value.length,
)
const failedExecutionCount = computed(() => dashboardSummary.value?.states.executions.failed ?? failedExecutions.value.length)
const runningExecutions = computed(() => dashboardExecutions.value.filter((execution) => execution.status === 'running'))
const queuedExecutions = computed(() => dashboardExecutions.value.filter((execution) => ['queued', 'pending'].includes(execution.status)))
const runningExecutionCount = computed(() => dashboardSummary.value?.states.executions.running ?? runningExecutions.value.length)
const queuedExecutionCount = computed(() => {
  if (dashboardSummary.value) {
    return dashboardSummary.value.states.executions.queued + dashboardSummary.value.states.executions.pending
  }
  return queuedExecutions.value.length
})
const attentionExecutionCount = computed(() => {
  if (dashboardSummary.value) return waitingUserInputExecutionCount.value + failedExecutionCount.value
  return attentionExecutions.value.length
})
const prioritizedExecutionCount = computed(() => {
  if (dashboardSummary.value) {
    const states = dashboardSummary.value.states.executions
    return states.waiting_user_input + states.failed + states.running + states.queued + states.pending
  }
  return prioritizedExecutions.value.length
})
const hiddenQueueExecutionCount = computed(() => Math.max(prioritizedExecutionCount.value - executionQueueItems.value.length, 0))
const executionSummary = computed(() => {
  if (waitingUserInputExecutionCount.value || failedExecutionCount.value) {
    const parts: string[] = []
    if (waitingUserInputExecutionCount.value) parts.push(`${waitingUserInputExecutionCount.value} 个待确认`)
    if (failedExecutionCount.value) parts.push(`${failedExecutionCount.value} 个失败`)
    return parts.join(' · ')
  }
  if (runningExecutionCount.value || queuedExecutionCount.value) {
    return `${runningExecutionCount.value} 个进行中 · ${queuedExecutionCount.value} 个排队`
  }
  return '近期无异常'
})
const executionQueueSummary = computed(() => {
  if (attentionExecutionCount.value) {
    return `${attentionExecutionCount.value} 个需要处理 · ${waitingUserInputExecutionCount.value} 个确认 · ${failedExecutionCount.value} 个失败`
  }
  if (runningExecutionCount.value || queuedExecutionCount.value) {
    return `${runningExecutionCount.value} 个进行中 · ${queuedExecutionCount.value} 个排队`
  }
  return '当前没有进行中的分析'
})
const dashboardStatusText = computed(() => {
  if (loading.value && !dashboardSummary.value && !studies.value.length && !datasetAssetsLoaded.value) {
    return '正在读取工作台状态'
  }
  if (attentionExecutionCount.value) {
    if (waitingUserInputExecutionCount.value) {
      return `${waitingUserInputExecutionCount.value} 条运行等待确认`
    }
    return `${failedExecutionCount.value} 条运行失败需要查看`
  }
  if (runningExecutionCount.value || queuedExecutionCount.value) {
    return `${runningExecutionCount.value} 个运行中 · ${queuedExecutionCount.value} 个排队中`
  }
  if (hasNoDatasetAssets.value) {
    return '还没有数据集，先导入数据'
  }
  if (!studyTotal.value) {
    return '还没有研究，先创建一个'
  }
  if (hasNoPipelineSnapshot.value) {
    return '还没有分析流程，可先建立一个'
  }
  if (hasPipelinesWithoutExecutions.value) {
    return '还没有运行记录'
  }
  if (!datasetAssetsLoaded.value) {
    return '部分摘要暂不可用，核心入口仍可使用'
  }
  return '工作台状态正常'
})
const dashboardStatusTone = computed(() => {
  if (waitingUserInputExecutionCount.value) return 'is-attention'
  if (failedExecutionCount.value) return 'is-danger'
  if (runningExecutionCount.value || queuedExecutionCount.value) return 'is-running'
  if (
    hasNoDatasetAssets.value ||
    !studyTotal.value ||
    hasNoPipelineSnapshot.value ||
    hasPipelinesWithoutExecutions.value
  ) {
    return 'is-muted'
  }
  return 'is-ok'
})

// UI Phase (docs_v2/6-05) P1-1: 需要处理 警示横幅 — 仅在有阻塞事项时显示
interface AttentionBanner {
  tone: 'danger' | 'warn'
  icon: string
  title: string
  description: string
  actions: Array<{ label: string; to: RouteLocationRaw }>
}
const attentionBanner = computed<AttentionBanner | null>(() => {
  const waiting = waitingUserInputExecutionCount.value
  const failed = failedExecutionCount.value
  // 失败优先级最高（红色）
  if (failed > 0) {
    const parts: string[] = []
    if (failed > 0) parts.push(`${failed} 条运行失败`)
    if (waiting > 0) parts.push(`${waiting} 个等待确认`)
    return {
      tone: 'danger',
      icon: 'alert',
      title: '需要处理',
      description: parts.join(' · ') + '，建议尽快查看',
      actions: [
        ...(failed > 0 && failedExecutions.value.length
          ? [{ label: `查看失败 (${failed})`, to: pipelineExecutionRoute(failedExecutions.value[0]) }]
          : []),
        ...(waiting > 0 && waitingUserInputExecutions.value.length
          ? [{ label: `处理确认 (${waiting})`, to: pipelineExecutionRoute(waitingUserInputExecutions.value[0]) }]
          : []),
      ],
    }
  }
  // 仅等待确认（橙色）
  if (waiting > 0) {
    return {
      tone: 'warn',
      icon: 'pause',
      title: '有任务等待你确认',
      description: `${waiting} 条运行暂停在确认环节，需要你介入推进`,
      actions: waitingUserInputExecutions.value.length
        ? [{ label: `去确认 (${waiting})`, to: pipelineExecutionRoute(waitingUserInputExecutions.value[0]) }]
        : [],
    }
  }
  return null
})

const studyEmptyState = computed<DashboardEmptyState>(() => {
  if (hasNoDatasetAssets.value) {
    return {
      title: '导入数据',
      description: '先把数据放进工作台。',
      icon: 'import',
      action: { label: '导入数据', to: '/datasets', icon: 'import' },
    }
  }
  if (hasDatasetAssets.value && !studyTotal.value) {
    return {
      title: '创建研究',
      description: '用研究组织你的数据和分析。',
      icon: 'studies',
      action: { label: '创建研究', to: '/studies', icon: 'plus' },
    }
  }
  return {
    title: '创建研究',
    description: '先建立研究，再继续。',
    icon: 'studies',
    action: { label: '创建研究', to: '/studies', icon: 'plus' },
  }
})
const executionEmptyState = computed<DashboardEmptyState>(() => {
  if (hasNoPipelineSnapshot.value) {
    return {
      title: '建立分析流程',
      description: '为研究配置一套分析流程。',
      icon: 'pipeline',
    }
  }
  if (!studyTotal.value || hasNoDatasetAssets.value) {
    return {
      title: '等待前置设置',
      description: '先完成数据和研究设置。',
      icon: 'clock',
    }
  }
  return {
    title: '暂无进行中的分析',
    description: '没有等待处理或正在运行的任务。',
    icon: 'clock',
  }
})
const studyMetricsMap = computed<Record<string, StudyMetrics>>(() => {
  const map: Record<string, StudyMetrics> = {}
  if (dashboardSummary.value) {
    dashboardSummary.value.recent_studies.forEach((study) => {
      map[study.id] = {
        pipelineCount: study.metrics.pipeline_count,
        executionCount: study.metrics.execution_count,
        attentionExecutionCount: study.metrics.attention_execution_count,
      }
    })
    return map
  }

  studies.value.forEach((study) => {
    map[study.id] = { pipelineCount: 0, executionCount: 0, attentionExecutionCount: 0 }
  })
  pipelineItems.value.forEach((pipeline) => {
    const metrics = map[pipeline.study_id] || { pipelineCount: 0, executionCount: 0, attentionExecutionCount: 0 }
    metrics.pipelineCount += 1
    map[pipeline.study_id] = metrics
  })
  recentExecutions.value.forEach((execution) => {
    const metrics = map[execution.study_id] || { pipelineCount: 0, executionCount: 0, attentionExecutionCount: 0 }
    metrics.executionCount += 1
    if (isAttentionExecutionStatus(execution.status)) metrics.attentionExecutionCount += 1
    map[execution.study_id] = metrics
  })
  return map
})
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  if (hour < 22) return '晚上好'
  return '夜深了'
})
const todayLabel = computed(() => {
  const date = new Date()
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日 · ${week}`
})
const activityItems = computed<ActivityItem[]>(() => {
  if (!dashboardSummary.value) return []
  const raw = dashboardSummary.value.recent_activity.map(summaryActivityToItem)
  return collapseDatasetImportBatches(raw).slice(0, ACTIVITY_LIMIT)
})

// 把同一研究项 + 同一动作 + 相近时间的多条「数据集导入」合并成一条「批量导入 N 条采集记录」
function collapseDatasetImportBatches(items: ActivityItem[]): ActivityItem[] {
  if (!items.length) return items
  const result: ActivityItem[] = []
  for (const item of items) {
    const last = result[result.length - 1]
    const mergeable =
      last !== undefined &&
      last.objectType === '数据集' &&
      item.objectType === '数据集' &&
      last.actionLabel === item.actionLabel &&
      last.studyId === item.studyId &&
      timeWithin(last.time, item.time, ACTIVITY_COLLAPSE_WINDOW_MS)
    if (mergeable && last) {
      const count = (last.collapsedCount ?? 1) + 1
      const samples = (last.collapsedSamples ?? [last.objectName]).slice(0, 3)
      if (samples.length < 3) samples.push(item.objectName)
      last.collapsedCount = count
      last.collapsedSamples = samples
      last.objectName = `批量导入 ${count} 条采集记录`
      last.groupKind = 'dataset_import_batch'
      last.groupSummary = samples.length === count
        ? `包括 ${samples.join('、')}`
        : `包括 ${samples.join('、')} 等`
      // 时间取最早一条（保留最新的"刚刚"感更好？这里取最新）
      last.time = item.time || last.time
    } else {
      result.push({ ...item })
    }
  }
  return result
}

function timeWithin(a: string | null, b: string | null, windowMs: number): boolean {
  if (!a || !b) return false
  const ta = new Date(a).getTime()
  const tb = new Date(b).getTime()
  if (!Number.isFinite(ta) || !Number.isFinite(tb)) return false
  return Math.abs(ta - tb) <= windowMs
}

async function loadDashboard() {
  loading.value = true
  errorMessage.value = ''
  warnings.value = []

  try {
    const summaryRes = await dashboardApi.summary()
    applyDashboardSummary(summaryRes.data)
    loading.value = false
    return
  } catch {
    dashboardSummary.value = null
    addSummaryWarning()
  }

  await loadDashboardFallback()
  loading.value = false
}

async function loadDashboardFallback() {
  try {
    const studyRes = await studyApi.list()
    studies.value = studyRes.data.studies
  } catch {
    errorMessage.value = BLOCKING_STUDY_ERROR_MESSAGE
    resetDashboardData()
    return
  }

  await Promise.all([loadDatasetAssets(), loadPipelineSnapshot()])
}

function applyDashboardSummary(summary: DashboardSummaryResponse) {
  dashboardSummary.value = summary
  studies.value = []
  datasetAssets.value = []
  datasetAssetsLoaded.value = true
  pipelineItems.value = []
  recentExecutions.value = []
  loadedPipelineStudyCount.value = 0
}

async function loadDatasetAssets() {
  datasetAssetsLoaded.value = false
  try {
    const res = await datasetAssetApi.list()
    datasetAssets.value = res.data.assets
    datasetAssetsLoaded.value = true
  } catch {
    datasetAssets.value = []
    addSummaryWarning()
  }
}

async function loadPipelineSnapshot() {
  pipelineItems.value = []
  recentExecutions.value = []
  loadedPipelineStudyCount.value = 0

  const snapshotStudies = studies.value.slice(0, MAX_SNAPSHOT_STUDIES)
  if (!snapshotStudies.length) return

  let summaryFailed = false
  const pipelineGroups = await Promise.all(
    snapshotStudies.map(async (study) => {
      try {
        const res = await pipelineApi.list(study.id)
        loadedPipelineStudyCount.value += 1
        return res.data.pipelines
      } catch {
        summaryFailed = true
        return []
      }
    }),
  )

  pipelineItems.value = pipelineGroups
    .flat()
    .sort((a, b) => timestamp(b.updated_at || b.created_at) - timestamp(a.updated_at || a.created_at))

  const executionTargets = pipelineItems.value.slice(0, MAX_EXECUTION_PIPELINES)
  const executionGroups = await Promise.all(
    executionTargets.map(async (pipeline) => {
      try {
        const res = await pipelineApi.listExecutions(pipeline.study_id, pipeline.id, 3)
        return res.data.executions
      } catch {
        summaryFailed = true
        return []
      }
    }),
  )

  recentExecutions.value = executionGroups
    .flat()
    .sort((a, b) => timestamp(b.finished_at || b.started_at) - timestamp(a.finished_at || a.started_at))
    .slice(0, 8)

  if (summaryFailed) addSummaryWarning()
}

function resetDashboardData() {
  dashboardSummary.value = null
  studies.value = []
  datasetAssets.value = []
  datasetAssetsLoaded.value = false
  pipelineItems.value = []
  recentExecutions.value = []
  loadedPipelineStudyCount.value = 0
}

function addSummaryWarning() {
  if (!warnings.value.includes(SUMMARY_WARNING_MESSAGE)) {
    warnings.value.push(SUMMARY_WARNING_MESSAGE)
  }
}

function studyMetrics(studyId: string) {
  return studyMetricsMap.value[studyId] || { pipelineCount: 0, executionCount: 0, attentionExecutionCount: 0 }
}

// 研究阶段（粗粒度）：跑过分析(有结果) > 有分析流程 > 仅有数据。后端 summary 给出 completed 数后可细化。
function studyStage(studyId: string): number {
  const metrics = studyMetrics(studyId)
  if (metrics.executionCount > 0) return 2
  if (metrics.pipelineCount > 0) return 1
  return 0
}

function studyStageLabel(studyId: string): string {
  if (studyMetrics(studyId).attentionExecutionCount > 0) return '需要你看一下'
  return ['待建立分析', '分析进行中', '结果就绪'][studyStage(studyId)]
}

function pipelineNameForExecution(execution: DashboardExecutionItem) {
  if ('pipeline_name' in execution && execution.pipeline_name) return execution.pipeline_name
  const pipeline = pipelineItems.value.find(
    (item) => item.study_id === execution.study_id && item.id === execution.pipeline_id,
  )
  return pipeline?.name || `Pipeline #${execution.pipeline_id}`
}

function pipelineExecutionRoute(execution: DashboardExecutionItem): RouteLocationRaw {
  return {
    path: `/studies/${execution.study_id}/pipeline`,
    query: {
      pipeline_id: String(execution.pipeline_id),
      execution_id: execution.id,
    },
  }
}

function executionQueueDetail(execution: DashboardExecutionItem) {
  if ('stage_label' in execution && execution.stage_label) {
    return `${executionStatusLabel(execution.status)} · ${execution.stage_label}`
  }
  return `${executionStatusLabel(execution.status)} · ${executionModeLabel(execution.execution_mode)}`
}

function isActiveExecutionStatus(status: string) {
  return ACTIVE_EXECUTION_STATUSES.includes(status)
}

function isAttentionExecutionStatus(status: string) {
  return ATTENTION_EXECUTION_STATUSES.includes(status)
}

function compareExecutionsByPriority(a: DashboardExecutionItem, b: DashboardExecutionItem) {
  const priorityDiff = executionStatusPriority(a.status) - executionStatusPriority(b.status)
  if (priorityDiff !== 0) return priorityDiff
  return timestamp(b.finished_at || b.started_at) - timestamp(a.finished_at || a.started_at)
}

function executionStatusPriority(status: string) {
  return EXECUTION_STATUS_PRIORITY[status] ?? 9
}

function executionActionLabel(status: string) {
  if (status === 'waiting_user_input') return '进入确认'
  if (status === 'failed') return '查看错误'
  return '查看详情'
}

function summaryActivityToItem(item: DashboardRecentActivityItem, index: number): ActivityItem {
  const objectType = summaryObjectKindLabel(item.object_kind)
  return {
    id: `summary-${index}-${item.object_kind}-${item.object_name}`,
    objectType,
    objectName: item.object_name,
    actionLabel: item.action_label,
    time: item.created_at || null,
    to: item.target_url || defaultActivityRoute(item.object_kind),
    tone: activityTone(item.object_kind),
    priority: index,
    studyId: item.study_id ?? null,
    studyName: item.study_name ?? null,
    pipelineName: item.pipeline_name ?? null,
    executionSeq: item.execution_seq ?? null,
    severity: item.severity ?? 'info',
    groupKind: item.group_kind ?? null,
    groupSummary: item.group_summary ?? null,
  }
}

// 活动条目的 tone 同时用于 CSS class（.is-run/.is-pipeline 等，保留旧类名）。
// 后端 object_kind 现为 'execution'，映射到 CSS 用的 'run' tone。
function activityTone(kind: DashboardRecentActivityItem['object_kind']): ActivityItem['tone'] {
  if (kind === 'execution') return 'run'
  return kind
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  const diffMs = Date.now() - date.getTime()
  if (!Number.isFinite(diffMs)) return ''
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 0) return formatShortDate(iso)
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24 && date.toDateString() === new Date().toDateString()) {
    return `${diffH} 小时前`
  }
  // 同一日历日(理论上覆盖很多边缘),否则降级到 MM/DD HH:MM
  return formatShortDate(iso)
}

function formatAbsoluteTime(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (!Number.isFinite(date.getTime())) return ''
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const HH = String(date.getHours()).padStart(2, '0')
  const MM = String(date.getMinutes()).padStart(2, '0')
  const SS = String(date.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${HH}:${MM}:${SS}`
}

function summaryObjectKindLabel(kind: DashboardRecentActivityItem['object_kind']): ActivityItem['objectType'] {
  const labels: Record<DashboardRecentActivityItem['object_kind'], ActivityItem['objectType']> = {
    dataset: '数据集',
    study: '研究',
    pipeline: '分析流程',
    execution: '分析',
  }
  return labels[kind]
}

function defaultActivityRoute(kind: DashboardRecentActivityItem['object_kind']): RouteLocationRaw {
  if (kind === 'dataset') return '/datasets'
  return '/studies'
}

function executionModeLabel(mode: string) {
  const labels: Record<string, string> = {
    trial: '试跑',
    analysis: '分析',
    replay: '复现',
    system: '系统',
  }
  return labels[mode] || mode
}

function isDatasetAssetErrorStatus(status: string) {
  return ['error', 'failed', 'quarantined', 'deleted'].includes(status)
}

function timestamp(value: string | null | undefined) {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? 0 : time
}

function formatShortDate(value: string | null | undefined) {
  if (!value) return '暂无时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无时间'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: '活跃',
    archived: '已归档',
    trashed: '回收站',
    deleted: '已删除',
  }
  return labels[status] || status
}

function executionStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: '排队中',
    pending: '等待调度',
    running: '运行中',
    waiting_user_input: '等待确认',
    completed: '已完成',
    failed: '失败',
    canceled: '已取消',
  }
  return labels[status] || status
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-header {
  align-items: flex-start;
  gap: var(--s-4);
}

.dashboard-date {
  margin: 6px 0 0;
  color: var(--c-text-3);
  font-size: 13px;
}

.dashboard-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  margin: 8px 0 0;
  padding: 4px 9px;
  color: var(--c-text-2);
  font-size: 12px;
  line-height: 1.35;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill);
  box-shadow: var(--shadow-sm);
}

.dashboard-status__dot {
  width: 7px;
  height: 7px;
  background: var(--c-text-3);
  border-radius: 999px;
  flex-shrink: 0;
}

.dashboard-status.is-ok .dashboard-status__dot {
  background: var(--c-success);
}

.dashboard-status.is-running .dashboard-status__dot {
  background: var(--c-info);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .14);
}

.dashboard-status.is-attention {
  color: var(--c-warning);
  background: var(--c-warning-soft);
  border-color: transparent;
}

.dashboard-status.is-attention .dashboard-status__dot {
  background: var(--c-warning);
}

.dashboard-status.is-danger {
  color: var(--c-danger);
  background: var(--c-danger-soft);
  border-color: transparent;
}

.dashboard-status.is-danger .dashboard-status__dot {
  background: var(--c-danger);
}

.dashboard-status.is-muted .dashboard-status__dot {
  background: var(--c-text-3);
}

.dashboard-alert {
  align-items: center;
}

.dashboard-alert .alert__body {
  flex: 1;
  min-width: 0;
}

/* UI Phase (docs_v2/6-05) P1-1: 需要处理 警示横幅 */
.attention-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  border-radius: 10px;
  padding: 14px 18px;
  margin-bottom: 16px;
  border-left: 4px solid;
}
.attention-banner--danger {
  background: var(--c-danger-soft);
  border-left-color: var(--c-danger);
  color: #7f1d1d;
}
.attention-banner--warn {
  background: var(--c-warning-soft);
  border-left-color: var(--c-warning);
  color: #92400e;
}
.attention-banner__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  color: inherit;
}
.attention-banner__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.attention-banner__body strong {
  font-size: 15px;
  color: inherit;
}
.attention-banner__body span {
  color: inherit;
  opacity: 0.85;
  font-size: 13px;
}
.attention-banner__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.attention-banner__action {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  color: inherit;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  border: 1px solid currentColor;
}
.attention-banner__action:hover {
  background: rgba(255, 255, 255, 0.95);
}

.dashboard-alert .btn {
  flex-shrink: 0;
}

.dashboard-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--s-2);
  flex-shrink: 0;
}

.dashboard-primary-action {
  min-width: 136px;
}

/* 顶部核心对象摘要:复用全局 .page-stat-strip/.page-stat(与 datasets 页一致),
   这里仅补两条:RouterLink 版去下划线 + 数字后单位(个/条)弱化 */
a.page-stat {
  text-decoration: none;
  color: inherit;
}

.page-stat__value small {
  margin-left: 3px;
  color: var(--c-text-3);
  font-size: 13px;
  font-weight: 500;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, .9fr);
  gap: var(--s-4);
  align-items: start;
}

.dashboard-panel {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-5);
  box-shadow: var(--shadow-sm);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: var(--s-4);
  align-items: flex-start;
  margin-bottom: var(--s-4);
}

.section-head h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}

.section-head p {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.65;
}

.dashboard-empty {
  gap: 9px;
  min-height: 210px;
  padding: var(--s-6) var(--s-5);
}

.dashboard-empty strong {
  color: var(--c-text);
  font-size: 15px;
  font-weight: 800;
}

.dashboard-empty p {
  max-width: 280px;
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.dashboard-empty .btn {
  margin-top: var(--s-1);
}

.dashboard-empty--compact {
  display: flex;
  flex-direction: column;
  min-height: 174px;
}

.dashboard-empty--quiet {
  color: var(--c-text-3);
  background: var(--c-bg-soft);
}

.dashboard-empty--quiet .empty__icon,
.dashboard-empty--quiet .run-empty__icon {
  color: var(--c-text-3);
  background: var(--c-bg);
}

.study-list {
  display: grid;
  gap: var(--s-3);
  min-width: 0;
}

.study-row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) minmax(72px, auto);
  align-items: center;
  gap: var(--s-3);
  min-width: 0;
  padding: 13px 14px;
  color: var(--c-text);
  text-decoration: none;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}

.study-row:hover {
  border-color: var(--c-border-strong);
  background: #fafbfd;
}

.study-row__content {
  min-width: 0;
}

.study-row__title {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  min-width: 0;
  overflow: hidden;
}

.study-row__title strong {
  min-width: 0;
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.study-code {
  flex: 0 1 auto;
  min-width: 0;
  max-width: min(180px, 42%);
  overflow: hidden;
  padding: 1px 6px;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
}

.study-row__content p {
  margin: 3px 0 0;
  overflow: hidden;
  color: var(--c-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.study-stage {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 9px;
  min-width: 0;
}

.study-stage__seg {
  width: 26px;
  height: 4px;
  border-radius: 2px;
  background: var(--c-border);
}

.study-stage__seg.is-on {
  background: var(--c-primary);
}

.study-stage__text {
  margin-left: 8px;
  color: var(--c-text-2);
  font-size: 12px;
  white-space: nowrap;
}

.study-stage__text.is-attention {
  color: var(--c-warning);
}

.study-row__meta {
  display: grid;
  gap: 7px;
  justify-items: end;
  min-width: 0;
  flex-shrink: 0;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
}

.study-row__meta > span:last-child {
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-badge {
  padding: 3px 8px;
  color: var(--c-text-3);
  font-family: var(--ff-sans);
  font-size: 11px;
  font-weight: 700;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill);
}

.state-badge.is-active {
  color: var(--c-success);
  background: var(--c-success-soft);
  border-color: transparent;
}

.state-badge.is-archived {
  color: var(--c-warning);
  background: var(--c-warning-soft);
  border-color: transparent;
}

.status-dot {
  width: 9px;
  height: 9px;
  background: var(--c-text-3);
  border-radius: 999px;
  flex-shrink: 0;
}

.status-dot.is-active {
  background: var(--c-success);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, .14);
}

.status-dot.is-archived {
  background: var(--c-warning);
}

.status-dot.is-trashed,
.status-dot.is-deleted {
  background: var(--c-danger);
}

.live-runs {
  overflow: hidden;
}

.live-runs__head {
  align-items: center;
}

.live-runs h2 {
  display: flex;
  align-items: center;
}

.live-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 8px;
  background: var(--c-info);
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, .16);
  animation: pulse 1.45s ease-out infinite;
}

.live-dot.is-attention {
  background: var(--c-warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, .16);
}

.run-list {
  display: grid;
  gap: var(--s-3);
}

.run-list__more {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  text-align: center;
}

.run-row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--s-3);
  padding: 13px 14px;
  color: var(--c-text);
  text-decoration: none;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
}

.run-row.is-attention {
  background: #fffbf1;
  border-color: rgba(245, 158, 11, .28);
}

.run-row:hover {
  border-color: var(--c-border-strong);
  background: #fafbfd;
}

.run-row__dot {
  width: 9px;
  height: 9px;
  background: var(--c-text-3);
  border-radius: 999px;
  flex-shrink: 0;
}

.run-row__dot.is-running {
  background: var(--c-info);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, .16);
  animation: pulse 1.45s ease-out infinite;
}

.run-row__dot.is-waiting_user_input {
  background: var(--c-warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, .16);
}

.run-row__dot.is-failed {
  background: var(--c-danger);
  box-shadow: 0 0 0 4px rgba(239, 68, 68, .14);
}

.run-row__dot.is-queued,
.run-row__dot.is-pending {
  background: var(--c-accent);
}

.run-row__body {
  min-width: 0;
}

.run-row__title {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  min-width: 0;
}

.run-row__title strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-row__title span {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
}

.run-row__body p {
  margin: 2px 0 0;
  overflow: hidden;
  color: var(--c-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-row__action {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  color: var(--c-text);
  font-size: 12px;
  font-weight: 700;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill);
  white-space: nowrap;
}

.run-row__time {
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
  white-space: nowrap;
}

.run-progress {
  height: 5px;
  margin-top: 8px;
  overflow: hidden;
  background: var(--c-bg-tint);
  border-radius: 999px;
}

.run-progress span {
  display: block;
  width: 58%;
  height: 100%;
  background: linear-gradient(90deg, var(--c-primary), var(--c-info), var(--c-accent));
  background-size: 220% 100%;
  border-radius: inherit;
  animation: progress-flow 1.8s linear infinite;
}

.run-empty {
  display: grid;
  place-items: center;
  min-height: 174px;
  padding: var(--s-5);
  color: var(--c-text-3);
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
  background: var(--c-bg-soft);
  border: 1px dashed var(--c-border);
  border-radius: var(--r);
}

.run-empty__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-bottom: var(--s-2);
  color: var(--c-info);
  background: var(--c-info-soft);
  border-radius: var(--r-pill);
}

.run-empty.dashboard-empty {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-empty.dashboard-empty strong {
  color: var(--c-text);
  font-size: 14px;
  font-weight: 800;
}

.run-empty.dashboard-empty p {
  margin: 0;
  color: var(--c-text-3);
}

.run-empty.dashboard-empty--quiet .run-empty__icon {
  color: var(--c-text-3);
  background: var(--c-bg);
}

.activity-panel {
  padding-bottom: var(--s-4);
}

.activity-timeline {
  display: grid;
  gap: var(--s-2);
}

.activity-line {
  position: relative;
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr);
  gap: var(--s-3);
  padding: 10px 0 10px;
  color: var(--c-text);
  text-decoration: none;
}

.activity-line + .activity-line {
  border-top: 1px solid var(--c-border);
}

.activity-line__mark {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  background: var(--c-text-3);
  border: 3px solid var(--c-surface);
  border-radius: 999px;
  box-shadow: 0 0 0 1px var(--c-border);
}

.activity-line__mark.is-dataset {
  background: var(--c-primary);
}

.activity-line__mark.is-study {
  background: var(--c-accent);
}

.activity-line__mark.is-pipeline {
  background: var(--c-warning);
}

.activity-line__mark.is-run {
  background: var(--c-info);
}

.activity-line__body {
  min-width: 0;
}

.activity-line__main {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--s-2);
  min-width: 0;
}

.activity-line__title {
  flex: 1 1 auto;
  min-width: 0;
}

.activity-line__type {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0;
  background: var(--c-bg);
  border: 1px solid var(--c-border);
  border-radius: var(--r-pill);
}

.activity-line__type.is-dataset {
  color: var(--c-primary);
  background: var(--c-primary-soft);
  border-color: transparent;
}

.activity-line__type.is-study {
  color: var(--c-accent);
  background: var(--c-accent-soft);
  border-color: transparent;
}

.activity-line__type.is-pipeline {
  color: var(--c-warning);
  background: var(--c-warning-soft);
  border-color: transparent;
}

.activity-line__type.is-run {
  color: var(--c-info);
  background: var(--c-info-soft);
  border-color: transparent;
}

.activity-line__body strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-line__action {
  overflow: hidden;
  max-width: 120px;
  color: var(--c-text-2);
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-line__main > span:last-child {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
  white-space: nowrap;
}

/* severity 色条:覆盖 tone 默认色,语义优先 */
.activity-line__mark.is-sev-success { background: var(--c-success, #2F766F); }
.activity-line__mark.is-sev-warn { background: var(--c-warning, #C7831D); }
.activity-line__mark.is-sev-error { background: var(--c-danger, #DC2626); }
/* is-sev-info 保留 tone 颜色,不覆盖 */

/* 折叠组卡片轻微突出 */
.activity-line.is-group {
  padding-left: 4px;
  border-left: 2px solid var(--c-primary-soft, #E0E7FF);
  background: linear-gradient(90deg, var(--c-bg, #FAFBFC) 0%, transparent 60%);
}

/* 运行 #seq 后面跟的 pipeline 名(灰色,次重要) */
.activity-line__meta {
  overflow: hidden;
  max-width: 200px;
  color: var(--c-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 时间 - 主显示相对时间(刚刚 / N 分钟前),hover 看绝对时间 */
.activity-line__time {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-family: var(--ff-mono);
  font-size: 11px;
  white-space: nowrap;
  cursor: help;
}

/* 副行:"in <Study>" 徽章 + bootstrap group_summary */
.activity-line__sub {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--c-text-3);
}

.activity-line__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  color: var(--c-text-2);
  font-size: 11px;
  background: var(--c-bg, #F4F6FA);
  border: 1px solid var(--c-border, #E5E7EB);
  border-radius: var(--r-pill, 999px);
}

.activity-line__chip strong {
  color: var(--c-text);
  font-weight: 700;
}

.activity-line__summary {
  overflow: hidden;
  color: var(--c-text-2);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-line__body p {
  margin: 3px 0 0;
  overflow: hidden;
  color: var(--c-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, .36);
  }
  70% {
    box-shadow: 0 0 0 9px rgba(59, 130, 246, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
  }
}

@keyframes progress-flow {
  0% {
    background-position: 0% 0;
  }
  100% {
    background-position: 220% 0;
  }
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .dashboard-header {
    align-items: stretch;
    flex-direction: column;
  }

  .dashboard-status {
    width: fit-content;
    max-width: 100%;
  }

  .dashboard-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .dashboard-primary-action {
    min-width: 0;
  }

  .dashboard-panel {
    padding: var(--s-4);
  }

  .section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .study-row,
  .run-row {
    grid-template-columns: 10px minmax(0, 1fr);
    align-items: start;
  }

  .study-row__meta,
  .run-row__action,
  .run-row__time {
    grid-column: 2;
    justify-items: start;
  }

  .study-row__meta {
    display: flex;
    align-items: center;
  }

  .run-row__time {
    display: block;
  }

  .run-row__action {
    justify-self: start;
  }

  .activity-line__main {
    grid-template-columns: auto minmax(0, 1fr);
    gap: 6px 8px;
  }

  .activity-line__action {
    max-width: 100%;
  }
}

</style>
