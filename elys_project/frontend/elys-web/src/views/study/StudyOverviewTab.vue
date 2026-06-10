<template>
  <div class="study-overview">
    <div v-if="error" class="alert alert--warning">{{ error }}</div>

    <div v-if="loading && !summary" class="study-overview__loading">正在加载研究概览…</div>

    <template v-else-if="summary">
      <!-- 研究进度：数据 → 工作流 → 运行 主线 -->
      <section class="study-card">
        <header class="study-card__head"><h3>研究进度</h3></header>
        <div class="study-progress-grid">
          <div class="progress-stat">
            <span class="progress-stat__icon"><IconLine name="target" :size="22" /></span>
            <div>
              <strong>{{ summary.subject_total }}</strong>
              <small>名被试（{{ summary.counts.mounts }} 个数据集）</small>
            </div>
          </div>
          <div class="progress-stat">
            <span class="progress-stat__icon"><IconLine name="settings" :size="22" /></span>
            <div>
              <strong>{{ summary.counts.pipelines }}</strong>
              <small>{{ pipelineReadinessText }}</small>
            </div>
          </div>
          <div class="progress-stat">
            <span class="progress-stat__icon"><IconLine name="barChart" :size="22" /></span>
            <div>
              <strong>{{ summary.counts.executions }}</strong>
              <small>{{ executionReadinessText }}</small>
            </div>
          </div>
          <div class="progress-stat">
            <span class="progress-stat__icon"><IconLine name="lock" :size="22" /></span>
            <div>
              <strong>{{ summary.counts.members }} 人</strong>
              <small>{{ permissionText }}</small>
            </div>
          </div>
        </div>

        <div v-if="summary.mounts.length" class="study-mounted-list">
          <span class="study-mounted-list__label">已挂载的数据集</span>
          <div class="study-mounted-list__items">
            <RouterLink
              v-for="mount in summary.mounts"
              :key="mount.id"
              class="mounted-data-item"
              :class="{ 'is-upgradable': isMountUpgradable(mount) }"
              to="/datasets"
            >
              <strong>{{ mountAssetLabel(mount) }}</strong>
              <span v-if="mount.dataset_version">v{{ mount.dataset_version.version_label }}</span>
              <small v-if="mount.dataset_asset?.subject_count">{{ mount.dataset_asset.subject_count }} 名被试</small>
              <span v-if="isMountUpgradable(mount)" class="upgrade-marker" title="有新版本可升级">⇡</span>
            </RouterLink>
          </div>
        </div>

        <div class="study-decision-inline">
          <div>
            <span>建议下一步</span>
            <strong>{{ decision.title }}</strong>
            <p>{{ decision.description }}</p>
          </div>
          <RouterLink class="btn btn--primary" :to="decision.to">{{ decision.action }}</RouterLink>
        </div>
      </section>

      <!-- 工作流 / 运行 / 派生数据 -->
      <section class="study-card">
        <header class="study-card__head"><h3>工作流与运行</h3></header>
        <div class="study-workspace-lists">
          <div class="study-workspace-col">
            <span class="study-workspace-col__label">工作流</span>
            <div v-if="!summary.pipelines.length" class="study-inline-empty">
              暂无工作流，进入工作流 tab 可创建分析流程。
            </div>
            <div v-else class="study-compact-list">
              <article v-for="pipeline in summary.pipelines" :key="pipeline.id" class="study-compact-item">
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
          <div class="study-workspace-col">
            <span class="study-workspace-col__label">运行记录</span>
            <div v-if="!summary.executions.length" class="study-inline-empty">
              暂无运行记录，配置工作流后可发起运行。
            </div>
            <div v-else class="study-compact-list">
              <article v-for="execution in summary.executions" :key="execution.id" class="study-compact-item">
                <div>
                  <strong>第 {{ execution.execution_seq }} 次运行</strong>
                  <p>{{ executionModeLabel(execution.execution_mode) }} · {{ formatDateTime(execution.finished_at || execution.started_at) }}</p>
                </div>
                <span class="status-pill" :class="executionPillClass(execution.status)">
                  {{ executionStatusLabel(execution.status) }}
                </span>
              </article>
            </div>
          </div>
        </div>

        <div class="study-mounted-list">
          <span class="study-mounted-list__label">派生数据</span>
          <div v-if="!summary.study_outputs.length" class="study-inline-empty">
            暂无派生数据，运行完成后在「结果」tab 汇总可预览或可固定的输出。
          </div>
          <div v-else class="study-compact-list">
            <article v-for="artifact in summary.study_outputs" :key="artifact.id" class="study-compact-item">
              <div>
                <strong>{{ artifact.display_name || artifact.data_type }}</strong>
                <p>{{ artifact.data_type }} · {{ formatFileSize(artifact.file_size) }}</p>
              </div>
              <span class="status-pill" :class="artifactPillClass(artifact)">
                {{ retentionStatusLabel(artifact) }}
              </span>
            </article>
          </div>
        </div>
      </section>

      <!-- 元信息 -->
      <section v-if="study.currentStudy" class="study-card">
        <header class="study-card__head"><h3>元信息</h3></header>
        <dl class="study-meta-table">
          <div>
            <dt>最近更新</dt>
            <dd>{{ formatDateTime(study.currentStudy.updated_at || study.currentStudy.created_at) }}</dd>
          </div>
          <div>
            <dt>创建时间</dt>
            <dd>{{ formatDateTime(study.currentStudy.created_at) }}</dd>
          </div>
          <div>
            <dt>访问范围</dt>
            <dd>按成员权限</dd>
          </div>
          <div>
            <dt>存储配额</dt>
            <dd>{{ formatStorageQuota(study.currentStudy.storage_quota_bytes) }}</dd>
          </div>
        </dl>
        <details class="study-technical-details">
          <summary>技术信息</summary>
          <dl>
            <div><dt>研究项 ID</dt><dd>{{ study.currentStudy.id }}</dd></div>
            <div><dt>状态</dt><dd>{{ study.currentStudy.status }}</dd></div>
          </dl>
        </details>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import IconLine from '@/components/IconLine.vue'
import { useStudyStore } from '@/stores/study'
import { useStudySummary } from '@/composables/useStudySummary'
import type { StudyDatasetMount } from '@/types'

const props = defineProps<{ studyId?: string }>()
const route = useRoute()
const study = useStudyStore()
const { summary, loading, error, load } = useStudySummary()

// 优先用 prop（列表页右栏传入），回退 route.params（独立/子路由访问时）
const studyId = computed(() => props.studyId || String(route.params.studyId || ''))

function loadAll(id: string) {
  void load(id) // 概览聚合数据
  void study.loadStudy(id) // study 详情对象（元信息卡读 study.currentStudy）
}
onMounted(() => {
  if (studyId.value) loadAll(studyId.value)
})
watch(studyId, (id) => {
  if (id) loadAll(id)
})

// 沿用原 StudiesPage 的 studyDecision 主线判断：数据空→导入 / 工作流空→配置 / 运行中→看运行 / 就绪→继续
const decision = computed(() => {
  const s = summary.value
  const sid = studyId.value
  if (!s) return { title: '加载中', description: '', action: '查看数据', to: `/studies/${sid}/data` }
  if (s.counts.recordings === 0) {
    return { title: '先导入数据集', description: '当前研究项还没有可处理的数据引用。导入或挂载数据集后再进入后续处理。', action: '导入数据集', to: `/datasets?study_id=${sid}` }
  }
  if (s.counts.pipelines === 0) {
    return { title: '配置工作流', description: '已有数据引用，但还没有工作流。下一步是创建或选择分析流程。', action: '进入工作流', to: `/studies/${sid}/workflow` }
  }
  if (s.running_execution_count > 0) {
    return { title: '查看运行状态', description: '当前有运行正在进行，建议先查看进度、日志和输出状态。', action: '查看运行记录', to: `/studies/${sid}/workflow` }
  }
  return { title: '可以继续分析', description: '数据和工作流已就绪，可以创建新运行或查看既有运行结果。', action: '进入工作流', to: `/studies/${sid}/workflow` }
})

const pipelineReadinessText = computed(() => {
  const s = summary.value
  if (!s) return ''
  return s.counts.pipelines === 0 ? '还没有工作流，可先配置分析流程' : '已有工作流，可继续创建或查看运行记录'
})
const executionReadinessText = computed(() => {
  const s = summary.value
  if (!s) return ''
  if (s.running_execution_count > 0) return `${s.running_execution_count} 条运行正在进行`
  if (s.counts.executions === 0) return '暂无运行记录'
  return '已有运行记录，可查看结果和审计信息'
})
const permissionText = computed(() => {
  const s = summary.value
  if (!s) return ''
  const role = roleLabel(s.member_role)
  return s.can_run ? `${role}，可发起运行` : `${role}，不可发起运行`
})

function roleLabel(role?: string | null) {
  if (!role) return '未同步'
  const labels: Record<string, string> = { owner: '负责人', admin: '管理员', editor: '编辑', viewer: '查看', pi: 'PI' }
  return labels[role] || role
}
function mountAssetLabel(mount: StudyDatasetMount) {
  return mount.dataset_asset?.name || mount.mount_name || '未命名 Asset'
}
function isMountUpgradable(mount: StudyDatasetMount) {
  const locked = mount.dataset_version_id
  const current = mount.dataset_asset?.current_version_id
  if (!locked || !current) return false
  return locked !== current
}
function pipelineStatusLabel(status: string) {
  const labels: Record<string, string> = { draft: '草稿', active: '可运行', archived: '已归档', deleted: '已删除' }
  return labels[status] || status
}
function pipelinePillClass(status: string) {
  if (status === 'active') return 'status-pill--success'
  if (status === 'draft') return 'status-pill--warn'
  return 'status-pill--muted'
}
function executionStatusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: '排队中', pending: '排队中', running: '运行中', waiting_user_input: '等待确认',
    completed: '已完成', failed: '失败', canceled: '已取消',
  }
  return labels[status] || status
}
function executionPillClass(status: string) {
  if (status === 'completed') return 'status-pill--success'
  if (['queued', 'pending', 'running', 'waiting_user_input'].includes(status)) return 'status-pill--warn'
  if (['failed', 'canceled'].includes(status)) return 'status-pill--danger'
  return 'status-pill--muted'
}
function executionModeLabel(mode: string) {
  const labels: Record<string, string> = { trial: '试运行', analysis: '正式分析', replay: '重放', system: '系统' }
  return labels[mode] || mode
}
function retentionStatusLabel(artifact: { keep?: boolean; cache_eligible?: boolean; deleted_at?: string | null }) {
  if (artifact.deleted_at) return '已删除'
  if (artifact.keep) return '保存'
  if (artifact.cache_eligible) return '缓存'
  return '临时'
}
function artifactPillClass(artifact: { keep?: boolean; deleted_at?: string | null }) {
  if (artifact.deleted_at) return 'status-pill--danger'
  if (artifact.keep) return 'status-pill--success'
  return 'status-pill--warn'
}
function formatFileSize(bytes?: number | null) {
  if (!bytes) return '未知大小'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}
function formatStorageQuota(bytes?: number | null) {
  if (!bytes) return '未设置'
  const gb = bytes / 1024 ** 3
  if (gb >= 1) return `${gb.toFixed(gb >= 10 ? 0 : 1)} GB`
  return `${(bytes / 1024 ** 2).toFixed(0)} MB`
}
function formatDateTime(value?: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(date)
}
</script>

<style scoped>
.study-overview {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.study-overview__loading {
  padding: 48px 24px;
  color: var(--c-text-3);
  text-align: center;
}
.alert {
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 14px;
}
.alert--warning {
  border: 1px solid var(--c-warning-soft);
  background: var(--c-warning-soft);
  color: var(--c-warning);
}
.study-card {
  border: 1px solid var(--c-border);
  border-radius: 10px;
  background: #fff;
  padding: 18px;
}
.study-card__head {
  margin-bottom: 14px;
}
.study-card__head h3 {
  margin: 0;
  color: var(--c-text);
  font-size: 15px;
  font-weight: 700;
}
.study-progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.progress-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 8px;
  background: var(--c-bg-soft);
  padding: 12px 14px;
}
.progress-stat__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  color: var(--c-text-2);
}
.progress-stat > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.progress-stat strong {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.1;
}
.progress-stat small {
  color: var(--c-text-3);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.study-mounted-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--c-bg-tint);
}
.study-mounted-list__label {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
}
.study-mounted-list__items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.mounted-data-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #d8e3f5;
  border-radius: 8px;
  background: #f5f8ff;
  padding: 6px 10px;
  color: #3358c6;
  font-size: 12px;
  text-decoration: none;
}
.mounted-data-item.is-upgradable {
  border-color: #f0c674;
  background: #fff7e6;
}
.mounted-data-item small {
  color: var(--c-text-3);
}
.upgrade-marker {
  color: var(--c-warning);
  font-weight: 700;
}
.study-decision-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--c-border);
}
.study-decision-inline span {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
}
.study-decision-inline strong {
  display: block;
  margin-top: 6px;
  color: var(--c-text);
  font-size: 18px;
}
.study-decision-inline p {
  margin: 6px 0 0;
  color: var(--c-text-2);
  line-height: 1.6;
}
.study-workspace-lists {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}
.study-workspace-col__label {
  color: var(--c-text-3);
  font-size: 12px;
  font-weight: 700;
}
.study-compact-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.study-compact-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 12px;
}
.study-compact-item strong {
  color: var(--c-text);
  font-size: 13px;
}
.study-compact-item p {
  margin: 4px 0 0;
  color: var(--c-text-3);
  font-size: 12px;
}
.study-inline-empty {
  margin-top: 8px;
  padding: 16px;
  border-radius: 8px;
  background: var(--c-bg-soft);
  color: var(--c-text-3);
  font-size: 13px;
}
.study-meta-table {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 0;
}
.study-meta-table dt {
  color: var(--c-text-3);
  font-size: 12px;
}
.study-meta-table dd {
  margin: 4px 0 0;
  color: var(--c-text);
  font-size: 14px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.study-technical-details {
  margin-top: 14px;
  font-size: 13px;
}
.study-technical-details summary {
  cursor: pointer;
  color: var(--c-text-3);
}
.study-technical-details dl {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin: 12px 0 0;
}
.study-technical-details dt {
  color: var(--c-text-3);
  font-size: 12px;
}
.study-technical-details dd {
  margin: 2px 0 0;
  color: var(--c-text-2);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  overflow-wrap: anywhere;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-3);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.status-pill--success { background: var(--c-success-soft); color: var(--c-success); }
.status-pill--warn { background: var(--c-warning-soft); color: var(--c-warning); }
.status-pill--danger { background: var(--c-danger-soft); color: var(--c-danger); }
.status-pill--muted { background: var(--c-bg-tint); color: var(--c-text-3); }
</style>
