<template>
  <!-- 版心对齐主页 .hero__inner(1200)：与 Dashboard/Datasets 同款，--content-w=1200 + --page-pad-x=0。仅本页生效。 -->
  <WorkbenchShell active-key="studies" active-top-key="studies" :show-sidebar="false" :narrow="true" :style="{ '--content-w': '1200px', '--page-pad-x': '0px' }">
    <div class="studies-page">
      <div class="page__header studies-page__header">
        <div>
          <h1 class="page__title">研究项</h1>
          <p class="page__subtitle">
            研究项用来组织协作、质控、工作流与运行记录。数据集作为独立数据资产挂载到研究项中，
            这里重点展示每个研究项当前能不能继续处理。
          </p>
        </div>
        <div class="studies-page__actions">
          <button class="btn btn--ghost" type="button" :disabled="loading" @click="loadStudies">
            <AppIcon name="refresh" :size="16" />
            刷新
          </button>
          <button v-if="canCreateStudy" class="btn btn--primary" type="button" @click="openCreateModal">
            <AppIcon name="plus" :size="16" />
            新建研究项
          </button>
        </div>
      </div>

      <section class="study-overview-bar" aria-label="研究项摘要">
        <div class="page-stat-strip">
          <article class="page-stat">
            <span class="page-stat__label">活跃研究项</span>
            <strong class="page-stat__value">{{ activeStudies.length }}</strong>
          </article>
          <article class="page-stat">
            <span class="page-stat__label">可进入处理</span>
            <strong class="page-stat__value">{{ readyStudyCount }}</strong>
          </article>
          <article class="page-stat">
            <span class="page-stat__label">需导入数据</span>
            <strong class="page-stat__value">{{ needsDataCount }}</strong>
          </article>
          <article class="page-stat">
            <span class="page-stat__label">进行中的运行</span>
            <strong class="page-stat__value">{{ runningStudyCount }}</strong>
          </article>
        </div>
        <div class="study-tabs" role="tablist" aria-label="研究项视图">
          <button type="button" :class="{ active: viewMode === 'active' }" @click="switchView('active')">
            活跃
          </button>
          <button type="button" :class="{ active: viewMode === 'trash' }" @click="switchView('trash')">
            回收站
            <span v-if="trashedStudies.length">{{ trashedStudies.length }}</span>
          </button>
        </div>
      </section>

      <div v-if="error" class="alert alert--error">
        {{ error }}
      </div>
      <div v-if="summaryWarnings.length" class="alert alert--warning">
        {{ summaryWarnings.join('；') }}
      </div>
      <div v-if="successMessage" class="alert alert--success">
        {{ successMessage }}
      </div>

      <section class="study-workbench">
        <aside class="study-list-panel" aria-label="研究项列表">
          <div class="study-list-panel__head">
            <div>
              <h2>研究项目录</h2>
              <p>{{ visibleStudies.length }} / {{ baseStudyCount }} 个</p>
            </div>
          </div>

          <div class="study-list-toolbar">
            <label class="study-search">
              <AppIcon name="search" :size="16" />
              <input v-model.trim="studySearch" type="search" placeholder="搜索名称、code 或描述" />
            </label>
            <select v-model="studyFocusFilter" :disabled="viewMode === 'trash'">
              <option value="all">全部状态</option>
              <option value="needs-data">需导入数据</option>
              <option value="needs-pipeline">需配置工作流</option>
              <option value="running">运行进行中</option>
              <option value="ready">可继续处理</option>
            </select>
          </div>

          <div v-if="loading" class="study-empty">
            正在同步研究项...
          </div>

          <div v-else-if="!visibleStudies.length" class="study-empty">
            <strong>{{ emptyTitle }}</strong>
            <span>{{ emptyDescription }}</span>
          </div>

          <div v-else class="study-list">
            <div
              v-for="study in visibleStudies"
              :key="study.id"
              class="study-row"
              :class="{ 'is-active': selectedStudyId === study.id }"
              @click="selectStudy(study.id)"
            >
              <span class="study-row__top">
                <span class="study-row__title">
                  <strong>{{ study.name }}</strong>
                  <small v-if="study.code">{{ study.code }}</small>
                </span>
                <span class="status-pill" :class="statusPillClass(study.status)">
                  {{ statusLabel(study.status) }}
                </span>
              </span>
              <span class="study-row__desc">{{ study.description || '暂无描述' }}</span>
              <span class="study-row__meta">
                <span>角色 {{ ownerRoleLabel(study) }}</span>
                <span>{{ recentActivityLabel(study) }}</span>
              </span>
              <span
                v-if="viewMode === 'active' && summaryFor(study.id).mounts !== null"
                class="study-row__mounts"
                :title="(summaryFor(study.id).mounts ?? []).map(mountAssetLabel).join('、')"
              >
                <template v-if="!mountPreviewList(summaryFor(study.id)).length">
                  <span class="mount-tag mount-tag--empty">未挂载数据集</span>
                </template>
                <template v-else>
                  <span
                    v-for="mount in mountPreviewList(summaryFor(study.id))"
                    :key="mount.id"
                    class="mount-tag"
                    :class="{ 'mount-tag--upgradable': isMountUpgradable(mount) }"
                    :title="mountTooltip(mount)"
                  >
                    {{ mountAssetLabel(mount) }}<span v-if="mount.dataset_version" class="mount-tag__version">@{{ mount.dataset_version.version_label }}</span>
                    <span v-if="isMountUpgradable(mount)" class="mount-upgrade-marker" aria-label="有新版本可升级">⇡</span>
                  </span>
                  <span v-if="mountOverflowCount(summaryFor(study.id)) > 0" class="mount-tag mount-tag--more">
                    +{{ mountOverflowCount(summaryFor(study.id)) }}
                  </span>
                </template>
              </span>
              <span v-if="viewMode === 'active'" class="study-row__signals">
                <span :class="signalClass(summaryFor(study.id).recordingCount)">
                  数据 {{ compactCount(summaryFor(study.id).recordingCount) }}
                </span>
                <span :class="signalClass(summaryFor(study.id).pipelineCount)">
                  工作流 {{ compactCount(summaryFor(study.id).pipelineCount) }}
                </span>
                <span :class="{ active: (summaryFor(study.id).runningExecutionCount ?? 0) > 0 }">
                  运行 {{ compactCount(summaryFor(study.id).executionCount) }}
                </span>
              </span>
              <span v-else class="study-row__signals">
                <span class="danger">已删除</span>
                <span>{{ trashedLabel(study) }}</span>
              </span>
            </div>
          </div>
        </aside>

        <main class="study-detail-panel" aria-label="研究项详情">
          <div v-if="!selectedStudy" class="study-empty study-empty--detail">
            <strong>选择一个研究项查看概况</strong>
            <span>左侧目录用于挑选研究项，右侧铺开它的数据 / 工作流 / 结果概况，点「进入工作区」开干。</span>
          </div>

          <template v-else-if="viewMode === 'active'">
            <div class="study-detail__head">
              <div>
                <h2>{{ selectedStudy.name }}</h2>
                <div class="study-badges">
                  <span v-if="selectedStudy.code">{{ selectedStudy.code }}</span>
                  <span class="status-pill" :class="statusPillClass(selectedStudy.status)">
                    {{ statusLabel(selectedStudy.status) }}
                  </span>
                </div>
              </div>
              <div class="study-detail__actions">
                <RouterLink class="btn btn--primary" :to="`/studies/${selectedStudy.id}/pipeline`">
                  <AppIcon name="pipeline" :size="16" />
                  进入工作区
                </RouterLink>
                <button class="btn btn--ghost danger-text" type="button" @click="openActionModal(selectedStudy, 'trash')">
                  移入回收站
                </button>
              </div>
            </div>
            <StudyOverviewTab :study-id="selectedStudy.id" />
          </template>

          <template v-else>
            <div class="study-detail__head">
              <div>
                <h2>{{ selectedStudy.name }}</h2>
                <div class="study-badges">
                  <span class="status-pill status-pill--danger">已删除</span>
                </div>
              </div>
              <div class="study-detail__actions">
                <button class="btn btn--ghost" type="button" @click="openActionModal(selectedStudy, 'restore')">恢复</button>
                <button class="btn btn--danger" type="button" @click="openActionModal(selectedStudy, 'purge')">永久删除</button>
              </div>
            </div>
            <p class="study-description">已移入回收站。恢复后回到活跃研究项；永久删除前请确认数据和审计要求。</p>
          </template>
        </main>
      </section>
    </div>

    <div v-if="showCreateModal" class="modal-backdrop" role="presentation" @click.self="closeCreateModal">
      <form class="modal-card study-modal" @submit.prevent="handleCreateStudy">
        <header>
          <div>
            <p class="eyebrow">新建研究项</p>
            <h2>创建研究项工作空间</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeCreateModal">x</button>
        </header>
        <div class="form-grid">
          <label>
            <span>研究项名称</span>
            <input v-model.trim="createForm.name" required maxlength="160" placeholder="例如 静息态 EEG 分析" />
          </label>
          <label>
            <span>研究项短码</span>
            <input
              v-model.trim="createForm.code"
              maxlength="64"
              placeholder="resting-eeg"
              pattern="[A-Za-z0-9_-]+"
              :class="{ 'has-error': codeFieldError }"
              @input="codeFieldError = ''"
            />
            <small class="field-hint" :class="{ 'is-error': codeFieldError }">
              {{ codeFieldError || '只能用字母、数字、短横线、下划线；留空则按名称自动生成' }}
            </small>
          </label>
        </div>
        <label>
          <span>描述</span>
          <textarea v-model.trim="createForm.description" rows="4" placeholder="研究目标、样本范围或协作说明" />
        </label>
        <div class="form-grid form-grid--single">
          <label>
            <span>存储配额（GB）</span>
            <input v-model.number="createForm.storage_quota_gb" type="number" min="1" step="1" placeholder="默认 100" />
          </label>
        </div>
        <p class="modal-hint">研究项 ID 会自动生成；普通列表默认不展示技术 ID。</p>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeCreateModal">取消</button>
          <button class="btn btn--primary" type="submit" :disabled="studySaving">
            {{ studySaving ? '创建中...' : '创建研究项' }}
          </button>
        </footer>
      </form>
    </div>

    <div v-if="actionModal.study" class="modal-backdrop" role="presentation" @click.self="closeActionModal">
      <form class="modal-card study-modal" @submit.prevent="handleStudyAction">
        <header>
          <div>
            <p class="eyebrow">研究项治理</p>
            <h2>{{ actionTitle }}</h2>
          </div>
          <button class="icon-button" type="button" aria-label="关闭" @click="closeActionModal">x</button>
        </header>
        <p class="modal-copy">
          {{ actionDescription }}
        </p>
        <label v-if="actionModal.action === 'trash'">
          <span>删除原因</span>
          <textarea v-model.trim="actionModal.reason" rows="3" placeholder="可选，用于审计记录" />
        </label>
        <label v-if="actionModal.action === 'purge'">
          <span>请输入研究项 ID 确认永久删除</span>
          <input v-model.trim="actionModal.confirmation" :placeholder="actionModal.study.id" />
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeActionModal">取消</button>
          <button class="btn" :class="actionButtonClass" type="submit" :disabled="actionLoading">
            {{ actionLoading ? '处理中...' : actionButtonText }}
          </button>
        </footer>
      </form>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import StudyOverviewTab from './study/StudyOverviewTab.vue'
import WorkbenchShell from '../components/WorkbenchShell.vue'
import { datasetApi } from '../api/datasets'
import { studyDatasetMountApi } from '../api/datasetAssets'
import { pipelineApi } from '../api/pipelines'
import { studyApi } from '../api/studies'
import { useAuthStore } from '../stores/auth'
import type { CreateStudyRequest, Pipeline, PipelineExecution, Study, StudyDatasetMount, StudyMember } from '../types'

type StudyViewMode = 'active' | 'trash'
type StudyAction = 'trash' | 'restore' | 'purge'
type StudyFocusFilter = 'all' | 'needs-data' | 'needs-pipeline' | 'running' | 'ready'

interface StudySummary {
  loaded: boolean
  loading: boolean
  recordingCount: number | null
  pipelineCount: number | null
  executionCount: number | null
  runningExecutionCount: number | null
  memberCount: number | null
  memberRole: string | null
  canRun: boolean | null
  latestExecution: PipelineExecution | null
  latestActivityAt: string | null
  mounts: StudyDatasetMount[] | null
  pipelines: Pipeline[]
  executions: PipelineExecution[]
}

const SUMMARY_LIMIT = 12
const EXECUTION_PIPELINE_LIMIT = 3

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const studies = ref<Study[]>([])
const selectedStudyId = ref('')
const trashedStudies = ref<Study[]>([])
const summaries = reactive<Record<string, StudySummary>>({})
const loading = ref(false)
const actionLoading = ref(false)
const studySaving = ref(false)
const error = ref('')
const successMessage = ref('')
const summaryWarnings = ref<string[]>([])
const viewMode = ref<StudyViewMode>('active')
const studySearch = ref('')
const studyFocusFilter = ref<StudyFocusFilter>('all')
const showCreateModal = ref(false)

const createForm = reactive({
  name: '',
  code: '',
  description: '',
  storage_quota_gb: null as number | null,
})

const STUDY_CODE_PATTERN = /^[A-Za-z0-9_-]+$/
const codeFieldError = ref('')

const actionModal = reactive<{
  study: Study | null
  action: StudyAction
  reason: string
  confirmation: string
}>({
  study: null,
  action: 'trash',
  reason: '',
  confirmation: '',
})

const isAdmin = computed(() => auth.user?.roles?.includes('admin') ?? false)
const canCreateStudy = computed(() => isAdmin.value || (auth.user?.roles?.includes('pi') ?? false))
const activeStudies = computed(() => studies.value.filter((study) => study.status !== 'archived'))
const baseStudies = computed(() => (viewMode.value === 'trash' ? trashedStudies.value : studies.value))
const baseStudyCount = computed(() => baseStudies.value.length)

const visibleStudies = computed(() => {
  const keyword = studySearch.value.trim().toLowerCase()
  return baseStudies.value.filter((study) => {
    if (keyword) {
      const haystack = `${study.name} ${study.code ?? ''} ${study.description ?? ''}`.toLowerCase()
      if (!haystack.includes(keyword)) return false
    }
    if (viewMode.value === 'trash' || studyFocusFilter.value === 'all') return true
    const summary = summaryFor(study.id)
    if (!summary.loaded) return true
    if (studyFocusFilter.value === 'needs-data') return (summary.recordingCount ?? 0) === 0
    if (studyFocusFilter.value === 'needs-pipeline') {
      return (summary.recordingCount ?? 0) > 0 && (summary.pipelineCount ?? 0) === 0
    }
    if (studyFocusFilter.value === 'running') return (summary.runningExecutionCount ?? 0) > 0
    if (studyFocusFilter.value === 'ready') {
      return (summary.recordingCount ?? 0) > 0 && (summary.pipelineCount ?? 0) > 0
    }
    return true
  })
})

const selectedStudy = computed(() => visibleStudies.value.find((s) => s.id === selectedStudyId.value) ?? null)

function selectStudy(id: string) {
  selectedStudyId.value = id
  void router.replace({ query: { ...route.query, study: id } })
}

// 选中项不在当前可见列表里时，优先取 URL ?study=，否则落到第一个
function ensureSelectedStudy() {
  if (selectedStudyId.value && visibleStudies.value.some((s) => s.id === selectedStudyId.value)) return
  const fromQuery = typeof route.query.study === 'string' ? route.query.study : ''
  if (fromQuery && visibleStudies.value.some((s) => s.id === fromQuery)) {
    selectedStudyId.value = fromQuery
    return
  }
  selectedStudyId.value = visibleStudies.value[0]?.id ?? ''
}

const readyStudyCount = computed(() =>
  studies.value.filter((study) => {
    const summary = summaries[study.id]
    return summary?.loaded && (summary.recordingCount ?? 0) > 0 && (summary.pipelineCount ?? 0) > 0
  }).length,
)

const needsDataCount = computed(() =>
  studies.value.filter((study) => {
    const summary = summaries[study.id]
    return summary?.loaded && (summary.recordingCount ?? 0) === 0
  }).length,
)

const runningStudyCount = computed(() =>
  studies.value.reduce((total, study) => total + (summaries[study.id]?.runningExecutionCount ?? 0), 0),
)

const emptyTitle = computed(() => {
  if (viewMode.value === 'trash') return '回收站为空'
  if (studySearch.value || studyFocusFilter.value !== 'all') return '没有匹配的 Study'
  return '还没有 Study'
})

const emptyDescription = computed(() => {
  if (viewMode.value === 'trash') return '删除后的 Study 会出现在这里，便于恢复或治理。'
  if (studySearch.value || studyFocusFilter.value !== 'all') return '调整搜索或状态筛选后再查看。'
  return canCreateStudy.value ? '可以先创建一个研究项工作空间。' : '请联系 PI 或管理员创建研究项。'
})

const actionTitle = computed(() => {
  if (actionModal.action === 'trash') return '移入回收站'
  if (actionModal.action === 'restore') return '恢复 Study'
  return '永久删除 Study'
})

const actionDescription = computed(() => {
  if (!actionModal.study) return ''
  if (actionModal.action === 'trash') {
    return `将「${actionModal.study.name}」移入回收站后，普通列表不再展示，但仍可恢复。`
  }
  if (actionModal.action === 'restore') {
    return `恢复「${actionModal.study.name}」后，它会重新回到活跃研究项。`
  }
  return `永久删除「${actionModal.study.name}」会清理 Study 记录和关联治理状态，此操作不可撤销。`
})

const actionButtonText = computed(() => {
  if (actionModal.action === 'trash') return '移入回收站'
  if (actionModal.action === 'restore') return '恢复'
  return '永久删除'
})

const actionButtonClass = computed(() => (actionModal.action === 'purge' ? 'btn--danger' : 'btn--primary'))

onMounted(() => {
  void loadStudies()
})

watch([viewMode, studySearch, studyFocusFilter], () => {
  ensureSelectedStudy()
  void loadVisibleSummaries()
})

async function loadStudies() {
  loading.value = true
  error.value = ''
  summaryWarnings.value = []
  try {
    const [activeRes, trashRes] = await Promise.all([
      studyApi.list(),
      studyApi.listTrash().catch(() => null),
    ])
    studies.value = activeRes.data.studies
    trashedStudies.value = trashRes?.data.studies ?? []
    Object.keys(summaries).forEach((key) => delete summaries[key])
    ensureSelectedStudy()
    await loadVisibleSummaries()
  } catch (err) {
    error.value = friendlyError(err, '研究项列表加载失败')
  } finally {
    loading.value = false
  }
}

function switchView(mode: StudyViewMode) {
  viewMode.value = mode
  if (mode === 'trash') {
    studyFocusFilter.value = 'all'
  }
}

async function loadVisibleSummaries() {
  if (viewMode.value !== 'active') return
  const targets = visibleStudies.value.slice(0, SUMMARY_LIMIT)
  summaryWarnings.value = []
  if (visibleStudies.value.length > SUMMARY_LIMIT) {
    summaryWarnings.value.push(`当前仅同步前 ${SUMMARY_LIMIT} 个 Study 的处理摘要，可通过搜索快速定位。`)
  }
  await Promise.all(targets.map((study) => loadStudySummary(study)))
}

async function loadStudySummary(study: Study) {
  if (viewMode.value !== 'active') return
  const existing = summaries[study.id]
  if (existing?.loaded || existing?.loading) return
  summaries[study.id] = {
    ...makeEmptySummary(),
    loading: true,
  }
  try {
    const [datasetsRes, pipelinesRes, membersRes, mountsRes] = await Promise.all([
      datasetApi.list(study.id).catch(() => null),
      pipelineApi.list(study.id).catch(() => null),
      studyApi.listMembers(study.id).catch(() => null),
      studyDatasetMountApi.list(study.id).catch(() => null),
    ])

    const pipelines = pipelinesRes?.data.pipelines ?? []
    const executionResponses = await Promise.all(
      pipelines.slice(0, EXECUTION_PIPELINE_LIMIT).map((pipeline) => pipelineApi.listExecutions(study.id, pipeline.id, 5).catch(() => null)),
    )
    const executions = executionResponses.flatMap((res) => res?.data.executions ?? [])
    const runningExecutions = executions.filter((execution) => ['pending', 'running'].includes(execution.status)).length
    const latestExecution = executions
      .slice()
      .sort((a, b) => new Date(b.started_at ?? 0).getTime() - new Date(a.started_at ?? 0).getTime())[0] ?? null
    const members = membersRes?.data.members ?? []
    const currentMember = findCurrentMember(members, study)
    const candidateDates = [study.updated_at, latestExecution?.started_at, latestExecution?.finished_at].filter(
      Boolean,
    ) as string[]

    summaries[study.id] = {
      loaded: true,
      loading: false,
      recordingCount: datasetsRes?.data.recordings.length ?? null,
      pipelineCount: pipelines.length,
      executionCount: executions.length,
      runningExecutionCount: runningExecutions,
      memberCount: membersRes ? members.length : null,
      memberRole: currentMember?.role ?? (study.owner_id === auth.user?.id ? 'owner' : null),
      canRun: currentMember?.can_run ?? null,
      latestExecution,
      latestActivityAt: candidateDates.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null,
      mounts: mountsRes ? mountsRes.data.mounts.filter((mount) => mount.is_active) : null,
      pipelines,
      executions: executions
        .slice()
        .sort((a, b) => new Date(b.started_at ?? 0).getTime() - new Date(a.started_at ?? 0).getTime()),
    }
  } catch (err) {
    summaries[study.id] = {
      ...makeEmptySummary(),
      loaded: true,
      loading: false,
    }
    summaryWarnings.value.push(`「${study.name}」的处理摘要同步失败：${err instanceof Error ? err.message : '未知错误'}`)
  }
}

function findCurrentMember(members: StudyMember[], study: Study) {
  const userId = auth.user?.id
  if (!userId) return null
  return members.find((member) => member.user_id === userId) ?? (study.owner_id === userId ? ({ role: 'owner' } as StudyMember) : null)
}

function makeEmptySummary(): StudySummary {
  return {
    loaded: false,
    loading: false,
    recordingCount: null,
    pipelineCount: null,
    executionCount: null,
    runningExecutionCount: null,
    memberCount: null,
    memberRole: null,
    canRun: null,
    latestExecution: null,
    latestActivityAt: null,
    mounts: null,
    pipelines: [],
    executions: [],
  }
}

function summaryFor(studyId: string): StudySummary {
  return summaries[studyId] ?? makeEmptySummary()
}

const MOUNT_PREVIEW_LIMIT = 3

function mountAssetLabel(mount: StudyDatasetMount): string {
  return mount.dataset_asset?.name || mount.mount_name || '未命名 Asset'
}

function mountPreviewList(summary: StudySummary): StudyDatasetMount[] {
  if (!summary.mounts || !summary.mounts.length) return []
  return summary.mounts.slice(0, MOUNT_PREVIEW_LIMIT)
}

function mountOverflowCount(summary: StudySummary): number {
  if (!summary.mounts) return 0
  return Math.max(0, summary.mounts.length - MOUNT_PREVIEW_LIMIT)
}

// Phase 3 (docs_v2/3-25) C: mount 锁定的版本不是 Asset 当前默认版本 → 可升级
function isMountUpgradable(mount: StudyDatasetMount): boolean {
  const lockedVersion = mount.dataset_version_id
  const assetCurrent = mount.dataset_asset?.current_version_id
  if (!lockedVersion || !assetCurrent) return false
  return lockedVersion !== assetCurrent
}

function mountTooltip(mount: StudyDatasetMount): string {
  const name = mountAssetLabel(mount)
  const version = mount.dataset_version?.version_label
  if (!version) return name
  if (isMountUpgradable(mount)) return `${name} @ ${version} (有新版本可升级)`
  return `${name} @ ${version}`
}

function compactCount(value: number | null) {
  if (value === null || value === undefined) return '待同步'
  return String(value)
}

function signalClass(value: number | null) {
  return {
    muted: value === null || value === undefined,
    ready: typeof value === 'number' && value > 0,
    warning: value === 0,
  }
}

function recentActivityLabel(study: Study) {
  const summary = summaries[study.id]
  const value = summary?.latestActivityAt ?? study.updated_at ?? study.created_at
  return `最近 ${formatDateTime(value)}`
}

function trashedLabel(study: Study) {
  return study.deleted_at ? `删除于 ${formatDateTime(study.deleted_at)}` : '已进入回收站'
}

function statusLabel(status: Study['status'] | string) {
  if (status === 'active') return '活跃'
  if (status === 'archived') return '已归档'
  if (status === 'trashed') return '回收站'
  return status || '未知'
}

function statusPillClass(status: Study['status'] | string) {
  return {
    'status-pill--success': status === 'active',
    'status-pill--muted': status === 'archived',
    'status-pill--danger': status === 'trashed',
  }
}

function roleLabel(role?: string | null) {
  if (!role) return '未同步'
  if (role === 'owner') return '负责人'
  if (role === 'admin') return '管理员'
  if (role === 'editor') return '编辑'
  if (role === 'viewer') return '查看'
  if (role === 'pi') return 'PI'
  return role
}

function ownerRoleLabel(study: Study) {
  const summary = summaries[study.id]
  if (summary?.memberRole) return roleLabel(summary.memberRole)
  if (study.owner_id === auth.user?.id) return '负责人'
  return '待同步'
}

function friendlyError(err: unknown, fallback: string) {
  // 优先读取后端 detail（FastAPI 校验错误统一在 main.py 的 RequestValidationError handler 中拼成字符串）
  const response = (err as { response?: { data?: { detail?: unknown } } })?.response
  const detail = response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return `${fallback}：${detail}`
  }
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string } | string
    const msg = typeof first === 'string' ? first : first?.msg
    if (msg) return `${fallback}：${msg}`
  }
  const message = err instanceof Error ? err.message : ''
  if (/status code \d{3}/i.test(message)) return `${fallback}：接口暂时不可用，请确认后端服务或 mock API 已开启。`
  return message || fallback
}

function formatDateTime(value?: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function openCreateModal() {
  resetCreateForm()
  showCreateModal.value = true
}

function closeCreateModal() {
  if (studySaving.value) return
  showCreateModal.value = false
}

function resetCreateForm() {
  createForm.name = ''
  createForm.code = ''
  createForm.description = ''
  createForm.storage_quota_gb = null
  codeFieldError.value = ''
}

async function handleCreateStudy() {
  if (createForm.code && !STUDY_CODE_PATTERN.test(createForm.code)) {
    codeFieldError.value = '短码只能包含字母、数字、短横线、下划线'
    return
  }
  codeFieldError.value = ''
  studySaving.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const payload: CreateStudyRequest = {
      name: createForm.name,
      code: createForm.code || createForm.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || `study-${Date.now()}`,
      description: createForm.description || undefined,
      storage_quota_gb: createForm.storage_quota_gb || 100,
    }
    const res = await studyApi.create(payload)
    const createdStudy = res.data
    successMessage.value = `Study 已创建：${createdStudy.name}`
    showCreateModal.value = false
    await loadStudies()
  } catch (err) {
    error.value = friendlyError(err, '研究项创建失败')
  } finally {
    studySaving.value = false
  }
}

function openActionModal(study: Study, action: StudyAction) {
  actionModal.study = study
  actionModal.action = action
  actionModal.reason = ''
  actionModal.confirmation = ''
}

function closeActionModal() {
  if (actionLoading.value) return
  actionModal.study = null
  actionModal.reason = ''
  actionModal.confirmation = ''
}

async function handleStudyAction() {
  if (!actionModal.study) return
  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    let message = ''
    if (actionModal.action === 'trash') {
      const res = await studyApi.trash(actionModal.study.id, actionModal.reason || undefined)
      message = res.data.message
    } else if (actionModal.action === 'restore') {
      const res = await studyApi.restore(actionModal.study.id)
      message = res.data.message
    } else {
      const confirmation = actionModal.confirmation || actionModal.study.id
      const res = await studyApi.purge(actionModal.study.id, confirmation)
      message = res.data.message
    }
    successMessage.value = message || '操作已完成'
    closeActionModal()
    await loadStudies()
  } catch (err) {
    error.value = friendlyError(err, '研究项操作失败')
  } finally {
    actionLoading.value = false
  }
}
</script>

<style scoped>
/* 注意: WorkbenchShell 的 .page 已有 padding (var(--s-5) var(--s-6))，这里不要再加 padding，否则顶部出现双倍空白 */
.studies-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--c-text);
}

/* 页头复用全局 .page__header/.page__title/.page__subtitle,这里只抵消 margin-bottom
   避免和 .studies-page 的 flex gap 叠加 */
.studies-page__header {
  margin-bottom: 0;
}

.study-list-panel__head h2 {
  margin: 0;
  color: var(--c-text);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--c-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.studies-page__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

/* 让 .page-stat-strip 在外层容器里有完整宽度撑开，否则它会塌缩成 1 列 */
.study-overview-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 16px;
}
@media (max-width: 760px) {
  .study-overview-bar {
    grid-template-columns: 1fr;
  }
}

/* .study-summary-strip / .study-stat 已替换为通用 .page-stat-strip / .page-stat（见 style.css） */

.study-tabs {
  display: inline-flex;
  flex: 0 0 auto;
  align-self: center;
  overflow: hidden;
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
}

.study-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 10px 16px;
  color: var(--c-text-2);
  font-weight: 700;
  cursor: pointer;
}

.study-tabs button.active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.study-tabs span {
  color: inherit;
  opacity: 0.8;
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

.alert--warning {
  border: 1px solid var(--c-warning-soft);
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.alert--success {
  border: 1px solid var(--c-success-soft);
  background: var(--c-success-soft);
  color: var(--c-success);
}

.study-workbench {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  min-height: 560px;
  overflow: hidden;
  border: 1px solid #dfe7f3;
  border-radius: 8px;
  background: #fff;
}
@media (max-width: 860px) {
  .study-workbench {
    grid-template-columns: 1fr;
  }
}

.study-list-panel {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 14px;
  border-right: 1px solid #e5ecf5;
  /* 左侧研究项列表面板用白色，与灰色页面背景(--c-bg-soft)拉开；与右侧详情靠 border-right 分隔 */
  background: var(--c-surface);
  padding: 18px;
}

.study-list-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.study-list-panel__head h2 {
  font-size: 18px;
}

.study-list-panel__head p {
  margin: 6px 0 0;
  color: var(--c-text-3);
  font-size: 13px;
}

.study-list-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.study-search {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: #fff;
  padding: 0 12px;
  color: var(--c-text-3);
}

.study-search input,
.study-list-toolbar select {
  width: 100%;
  min-width: 0;
  border: 0;
  background: #fff;
  color: var(--c-text);
  font: inherit;
  outline: none;
}

.study-search input {
  height: 38px;
}

.study-list-toolbar select {
  height: 38px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 0 10px;
}

.study-list {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
  padding-right: 2px;
}

/* 列表项 = 可点选卡片（master-detail：点选不跳页，is-active 高亮） */
.study-row {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  gap: 9px;
  border: 1px solid #dfe7f3;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.study-row:hover {
  border-color: #8fb2ff;
  box-shadow: 0 8px 20px rgb(47 109 246 / 10%);
}

.study-row.is-active {
  border-color: #2f6df6;
  background: #f4f8ff;
  box-shadow: 0 8px 20px rgb(47 109 246 / 12%);
}

/* 右栏：选中研究项的概览工作台 */
.study-detail-panel {
  min-width: 0;
  padding: 24px;
  overflow: auto;
}

.study-empty--detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  text-align: center;
  color: var(--c-text-3);
}

.study-empty--detail strong {
  color: var(--c-text-2);
  font-size: 15px;
}

.study-detail__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.study-detail__head h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.3;
  color: var(--c-text);
  overflow-wrap: anywhere;
}

.study-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.study-badges > span:not(.status-pill) {
  border-radius: 999px;
  background: var(--c-bg-tint);
  padding: 5px 9px;
  color: var(--c-text-2);
  font-size: 12px;
  font-weight: 700;
}

.study-detail__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.study-description {
  margin: 0;
  color: var(--c-text-2);
  line-height: 1.7;
}

.study-row__top,
.study-row__meta,
.study-row__signals {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.study-row__top {
  justify-content: space-between;
}

.study-row__title {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.study-row__title strong,
.study-row__title small,
.study-row__desc,
.study-row__meta span,
.study-row__signals span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.study-row__title strong {
  color: var(--c-text);
  font-size: 15px;
}

.study-row__title small,
.study-row__desc,
.study-row__meta {
  color: var(--c-text-3);
  font-size: 12px;
}

.study-row__desc {
  display: block;
}

.study-row__meta,
.study-row__signals {
  justify-content: space-between;
}

.study-row__signals span {
  min-width: 0;
  border-radius: 6px;
  background: var(--c-bg-tint);
  padding: 4px 7px;
  color: var(--c-text-2);
  font-size: 12px;
  font-weight: 700;
}

.study-row__signals .ready {
  background: var(--c-success-soft);
  color: var(--c-success);
}

.study-row__signals .warning {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.study-row__signals .active {
  background: var(--c-primary-soft);
  color: var(--c-primary);
}

.study-row__signals .danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.study-row__mounts {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: -2px;
}

.mount-tag {
  display: inline-flex;
  max-width: 160px;
  align-items: center;
  border: 1px solid #d8e3f5;
  border-radius: 6px;
  background: #f5f8ff;
  padding: 3px 8px;
  color: #3358c6;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mount-tag--more {
  background: var(--c-bg-tint);
  color: var(--c-text-2);
}

.mount-tag--empty {
  border-color: #f0d6a8;
  background: #fff7ea;
  color: var(--c-warning);
  font-weight: 600;
}

/* Phase 3 (docs_v2/3-25) C: 可升级提示 */
.mount-tag--upgradable {
  border-color: #f0c674;
  background: #fff7e6;
}
.mount-tag__version {
  margin-left: 4px;
  opacity: 0.7;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 500;
}
.mount-upgrade-marker {
  margin-left: 4px;
  color: var(--c-warning);
  font-weight: 700;
}

.status-pill {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--c-bg-tint);
  padding: 4px 8px;
  color: var(--c-text-2);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill--success {
  background: #e8fff2;
  color: var(--c-success);
}

.status-pill--danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.status-pill--muted {
  background: var(--c-bg-tint);
  color: var(--c-text-2);
}

.status-pill--warn {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 36px;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0 14px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn--primary {
  background: var(--c-primary);
  color: #fff;
  box-shadow: 0 10px 20px rgb(47 109 246 / 18%);
}

.btn--ghost {
  border-color: var(--c-border);
  background: #fff;
  color: var(--c-text-2);
}

.btn--danger {
  background: var(--c-danger);
  color: #fff;
}

.danger-text {
  color: var(--c-danger);
}

.study-empty {
  display: flex;
  min-height: 160px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px dashed var(--c-border-2);
  border-radius: 8px;
  background: #fff;
  padding: 24px;
  color: var(--c-text-3);
  text-align: center;
}

.study-empty strong {
  color: var(--c-text);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(15 23 42 / 45%);
  padding: 24px;
}

.modal-card {
  width: min(640px, 100%);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 80px rgb(15 23 42 / 25%);
}

.study-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
}

.study-modal header,
.study-modal footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.study-modal h2 {
  margin: 0;
  color: var(--c-text);
}

.icon-button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  background: #fff;
  color: var(--c-text-2);
  cursor: pointer;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid--single {
  grid-template-columns: minmax(0, 1fr);
}

.study-modal label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: var(--c-text-2);
  font-weight: 700;
}

.study-modal input,
.study-modal textarea,
.study-modal select {
  width: 100%;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--c-text);
  font: inherit;
  outline: none;
}

.study-modal textarea {
  resize: vertical;
}

.study-modal input.has-error,
.study-modal textarea.has-error {
  border-color: #fca5a5;
  background: #fffafa;
}

.field-hint {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 400;
}

.field-hint.is-error {
  color: var(--c-danger);
}

.modal-hint,
.modal-copy {
  margin: 0;
  color: var(--c-text-2);
  line-height: 1.6;
}

@media (max-width: 760px) {
  .studies-page {
    padding: 16px;
  }

  .studies-page__header {
    flex-direction: column;
    align-items: stretch;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .studies-page__actions {
    width: 100%;
  }

  .studies-page__actions .btn {
    flex: 1;
  }
}
</style>
