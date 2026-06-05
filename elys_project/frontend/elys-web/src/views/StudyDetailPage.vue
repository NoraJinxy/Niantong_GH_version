<template>
  <WorkbenchShell active-key="studies" active-top-key="studies" :show-sidebar="false">
    <div class="page__header study-header">
      <div>
        <RouterLink class="muted text-sm" to="/studies">Study 研究项 /</RouterLink>
        <h1 class="page__title">{{ study?.name || 'Study 主页' }}</h1>
        <p class="page__subtitle">
          Study ID: <code>{{ studyId }}</code>
          <span v-if="study"> · {{ study.description || '暂无描述' }}</span>
        </p>
      </div>
      <div class="row gap-2 row--wrap">
        <button class="btn" type="button" :disabled="loading" @click="loadStudy">
          <AppIcon name="clock" :size="16" />
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <RouterLink class="btn" :to="importTarget">
          <AppIcon name="import" :size="16" />
          导入 Dataset
        </RouterLink>
        <RouterLink class="btn btn--primary" :to="{ path: '/pipeline', query: { studyId } }">
          <AppIcon name="pipeline" :size="16" />
          工作流 / 运行
        </RouterLink>
      </div>
    </div>

    <div v-if="error" class="alert alert--danger mb-4">
      <AppIcon name="admin" :size="18" />
      <div class="alert__body">{{ error }}</div>
    </div>

    <div v-if="warnings.length" class="alert alert--warning mb-4">
      <AppIcon name="clock" :size="18" />
      <div class="alert__body">{{ warnings.join('；') }}</div>
    </div>

    <div v-if="loading && !study" class="empty">
      <div class="empty__icon"><span class="spinner spinner--dark"></span></div>
      正在加载 Study 主页...
    </div>

    <template v-else>
      <section class="grid grid-4 mb-5" aria-label="Study overview">
        <article class="stat">
          <div class="stat__icon"><AppIcon name="database" :size="22" /></div>
          <div class="stat__label">Data</div>
          <div class="stat__value">{{ recordings.length }}</div>
          <div class="stat__delta">Recording / 采集记录</div>
        </article>
        <article class="stat stat--accent">
          <div class="stat__icon"><AppIcon name="pipeline" :size="22" /></div>
          <div class="stat__label">Pipelines</div>
          <div class="stat__value">{{ pipelines.length }}</div>
          <div class="stat__delta">{{ activePipelineCount }} 个可运行</div>
        </article>
        <article class="stat stat--warn">
          <div class="stat__icon"><AppIcon name="clock" :size="22" /></div>
          <div class="stat__label">运行记录</div>
          <div class="stat__value">{{ recentExecutions.length }}</div>
          <div class="stat__delta">{{ activeExecutionCount }} 个运行中 / 等待中</div>
        </article>
        <article class="stat stat--success">
          <div class="stat__icon"><AppIcon name="file" :size="22" /></div>
          <div class="stat__label">Artifacts</div>
          <div class="stat__value">{{ artifacts.length }}</div>
          <div class="stat__delta">来自最近运行的有限摘要</div>
        </article>
      </section>

      <section class="study-section mb-5" id="overview">
        <div class="section-head">
          <div>
            <h2>Overview</h2>
            <p>研究项摘要、成员、权限和当前状态。</p>
          </div>
          <span class="status-pill" :class="statusPillClass(study?.status)">
            {{ statusLabel(study?.status) }}
          </span>
        </div>

        <div class="overview-grid">
          <article class="overview-card">
            <span>兼容标识</span>
            <strong>{{ studyId }}</strong>
            <p>当前前端显示为 Study，底层 API 仍兼容既有路径。</p>
          </article>
          <article class="overview-card">
            <span>我的角色</span>
            <strong>{{ myRoleLabel }}</strong>
            <p>{{ myPermissionLabel }}</p>
          </article>
          <article class="overview-card">
            <span>成员</span>
            <strong>{{ members.length ? `${members.length} 人` : '待接入' }}</strong>
            <p>{{ members.length ? memberNames : '成员接口不可用时显示待接入。' }}</p>
          </article>
          <article class="overview-card">
            <span>运行空间配额</span>
            <strong>{{ formatQuota(study?.storage_quota_bytes || 0) }}</strong>
            <p>用于 Study 输出、预览、导出和临时运行文件。</p>
          </article>
        </div>
      </section>

      <section class="study-layout mb-5">
        <div class="study-section" id="data">
          <div class="section-head">
            <div>
              <h2>Data</h2>
              <p>Study 引用的数据资产、采集记录和 canonical FIF 状态。</p>
            </div>
            <RouterLink class="btn btn--sm" :to="importTarget">导入 Dataset</RouterLink>
          </div>

          <div class="data-subsection">
            <div class="subsection-title">
              <h3>Dataset Mounts</h3>
              <span>{{ mounts.length ? `${mounts.length} 个` : mountStatusLabel }}</span>
            </div>
            <div v-if="mounts.length" class="mount-list">
              <article v-for="mount in mounts" :key="mount.id" class="mount-item">
                <div>
                  <strong>{{ mount.mount_name }}</strong>
                  <p>{{ mount.dataset_asset?.name || mount.dataset_asset_id }}</p>
                </div>
                <span class="status-pill" :class="mount.is_active ? 'status-pill--ok' : ''">
                  {{ mount.is_active ? 'active' : 'inactive' }}
                </span>
              </article>
            </div>
            <div v-else class="empty compact-empty">
              <div class="empty__icon"><AppIcon name="database" :size="22" /></div>
              {{ mountStatusLabel }}
            </div>
          </div>

          <div class="data-subsection">
            <div class="subsection-title">
              <h3>Recordings</h3>
              <span>{{ recordings.length }} 条</span>
            </div>
            <div v-if="!recordings.length" class="empty compact-empty">
              <div class="empty__icon"><AppIcon name="file" :size="22" /></div>
              暂无采集记录。可以先导入 Dataset，或等待 Recording API 接入。
            </div>
            <div v-else class="table-wrap">
              <table class="table table--compact">
                <thead>
                  <tr>
                    <th>被试</th>
                    <th>Session</th>
                    <th>Task</th>
                    <th>Run</th>
                    <th>格式</th>
                    <th>canonical FIF</th>
                    <th>通道 / 事件</th>
                    <th>质量状态</th>
                    <th>导入时间</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="recording in recordings" :key="recording.id">
                    <td><strong>{{ recording.subject }}</strong></td>
                    <td>{{ recording.session || '-' }}</td>
                    <td>{{ recording.task || '-' }}</td>
                    <td>{{ recording.run || '-' }}</td>
                    <td>{{ recording.sourceFormat || '-' }}</td>
                    <td>
                      <span class="status-pill" :class="recording.hasCanonicalFif ? 'status-pill--ok' : ''">
                        {{ recording.hasCanonicalFif ? '已生成' : '待生成' }}
                      </span>
                    </td>
                    <td>{{ recording.channelEventLabel }}</td>
                    <td>
                      <span class="status-pill" :class="qualityPillClass(recording.qaStatus)">
                        {{ recording.qaStatus || 'unknown' }}
                      </span>
                    </td>
                    <td class="muted">{{ formatDate(recording.importedAt) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <aside class="study-section side-panel">
          <div class="section-head">
            <div>
              <h2>Quick Links</h2>
              <p>常用入口，不在此页做完整上传或执行。</p>
            </div>
          </div>
          <nav class="quick-actions">
            <RouterLink class="quick-action" :to="importTarget">
              <AppIcon name="import" :size="18" />
              <span>Dataset 导入</span>
            </RouterLink>
            <RouterLink class="quick-action" :to="{ path: '/pipeline', query: { studyId } }">
              <AppIcon name="pipeline" :size="18" />
              <span>工作流 / 运行</span>
            </RouterLink>
            <RouterLink class="quick-action is-preview" to="/observe">
              <AppIcon name="observe" :size="18" />
              <span>观察结果</span>
              <small>预览</small>
            </RouterLink>
            <RouterLink class="quick-action is-preview" to="/figures">
              <AppIcon name="figure" :size="18" />
              <span>论文出图</span>
              <small>预览</small>
            </RouterLink>
          </nav>
        </aside>
      </section>

      <section class="grid grid-2 mb-5">
        <div class="study-section" id="pipelines">
          <div class="section-head">
            <div>
              <h2>Pipelines</h2>
              <p>工作流定义，只保存节点、参数和选择规则。</p>
            </div>
            <RouterLink class="btn btn--sm" :to="{ path: '/pipeline', query: { studyId } }">打开工作流</RouterLink>
          </div>
          <div v-if="!pipelines.length" class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="pipeline" :size="22" /></div>
            暂无 Pipeline。进入工作流页创建 draft 或 active 工作流。
          </div>
          <div v-else class="compact-list">
            <article v-for="pipeline in pipelines" :key="pipeline.id" class="compact-item">
              <div>
                <strong>{{ pipeline.name }}</strong>
                <p>v{{ pipeline.version }} · {{ pipeline.node_count }} 个节点</p>
              </div>
              <span class="status-pill" :class="pipelinePillClass(pipeline.status)">
                {{ pipelineStatusLabel(pipeline.status) }}
              </span>
            </article>
          </div>
        </div>

        <div class="study-section" id="runs">
          <div class="section-head">
            <div>
              <h2>运行记录</h2>
              <p>运行记录保存输入快照、定义快照、任务、输出和 manifest。</p>
            </div>
          </div>
          <div v-if="!recentExecutions.length" class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="clock" :size="22" /></div>
            暂无最近运行。创建工作流后可以发起 trial 或 analysis 执行。
          </div>
          <div v-else class="compact-list">
            <article v-for="execution in recentExecutions" :key="execution.id" class="compact-item">
              <div>
                <strong>运行 #{{ execution.execution_seq }}</strong>
                <p>{{ execution.execution_mode }} / {{ execution.save_policy }} · {{ formatDate(execution.finished_at || execution.started_at) }}</p>
              </div>
              <span class="status-pill" :class="executionPillClass(execution.status)">
                {{ executionStatusLabel(execution.status) }}
              </span>
            </article>
          </div>
        </div>
      </section>

      <section class="grid grid-2 mb-5">
        <div class="study-section" id="artifacts">
          <div class="section-head">
            <div>
              <h2>Artifacts</h2>
              <p>输出结果通过 Artifact ID 访问，页面不暴露服务器绝对路径。</p>
            </div>
          </div>
          <div v-if="!artifacts.length" class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="file" :size="22" /></div>
            暂无 Artifact 摘要。完成运行后会在此显示可预览或可固定的输出。
          </div>
          <div v-else class="compact-list">
            <article v-for="artifact in artifacts" :key="artifact.id" class="compact-item">
              <div>
                <strong>{{ artifact.display_name || artifact.data_type }}</strong>
                <p>{{ artifact.data_type }} · {{ formatFileSize(artifact.file_size || null) }}</p>
              </div>
              <span class="status-pill" :class="artifactPillClass(artifact.retention_status)">
                {{ artifact.retention_status || 'current' }}
              </span>
            </article>
          </div>
        </div>

        <div class="study-section" id="activity">
          <div class="section-head">
            <div>
              <h2>Activity</h2>
              <p>当前为已有对象时间聚合；正式审计事件待接入。</p>
            </div>
          </div>
          <div v-if="!activityItems.length" class="empty compact-empty">
            <div class="empty__icon"><AppIcon name="clock" :size="22" /></div>
            暂无可显示活动。后续接入 audit_events 后展示真实协作轨迹。
          </div>
          <div v-else class="activity-list">
            <article v-for="item in activityItems" :key="item.id" class="activity-item">
              <span class="activity-mark" :class="`is-${item.kind}`"></span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.detail }}</p>
              </div>
              <span>{{ formatDate(item.time) }}</span>
            </article>
          </div>
        </div>
      </section>
    </template>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { recordingApi, studyDatasetMountApi } from '@/api/datasetAssets'
import { pipelineApi } from '@/api/pipelines'
import { studyApi } from '@/api/studies'
import type {
  DerivedDataset,
  Pipeline,
  PipelineExecution,
  Recording,
  Study,
  StudyDatasetMount,
  StudyMember,
} from '@/types'

interface RecordingRow {
  id: string
  subject: string
  session: string | null
  task: string
  run: string | null
  sourceFormat: string
  hasCanonicalFif: boolean
  channelEventLabel: string
  qaStatus: string | null
  importedAt: string | null
}

interface ActivityItem {
  id: string
  title: string
  detail: string
  time: string | null
  kind: 'study' | 'data' | 'pipeline' | 'run' | 'artifact'
}

const EXECUTION_PIPELINE_LIMIT = 4
const EXECUTION_LIMIT_PER_PIPELINE = 5
const ARTIFACT_EXECUTION_LIMIT = 5

const route = useRoute()
const studyId = computed(() => String(route.params.id || ''))
const importTarget = computed(() => `/datasets?study_id=${encodeURIComponent(studyId.value)}`)

const study = ref<Study | null>(null)
const members = ref<StudyMember[]>([])
const mounts = ref<StudyDatasetMount[]>([])
const recordings = ref<RecordingRow[]>([])
const pipelines = ref<Pipeline[]>([])
const recentExecutions = ref<PipelineExecution[]>([])
const artifacts = ref<DerivedDataset[]>([])
const loading = ref(false)
const error = ref('')
const warnings = ref<string[]>([])
const mountsLoaded = ref(false)

const activePipelineCount = computed(() => pipelines.value.filter((pipeline) => pipeline.status === 'active').length)
const activeExecutionCount = computed(() =>
  recentExecutions.value.filter((execution) => ['queued', 'running', 'waiting_user_input'].includes(execution.status)).length,
)
const currentMember = computed(() => members.value.find((member) => member.user_id === study.value?.owner_id))
const myRoleLabel = computed(() => {
  if (members.value.length === 0) return '待接入'
  const owner = members.value.find((member) => member.role === 'owner')
  return owner ? `${roleLabel(owner.role)} · ${owner.username}` : '成员'
})
const myPermissionLabel = computed(() => {
  const runEnabled = members.value.some((member) => member.can_run)
  if (!members.value.length) return '成员与权限接口不可用时显示待接入。'
  return runEnabled ? '已有成员具备运行权限。' : '尚未读取到可运行成员。'
})
const memberNames = computed(() =>
  members.value.slice(0, 3).map((member) => member.full_name || member.username).join('、'),
)
const mountStatusLabel = computed(() => {
  if (!mountsLoaded.value) return 'Dataset Mount API 待接入'
  return '暂无挂载 Dataset'
})
const activityItems = computed<ActivityItem[]>(() => {
  const items: ActivityItem[] = []
  if (study.value) {
    items.push({
      id: `study-${study.value.id}`,
      title: 'Study 信息更新',
      detail: study.value.status || 'status unknown',
      time: study.value.updated_at || study.value.created_at,
      kind: 'study',
    })
  }
  recordings.value.slice(0, 4).forEach((recording) => {
    items.push({
      id: `recording-${recording.id}`,
      title: `Recording ${recording.subject}`,
      detail: `${recording.task || '-'} · canonical FIF ${recording.hasCanonicalFif ? '已生成' : '待生成'}`,
      time: recording.importedAt,
      kind: 'data',
    })
  })
  pipelines.value.slice(0, 4).forEach((pipeline) => {
    items.push({
      id: `pipeline-${pipeline.id}`,
      title: `Pipeline ${pipeline.name}`,
      detail: `${pipelineStatusLabel(pipeline.status)} · v${pipeline.version}`,
      time: pipeline.updated_at || pipeline.created_at,
      kind: 'pipeline',
    })
  })
  recentExecutions.value.slice(0, 4).forEach((execution) => {
    items.push({
      id: `execution-${execution.id}`,
      title: `运行 #${execution.execution_seq}`,
      detail: `${executionStatusLabel(execution.status)} · ${execution.execution_mode} / ${execution.save_policy}`,
      time: execution.finished_at || execution.started_at,
      kind: 'run',
    })
  })
  artifacts.value.slice(0, 3).forEach((artifact) => {
    items.push({
      id: `derived-${artifact.id}`,
      title: `派生 ${artifact.display_name || artifact.data_type}`,
      detail: artifact.retention_status || 'current',
      time: artifact.created_at || null,
      kind: 'artifact',
    })
  })
  return items
    .filter((item) => !!item.time)
    .sort((a, b) => timestamp(b.time) - timestamp(a.time))
    .slice(0, 8)
})

onMounted(loadStudy)

watch(studyId, () => {
  void loadStudy()
})

async function loadStudy() {
  loading.value = true
  error.value = ''
  warnings.value = []
  mountsLoaded.value = false
  recordings.value = []
  pipelines.value = []
  recentExecutions.value = []
  artifacts.value = []

  try {
    const studyRes = await studyApi.get(studyId.value)
    study.value = studyRes.data
    await Promise.all([loadMembers(), loadMounts(), loadRecordings(), loadPipelinesAndExecutions()])
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Study 主页加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMembers() {
  try {
    const res = await studyApi.listMembers(studyId.value)
    members.value = res.data.members
  } catch {
    members.value = []
    warnings.value.push('成员与权限摘要暂不可用')
  }
}

async function loadMounts() {
  try {
    const res = await studyDatasetMountApi.list(studyId.value)
    mounts.value = res.data.mounts
    mountsLoaded.value = true
  } catch {
    mounts.value = []
    mountsLoaded.value = false
  }
}

async function loadRecordings() {
  try {
    const res = await recordingApi.list(studyId.value)
    recordings.value = res.data.recordings.map(normalizeRecording)
  } catch {
    recordings.value = []
    warnings.value.push('Recording 摘要暂不可用')
  }
}

async function loadPipelinesAndExecutions() {
  try {
    const pipelineRes = await pipelineApi.list(studyId.value)
    pipelines.value = pipelineRes.data.pipelines
  } catch {
    pipelines.value = []
    warnings.value.push('Pipeline 摘要暂不可用')
    return
  }

  const executionGroups = await Promise.all(
    pipelines.value.slice(0, EXECUTION_PIPELINE_LIMIT).map((pipeline) =>
      pipelineApi.listExecutions(studyId.value, pipeline.id, EXECUTION_LIMIT_PER_PIPELINE)
        .then((res) => res.data.executions)
        .catch(() => []),
    ),
  )
  recentExecutions.value = executionGroups
    .flat()
    .sort((a, b) => timestamp(b.finished_at || b.started_at) - timestamp(a.finished_at || a.started_at))
    .slice(0, 10)

  const artifactGroups = await Promise.all(
    recentExecutions.value.slice(0, ARTIFACT_EXECUTION_LIMIT).map((execution) =>
      pipelineApi.listExecutionDerivedDatasets(studyId.value, execution.id)
        .then((res) => res.data.derived_datasets)
        .catch(() => []),
    ),
  )
  artifacts.value = artifactGroups.flat().slice(0, 12)
}

function normalizeRecording(recording: Recording): RecordingRow {
  return {
    id: recording.id,
    subject: recording.bids_subject_id || recording.subject_id,
    session: recording.session || null,
    task: recording.task,
    run: recording.run || null,
    sourceFormat: recording.source_format,
    hasCanonicalFif: !!recording.fif_path,
    channelEventLabel: formatChannelEvent(recording.n_channels, recording.n_events),
    qaStatus: recording.qa_status || null,
    importedAt: recording.imported_at || null,
  }
}

function formatChannelEvent(channels?: number | null, events?: number | null) {
  const channelLabel = channels == null ? '-' : `${channels} ch`
  const eventLabel = events == null ? '-' : `${events} evt`
  return `${channelLabel} / ${eventLabel}`
}

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    owner: 'Owner',
    editor: 'Editor',
    viewer: 'Viewer',
  }
  return labels[role] || role
}

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
  if (status === 'active') return 'status-pill--ok'
  if (status === 'archived') return 'status-pill--warn'
  if (status === 'deleted' || status === 'trashed') return 'status-pill--danger'
  return ''
}

function pipelineStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    active: '可运行',
    archived: '已归档',
    deleted: '已删除',
  }
  return labels[status] || status
}

function pipelinePillClass(status: string) {
  if (status === 'active') return 'status-pill--ok'
  if (status === 'draft') return 'status-pill--warn'
  if (status === 'archived' || status === 'deleted') return 'status-pill--muted'
  return ''
}

function executionStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    waiting_user_input: '等待确认',
    completed: '已完成',
    failed: '失败',
    canceled: '已取消',
  }
  return labels[status] || status
}

function executionPillClass(status: string) {
  if (status === 'completed') return 'status-pill--ok'
  if (['queued', 'running', 'waiting_user_input'].includes(status)) return 'status-pill--warn'
  if (['failed', 'canceled'].includes(status)) return 'status-pill--danger'
  return ''
}

function qualityPillClass(status: string | null) {
  if (status === 'checked') return 'status-pill--ok'
  if (status === 'failed' || status === 'rejected') return 'status-pill--danger'
  if (status === 'pending' || status === 'converted') return 'status-pill--warn'
  return 'status-pill--muted'
}

function artifactPillClass(status: string | null | undefined) {
  if (status === 'pinned') return 'status-pill--ok'
  if (status === 'temporary' || status === 'cached') return 'status-pill--warn'
  if (status === 'hidden' || status === 'deleted') return 'status-pill--muted'
  return ''
}

function timestamp(value: string | null | undefined) {
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? 0 : parsed
}

function formatDate(value: string | null | undefined) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatQuota(bytes: number) {
  if (!bytes) return '0 GB'
  return `${(bytes / 1024 / 1024 / 1024).toFixed(0)} GB`
}

function formatFileSize(bytes: number | null) {
  if (!bytes) return '未知大小'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}
</script>

<style scoped>
.study-header {
  align-items: flex-start;
}

.study-section {
  min-width: 0;
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

.section-head h2,
.subsection-title h3 {
  margin: 0 0 4px;
  color: var(--c-text);
  font-size: 15px;
  font-weight: 700;
}

.section-head p,
.subsection-title span,
.overview-card p,
.mount-item p,
.compact-item p {
  margin: 0;
  color: var(--c-text-3);
  font-size: 12px;
  line-height: 1.6;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--s-3);
}

.overview-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: var(--s-4);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.overview-card span {
  color: var(--c-text-3);
  font-size: 12px;
}

.overview-card strong {
  color: var(--c-text);
  font-size: 16px;
  overflow-wrap: anywhere;
}

.study-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(260px, .55fr);
  gap: var(--s-4);
  align-items: start;
}

.side-panel {
  position: sticky;
  top: calc(var(--header-h) + var(--s-4));
}

.data-subsection + .data-subsection {
  margin-top: var(--s-5);
}

.data-subsection,
.table-wrap {
  min-width: 0;
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
}

.subsection-title {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
  align-items: center;
  margin-bottom: var(--s-3);
}

.mount-list,
.compact-list,
.activity-list {
  display: grid;
  gap: var(--s-3);
}

.mount-item,
.compact-item,
.activity-item {
  display: flex;
  justify-content: space-between;
  gap: var(--s-3);
  align-items: center;
  padding: var(--s-3);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  background: var(--c-bg-soft);
}

.mount-item > div,
.compact-item > div,
.activity-item > div {
  min-width: 0;
}

.mount-item strong,
.compact-item strong,
.activity-item strong {
  display: block;
  overflow: hidden;
  color: var(--c-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-empty {
  min-height: 150px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}

.status-pill--ok {
  background: var(--c-success-soft);
  color: var(--c-success);
}

.status-pill--warn {
  background: var(--c-warning-soft);
  color: var(--c-warning);
}

.status-pill--danger {
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.status-pill--muted {
  background: var(--c-bg-tint);
  color: var(--c-text-3);
}

.activity-item {
  align-items: flex-start;
}

.activity-item > span:last-child {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-size: 12px;
}

.activity-mark {
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--c-text-3);
  flex-shrink: 0;
}

.activity-mark.is-study { background: var(--c-success); }
.activity-mark.is-data { background: var(--c-primary); }
.activity-mark.is-pipeline { background: var(--c-warning); }
.activity-mark.is-run { background: var(--c-accent); }
.activity-mark.is-artifact { background: var(--c-text-2); }

@media (max-width: 1100px) {
  .overview-grid,
  .study-layout {
    grid-template-columns: 1fr;
  }

  .side-panel {
    position: static;
  }
}

@media (max-width: 720px) {
  .study-section {
    padding: var(--s-4);
  }

  .section-head,
  .subsection-title,
  .mount-item,
  .compact-item,
  .activity-item {
    align-items: stretch;
    flex-direction: column;
  }

  .table-wrap {
    width: 100%;
  }
}
</style>
