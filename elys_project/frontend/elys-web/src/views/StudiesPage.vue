<template>
  <!-- 版心对齐主页 .hero__inner(1200)：与 Dashboard/Datasets 同款，--content-w=1200 + --page-pad-x=0。仅本页生效。 -->
  <WorkbenchShell active-key="studies" active-top-key="studies" :show-sidebar="false" :narrow="true" :style="{ '--content-w': '1200px', '--page-pad-x': '0px' }">
    <div class="studies-page">
      <PageHeader
        flush
        title="研究项"
        subtitle="把数据、分析流程和结果按项目集中管理，并一眼看出每个项目下一步能做什么。"
      >
        <template #actions>
          <button class="btn btn--ghost" type="button" :disabled="loading" @click="loadStudies">
            <AppIcon name="refresh" :size="16" />
            刷新
          </button>
          <button v-if="canCreateStudy" class="btn btn--primary" type="button" @click="openCreateModal">
            <AppIcon name="plus" :size="16" />
            新建研究项
          </button>
        </template>
      </PageHeader>

      <div v-if="error" class="alert alert--danger">
        <AppIcon class="alert__icon" name="alert" :size="18" />
        <div class="alert__body">{{ error }}</div>
      </div>
      <div v-if="summaryWarnings.length" class="alert alert--warning">
        <AppIcon class="alert__icon" name="alert" :size="18" />
        <div class="alert__body">{{ summaryWarnings.join('；') }}</div>
      </div>
      <div v-if="successMessage" class="alert alert--success">
        <AppIcon class="alert__icon" name="check" :size="18" />
        <div class="alert__body">{{ successMessage }}</div>
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
              <input v-model.trim="studySearch" type="search" placeholder="按名称或描述搜索" />
            </label>
            <select :value="listFilterValue" @change="onListFilterChange">
              <option value="all">全部状态</option>
              <option value="needs-data">需导入数据</option>
              <option value="needs-pipeline">需配置工作流</option>
              <option value="running">运行进行中</option>
              <option value="ready">可继续处理</option>
              <option value="trash">回收站{{ trashedStudies.length ? '（' + trashedStudies.length + '）' : '' }}</option>
            </select>
          </div>

          <EmptyState v-if="loading" title="正在同步研究项…" compact />

          <EmptyState
            v-else-if="!visibleStudies.length"
            :title="emptyTitle"
            :description="emptyDescription"
            compact
          />

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
                <!-- 列表里「活跃」条条都有=噪音；仅非活跃(归档/回收站)显示状态药丸，与 Dashboard 一致 -->
                <StatusPill
                  v-if="study.status !== 'active'"
                  :tone="studyStatusTone(study.status)"
                  :label="studyStatusLabel(study.status)"
                />
              </span>
              <span class="study-row__desc">{{ study.description || '暂无描述' }}</span>
              <span class="study-row__meta">
                <span>角色 {{ ownerRoleLabel(study) }}</span>
                <span>{{ recentActivityLabel(study) }}</span>
              </span>
              <span v-if="viewMode === 'active'" class="study-row__stage">
                <StatusPill :tone="stageResultFor(study.id).tone" :label="stageResultFor(study.id).label" />
              </span>
              <span v-else class="study-row__signals">
                <span class="danger">已删除</span>
                <span>{{ trashedLabel(study) }}</span>
              </span>
            </div>
          </div>
        </aside>

        <main class="study-detail-panel" aria-label="研究项详情">
          <EmptyState
            v-if="!selectedStudy"
            title="选择一个研究项查看概况"
            description="左侧目录用于挑选研究项，右侧铺开它的数据 / 工作流 / 结果概况，点「进入工作区」开干。"
          />

          <template v-else-if="viewMode === 'active'">
            <div class="study-detail__head">
              <div>
                <h2>{{ selectedStudy.name }}</h2>
                <div class="study-badges">
                  <span v-if="selectedStudy.code">{{ selectedStudy.code }}</span>
                  <StatusPill :tone="studyStatusTone(selectedStudy.status)" :label="studyStatusLabel(selectedStudy.status)" />
                </div>
              </div>
              <div class="study-detail__actions">
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
                  <StatusPill tone="danger" label="已删除" />
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

    <Modal v-if="showCreateModal" @close="closeCreateModal">
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
        <details class="study-advanced">
          <summary>高级设置</summary>
          <div class="form-grid form-grid--single">
            <label>
              <span>存储配额（GB）</span>
              <input v-model.number="createForm.storage_quota_gb" type="number" min="1" step="1" placeholder="默认 100" />
              <small class="field-hint">留空按默认 100 GB；通常不用改。</small>
            </label>
          </div>
        </details>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeCreateModal">取消</button>
          <button class="btn btn--primary" type="submit" :disabled="studySaving">
            {{ studySaving ? '创建中...' : '创建研究项' }}
          </button>
        </footer>
      </form>
    </Modal>

    <Modal v-if="actionModal.study" @close="closeActionModal">
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
          <span>请输入研究项名称「{{ actionModal.study.name }}」确认永久删除</span>
          <input v-model.trim="actionModal.confirmation" :placeholder="actionModal.study.name" />
        </label>
        <footer>
          <button class="btn btn--ghost" type="button" @click="closeActionModal">取消</button>
          <button
            class="btn"
            :class="actionButtonClass"
            type="submit"
            :disabled="actionLoading || (actionModal.action === 'purge' && !purgeConfirmed)"
          >
            {{ actionLoading ? '处理中...' : actionButtonText }}
          </button>
        </footer>
      </form>
    </Modal>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppIcon from '../components/AppIcon.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import Modal from '@/components/common/Modal.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StudyOverviewTab from './study/StudyOverviewTab.vue'
import WorkbenchShell from '../components/WorkbenchShell.vue'
import { studyApi } from '../api/studies'
import { useAuthStore } from '../stores/auth'
import { friendlyError } from '@/composables/common/errors'
import { formatDateTime } from '@/composables/common/formatters'
import { deriveStudyStage } from '@/composables/studies/studyStage'
import { studyRoleLabel, studyStatusLabel, studyStatusTone } from '@/composables/studies/studyFormatters'
import type { CreateStudyRequest, Pipeline, PipelineExecution, Study, StudyDatasetMount } from '../types'

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
    // 筛选项的取值与阶段枚举一一对应，直接比对收口后的阶段
    return stageResultFor(study.id).stage === studyFocusFilter.value
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

// 永久删除需输入研究项「名称」做人性化确认闸门（比照抄技术 ID 友好；后端仍要求传 ID，见 handleStudyAction）。
const purgeConfirmed = computed(
  () => !!actionModal.study && actionModal.confirmation.trim() === actionModal.study.name,
)

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
    // 各研究项概况后台异步加载，不阻塞列表渲染：列表拿到名称即显示，每行 stage 药丸先「同步中…」再回填。
    // （此前 await 在这里，整张列表要等所有 study 的 datasets/pipelines/executions 拉完才出来，故卡几秒。）
    void loadVisibleSummaries()
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

// 左栏下拉合并了「视图」与「状态筛选」：回收站是独立视图，其余值是活跃视图内的聚焦过滤
const listFilterValue = computed<StudyFocusFilter | 'trash'>(() =>
  viewMode.value === 'trash' ? 'trash' : studyFocusFilter.value,
)

function onListFilterChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value
  if (value === 'trash') {
    switchView('trash')
    return
  }
  if (viewMode.value === 'trash') viewMode.value = 'active'
  studyFocusFilter.value = value as StudyFocusFilter
}

async function loadVisibleSummaries() {
  if (viewMode.value !== 'active') return
  const targets = visibleStudies.value.slice(0, SUMMARY_LIMIT)
  summaryWarnings.value = []
  if (visibleStudies.value.length > SUMMARY_LIMIT) {
    summaryWarnings.value.push('研究项较多，已优先加载靠前项目的概况；用上方搜索可快速定位其余。')
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
    // 一次聚合请求替代原先每项 4+3 个并发请求（N+1）：后端 /summary 在库里一把算好计数与最近活动。
    const { data } = await studyApi.summary(study.id)
    const latestExec = data.executions[0] ?? null
    const candidateDates = [study.updated_at, latestExec?.started_at, latestExec?.finished_at].filter(
      Boolean,
    ) as string[]

    summaries[study.id] = {
      loaded: true,
      loading: false,
      recordingCount: data.counts.recordings,
      pipelineCount: data.counts.pipelines,
      executionCount: data.counts.executions,
      runningExecutionCount: data.running_execution_count,
      memberCount: data.counts.members,
      memberRole: data.member_role ?? (study.owner_id === auth.user?.id ? 'owner' : null),
      canRun: data.can_run,
      latestActivityAt: candidateDates.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null,
      mounts: data.mounts,
      // 左栏列表只消费上面那几项；下列富字段列表不展示，仅为满足类型置空（详情页另走 useStudySummary）。
      latestExecution: null,
      pipelines: [],
      executions: [],
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

// 左栏列表行只显示一个「阶段」药丸（阶段对临床用户比裸计数更直观）。
// 判定收口到 deriveStudyStage —— 与 Dashboard、右栏「建议下一步」同一份事实源。
function stageResultFor(studyId: string) {
  const s = summaryFor(studyId)
  return deriveStudyStage({
    loaded: s.loaded,
    recordingCount: s.recordingCount,
    pipelineCount: s.pipelineCount,
    executionCount: s.executionCount,
    runningExecutionCount: s.runningExecutionCount,
  })
}

function recentActivityLabel(study: Study) {
  const summary = summaries[study.id]
  const value = summary?.latestActivityAt ?? study.updated_at ?? study.created_at
  return `最近 ${formatDateTime(value)}`
}

function trashedLabel(study: Study) {
  return study.deleted_at ? `删除于 ${formatDateTime(study.deleted_at)}` : '已进入回收站'
}

function ownerRoleLabel(study: Study) {
  const summary = summaries[study.id]
  if (summary?.memberRole) return studyRoleLabel(summary.memberRole)
  if (study.owner_id === auth.user?.id) return '负责人'
  return '待同步'
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
  // 永久删除二次确认：输入名称必须与研究项名称完全一致
  if (actionModal.action === 'purge' && actionModal.confirmation.trim() !== actionModal.study.name) return
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
      // 后端要求 confirm == 研究项 ID（studies.py purge_study）；用户输入的名字仅作前端闸门，提交回传 ID。
      const res = await studyApi.purge(actionModal.study.id, actionModal.study.id)
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


/* 告警条用全局 .alert/.alert__icon/.alert__body；此处仅抵消全局 margin-bottom，避免与 .studies-page 的 flex gap 叠加 */
.studies-page .alert {
  margin-bottom: 0;
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

.study-row__signals .danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.study-row__stage {
  display: flex;
}


/* 按钮全部用全局 .btn/.btn--primary/--ghost/--danger（删本地重定义，消除与全局漂移） */
.danger-text {
  color: var(--c-danger);
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

.study-advanced {
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 0 12px;
}

.study-advanced summary {
  padding: 11px 0;
  color: var(--c-text-2);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.study-advanced[open] summary {
  border-bottom: 1px solid var(--c-border);
}

.study-advanced .form-grid {
  padding: 12px 0;
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

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
