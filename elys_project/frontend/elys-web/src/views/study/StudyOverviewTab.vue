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
        </div>

        <div v-if="summary.mounts.length" class="study-mounted-list">
          <span class="study-mounted-list__label">使用的数据集</span>
          <div class="study-mounted-list__items">
            <RouterLink
              v-for="mount in summary.mounts"
              :key="mount.id"
              class="mounted-data-item"
              to="/datasets"
            >
              <strong>{{ mountAssetLabel(mount) }}</strong>
              <small v-if="mount.dataset_asset?.subject_count">{{ mount.dataset_asset.subject_count }} 名被试</small>
            </RouterLink>
          </div>
        </div>

        <div class="study-decision-inline">
          <div>
            <span>建议下一步</span>
            <strong>{{ decision.title }}</strong>
            <p>{{ decision.description }}</p>
          </div>
          <RouterLink
            class="btn btn--primary"
            :to="decision.to"
            :target="decisionOpensPipeline ? '_blank' : undefined"
            :rel="decisionOpensPipeline ? 'opener' : undefined"
          >{{ decision.action }}</RouterLink>
        </div>
      </section>

      <!-- 工作流 / 运行 / 结果 -->
      <section class="study-card">
        <header class="study-card__head"><h3>工作流与运行</h3></header>
        <div class="study-workspace-lists">
          <div class="study-workspace-col">
            <span class="study-workspace-col__label">工作流</span>
            <div v-if="!summary.pipelines.length" class="study-inline-empty">
              暂无工作流，进入工作区即可创建分析流程。
            </div>
            <div v-else class="study-compact-list">
              <article v-for="pipeline in summary.pipelines" :key="pipeline.id" class="study-compact-item">
                <div>
                  <strong>{{ pipeline.name }}</strong>
                  <p>v{{ pipeline.version }} · {{ pipeline.node_count }} 个节点</p>
                </div>
                <StatusPill :tone="pipelineStatusTone(pipeline.status)" :label="formatPipelineStatus(pipeline.status)" />
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
                  <p>{{ formatDateTime(execution.finished_at || execution.started_at) }}</p>
                </div>
                <StatusPill :tone="executionStatusTone(execution.status)" :label="formatPipelineExecutionStatus(execution.status)" />
              </article>
            </div>
          </div>
        </div>

        <div class="study-mounted-list">
          <span class="study-mounted-list__label">结果</span>
          <div v-if="!visibleStudyOutputs.length" class="study-inline-empty">
            暂无结果，运行完成后会在这里汇总可预览或已保存的结果。
          </div>
          <div v-else class="study-compact-list">
            <article v-for="artifact in visibleStudyOutputs" :key="artifact.id" class="study-compact-item">
              <div>
                <strong>{{ artifact.display_name || formatDataType(artifact.data_type) }}</strong>
                <p>{{ formatDataType(artifact.data_type) }} · {{ formatFileSize(artifact.file_size) }}</p>
              </div>
              <StatusPill :tone="artifactRetentionTone(artifact)" :label="formatArtifactRetention(artifact)" />
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
            <dt>成员</dt>
            <dd>{{ summary.counts.members }} 人</dd>
          </div>
          <div>
            <dt>你的角色</dt>
            <dd>{{ permissionText }}</dd>
          </div>
        </dl>
        <details class="study-technical-details">
          <summary>技术信息</summary>
          <dl>
            <div><dt>研究项 ID</dt><dd>{{ study.currentStudy.id }}</dd></div>
            <div><dt>状态</dt><dd>{{ studyStatusLabel(study.currentStudy.status) }}</dd></div>
            <div><dt>存储配额</dt><dd>{{ formatStorageQuota(study.currentStudy.storage_quota_bytes) }}</dd></div>
          </dl>
        </details>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import IconLine from '@/components/IconLine.vue'
import StatusPill from '@/components/common/StatusPill.vue'
import { useStudyStore } from '@/stores/study'
import { useStudySummary } from '@/composables/useStudySummary'
import {
  artifactRetentionTone,
  executionStatusTone,
  formatArtifactRetention,
  formatDataType,
  formatPipelineExecutionStatus,
  formatPipelineStatus,
  pipelineStatusTone,
} from '@/composables/pipeline/pipelineFormatters'
import { formatDateTime, formatFileSize } from '@/composables/common/formatters'
import { deriveStudyStage, type StudyNextTarget } from '@/composables/studies/studyStage'
import { studyRoleLabel, studyStatusLabel } from '@/composables/studies/studyFormatters'
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

// 「建议下一步」复用 deriveStudyStage（与 Dashboard/StudiesPage 同一份阶段判定），路由按 target 在本页拼。
function nextStepRoute(target: StudyNextTarget, sid: string): RouteLocationRaw {
  if (target === 'import-data') return `/datasets?study_id=${sid}`
  if (target === 'view-data') return `/studies/${sid}/data`
  // 工作流在新标签页打开：带 from=studies，让工作区顶栏「退出」按钮在来源页已关时知道兜底跳回研究项列表。
  return { path: `/studies/${sid}/pipeline`, query: { from: 'studies' } } // configure-pipeline / view-run / continue
}
const decision = computed(() => {
  const s = summary.value
  const sid = studyId.value
  const stage = deriveStudyStage(
    s
      ? {
          loaded: true,
          recordingCount: s.counts.recordings,
          pipelineCount: s.counts.pipelines,
          executionCount: s.counts.executions,
          runningExecutionCount: s.running_execution_count,
        }
      : { loaded: false },
  )
  return { ...stage.nextStep, to: nextStepRoute(stage.nextStep.target, sid) }
})
// 指向工作流(pipeline)时在新标签打开，让用户专注；指向数据集/数据 tab 则维持当前页跳转。
// decision.to 可能是字符串路径或 { path, query } 对象，取出 path 再判断。
const decisionOpensPipeline = computed(() => {
  const to = decision.value.to
  const path = typeof to === 'string' ? to : to.path || ''
  return path.includes('/pipeline')
})

// 概览结果区只展示「保存 / 缓存 / 回收站」三类；纯临时（keep=false 且 cache_eligible=false 且未删）
// 是系统中间态，与「结果」tab 同口径藏掉，不占用户视野。
const visibleStudyOutputs = computed(() =>
  (summary.value?.study_outputs ?? []).filter(
    (output) => output.keep || output.cache_eligible || Boolean(output.deleted_at),
  ),
)

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
  return '已有运行记录，可查看结果和运行详情'
})
const permissionText = computed(() => {
  const s = summary.value
  if (!s) return ''
  const role = studyRoleLabel(s.member_role)
  return s.can_run ? `${role}，可发起运行` : `${role}，不可发起运行`
})

function mountAssetLabel(mount: StudyDatasetMount) {
  return mount.dataset_asset?.name || mount.mount_name || '未命名 Asset'
}
function formatStorageQuota(bytes?: number | null) {
  if (!bytes) return '未设置'
  const gb = bytes / 1024 ** 3
  if (gb >= 1) return `${gb.toFixed(gb >= 10 ? 0 : 1)} GB`
  return `${(bytes / 1024 ** 2).toFixed(0)} MB`
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
.mounted-data-item small {
  color: var(--c-text-3);
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
</style>
