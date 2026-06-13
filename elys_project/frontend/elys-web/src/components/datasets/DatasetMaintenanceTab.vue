<template>
  <section class="dataset-tab-panel dmt" aria-label="数据维护中心">
    <!-- 空 / 加载 / 错误态 -->
    <div v-if="!recordsStudyContext" class="dataset-detail-empty">
      <AppIcon name="database" :size="24" />
      <strong>请先准备导入目标</strong>
      <span>准备处理工作空间后，这里会按被试列出采集记录与维护入口。</span>
    </div>
    <div v-else-if="isLoadingRecordings" class="dataset-list-empty">正在读取采集记录...</div>
    <div v-else-if="recordingsError" class="inline-error">{{ recordingsError }}</div>
    <div v-else-if="!selectedAssetRecordings.length" class="dataset-detail-empty">
      <AppIcon name="file" :size="24" />
      <strong>还没有采集记录</strong>
      <span>导入 EEG 原始数据后，这里会按被试 / 任务列出记录与状态。</span>
    </div>

    <template v-else>
      <!-- 体检条 -->
      <div v-if="healthSummary.total" class="dmt-health">
        <AppIcon name="alert" :size="15" />
        <span class="dmt-health__text">{{ healthText }}</span>
      </div>
      <div v-else class="dmt-health dmt-health--ok">
        <AppIcon name="check" :size="15" />
        <span class="dmt-health__text">全部记录就绪</span>
      </div>

      <!-- 工具栏 -->
      <div class="dmt-toolbar">
        <strong class="dmt-toolbar__title">采集记录 · {{ selectedAssetRecordings.length }}</strong>
        <div class="dmt-seg">
          <button type="button" :class="{ 'is-active': mainView === 'table' }" @click="mainView = 'table'">表格</button>
          <button type="button" :class="{ 'is-active': mainView === 'matrix' }" @click="mainView = 'matrix'">矩阵</button>
        </div>
        <button class="dmt-chip-btn" :class="{ 'is-active': onlyProblems }" type="button" @click="onlyProblems = !onlyProblems">
          仅看有问题
        </button>
        <button class="btn btn--sm" type="button" @click="loadSelectedAssetRecordings">
          <AppIcon name="restore" :size="14" /> 刷新
        </button>
      </div>

      <div class="dmt-body">
        <!-- L1 被试导航 / 筛选 -->
        <aside class="dmt-tree" aria-label="被试导航">
          <button class="dmt-tree__all" :class="{ 'is-active': !subjectFilter }" type="button" @click="subjectFilter = null">
            全部被试
          </button>
          <button
            v-for="g in recordingsBySubject"
            :key="g.subject"
            class="dmt-tree__item"
            :class="{ 'is-active': subjectFilter === g.subject }"
            type="button"
            @click="subjectFilter = subjectFilter === g.subject ? null : g.subject"
          >
            <IconLine name="users" :size="14" />
            <span class="dmt-tree__name">{{ g.subject }}</span>
            <span class="dmt-dot" :class="`dmt-dot--${subjectHealth(g.recordings)}`"></span>
            <span class="dmt-tree__count">{{ g.recordings.length }}</span>
          </button>
        </aside>

        <!-- L2 主区 -->
        <div class="dmt-main">
          <!-- 表格视图 -->
          <table v-if="mainView === 'table'" class="dmt-table">
            <thead>
              <tr>
                <th v-if="showSession">会话</th>
                <th>任务</th>
                <th v-if="showRun">run</th>
                <th class="dmt-table__status">状态</th>
              </tr>
            </thead>
            <tbody v-for="g in groupedRows" :key="g.subject">
              <tr class="dmt-group">
                <td :colspan="colCount">
                  <IconLine name="users" :size="13" />
                  <strong>{{ g.subject }}</strong>
                  <span class="dmt-group__count">{{ g.recordings.length }} 条</span>
                </td>
              </tr>
              <tr
                v-for="row in g.recordings"
                :key="row.rec.id"
                class="dmt-row"
                :class="{ 'is-selected': row.rec.id === selectedRecordingId }"
                @click="selectRecording(row.rec)"
              >
                <td v-if="showSession" class="dmt-muted">{{ row.rec.session ? `ses-${row.rec.session}` : '—' }}</td>
                <td>{{ row.rec.task }}</td>
                <td v-if="showRun" class="dmt-muted">{{ row.rec.run ?? '—' }}</td>
                <td class="dmt-table__status">
                  <span v-if="row.status" class="badge" :class="toneBadge(row.status.tone)">{{ row.status.label }}</span>
                  <AppIcon v-else name="check" :size="14" class="dmt-ready" />
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 矩阵视图：被试 × 任务 覆盖 -->
          <div v-else class="dmt-matrix">
            <table class="dmt-matrix__table">
              <thead>
                <tr>
                  <th></th>
                  <th v-for="task in matrixTasks" :key="task">{{ task }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mrow in matrixRows" :key="mrow.subject">
                  <th class="dmt-matrix__rowhead">{{ mrow.subject }}</th>
                  <td v-for="task in matrixTasks" :key="task">
                    <span class="dmt-cell" :class="`dmt-cell--${mrow.cells[task]}`" :title="cellTitle(mrow.cells[task])"></span>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="dmt-legend">
              <span><span class="dmt-cell dmt-cell--ok"></span> 就绪</span>
              <span><span class="dmt-cell dmt-cell--warning"></span> 有问题</span>
              <span><span class="dmt-cell dmt-cell--gap"></span> 缺（未采集）</span>
            </div>
          </div>
        </div>

        <!-- L2 记录抽屉（只读） -->
        <aside v-if="selectedRecording" class="dmt-drawer" aria-label="记录详情">
          <div class="dmt-drawer__head">
            <strong>{{ selectedRecording.subject }} · {{ selectedRecording.task }}</strong>
            <button class="icon-btn" type="button" title="关闭" @click="selectedRecordingId = null">×</button>
          </div>

          <div class="dmt-drawer__label">元数据</div>
          <dl class="dmt-meta">
            <div><dt>被试</dt><dd>{{ selectedRecording.subject }}</dd></div>
            <div v-if="selectedRecording.session"><dt>会话</dt><dd>{{ selectedRecording.session }}</dd></div>
            <div><dt>任务</dt><dd>{{ selectedRecording.task }}</dd></div>
            <div v-if="selectedRecording.run"><dt>run</dt><dd>{{ selectedRecording.run }}</dd></div>
            <div><dt>源格式</dt><dd>{{ selectedRecording.sourceFormat }}</dd></div>
            <div><dt>通道 / 事件</dt><dd>{{ selectedRecording.channelEventLabel }}</dd></div>
          </dl>

          <div class="dmt-drawer__label">两套维数</div>
          <div v-if="recordingFilesLoading[selectedRecording.id]" class="dataset-list-empty">正在读取文件...</div>
          <div v-else class="dmt-tracks">
            <div class="dmt-track">
              <IconLine name="folder" :size="14" />
              <div class="dmt-track__main">
                <strong>原始数据</strong>
                <span>{{ selectedBuckets?.upload.length || 0 }} 个 · {{ formatFileSize(selectedBuckets?.uploadSize || 0) }} · 永久保留</span>
              </div>
            </div>
            <div class="dmt-track__arrow">↓ 标准化生成</div>
            <div v-if="selectedRecording.hasCanonicalFif" class="dmt-track dmt-track--fif">
              <IconLine name="sparkles" :size="14" />
              <div class="dmt-track__main">
                <strong>标准 FIF</strong>
                <span>{{ selectedBuckets?.fif.length || 0 }} 个 · {{ formatFileSize(selectedBuckets?.fifSize || 0) }} · 可重建</span>
              </div>
            </div>
            <div v-else class="dmt-track dmt-track--missing">
              <IconLine name="sparkles" :size="14" />
              <div class="dmt-track__main">
                <strong>标准 FIF 待生成</strong>
                <span>原始数据已在，可在后续阶段生成标准 FIF</span>
              </div>
            </div>
          </div>

          <details v-if="(selectedBuckets?.tech.length || 0) > 0" class="dmt-tech">
            <summary>技术与元数据文件（{{ selectedBuckets?.tech.length }}）· 排错 / 高级</summary>
            <div v-for="f in selectedBuckets?.tech" :key="f.id" class="dmt-tech__item">
              <span>{{ getFileShortPath(f) }}</span>
              <span class="dmt-muted">{{ formatFileSize(f.file_size || 0) }}</span>
            </div>
          </details>

          <p class="dmt-drawer__note">维护操作（重生成 / 标记 / 替换 / 删除）将在后续阶段开放。</p>
        </aside>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
// 数据集详情「数据文件」tab —— M1 维护中心看层（日志/8_数据集维护中心260613）：
// 被试导航 + 记录主表（状态列只在异常亮 / ses-run 自适应显隐 / 按被试分组）+ 覆盖矩阵 + 只读抽屉 + 体检条。
// 纯展示，全部数据来自 useDatasetRecordings 现成结构，不新增后端调用。维护写操作（M2+）尚未开放。
import { computed, inject, ref } from 'vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import {
  formatFileSize,
  getFileShortPath,
  getQaStatusClass,
  getQaStatusLabel,
} from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
import type { DatasetRecordingRow } from '@/composables/datasets/useDatasetRecordings'

const ctx = inject(datasetContextKey)!
const {
  selectedAssetRecordings,
  recordingsBySubject,
  recordingBucketsById,
  recordingFilesLoading,
  isLoadingRecordings,
  recordingsError,
  loadSelectedAssetRecordings,
  loadRecordingFiles,
} = ctx.recordings
const { recordsStudyContext } = ctx.importTarget

const selectedRecordingId = ref<string | null>(null)
const mainView = ref<'table' | 'matrix'>('table')
const subjectFilter = ref<string | null>(null)
const onlyProblems = ref(false)

type RecTone = 'warning' | 'danger' | 'info'
interface RecStatusInfo {
  tone: RecTone
  label: string
}

// 状态只在「异常」时返回；就绪（有 FIF 且质控未挂）返回 null —— 主表多数行因此保持安静
function recStatus(rec: DatasetRecordingRow): RecStatusInfo | null {
  if (!rec.hasCanonicalFif) return { tone: 'warning', label: '待生成 FIF' }
  const cls = getQaStatusClass(rec.qaStatus)
  if (cls === 'badge--danger') return { tone: 'danger', label: getQaStatusLabel(rec.qaStatus) }
  if (cls === 'badge--warning') return { tone: 'warning', label: getQaStatusLabel(rec.qaStatus) }
  const norm = (rec.qaStatus || '').toLowerCase()
  if (norm === 'pending' || norm === 'queued') return { tone: 'info', label: '待质控' }
  return null
}
function toneBadge(tone: RecTone) {
  if (tone === 'danger') return 'badge--danger'
  if (tone === 'warning') return 'badge--warning'
  return 'badge--outline'
}

// ses / run 列：整个数据集只有单一取值时自动隐藏
const showSession = computed(() => new Set(selectedAssetRecordings.value.map((r) => r.session ?? '')).size > 1)
const showRun = computed(() => new Set(selectedAssetRecordings.value.map((r) => r.run ?? '')).size > 1)
const colCount = computed(() => 2 + (showSession.value ? 1 : 0) + (showRun.value ? 1 : 0))

const healthSummary = computed(() => {
  let noFif = 0
  let qaIssue = 0
  let pending = 0
  for (const r of selectedAssetRecordings.value) {
    const s = recStatus(r)
    if (!s) continue
    if (s.label === '待生成 FIF') noFif += 1
    else if (s.tone === 'info') pending += 1
    else qaIssue += 1
  }
  return { noFif, qaIssue, pending, total: noFif + qaIssue + pending }
})
const healthText = computed(() => {
  const parts: string[] = []
  if (healthSummary.value.noFif) parts.push(`${healthSummary.value.noFif} 条待生成 FIF`)
  if (healthSummary.value.qaIssue) parts.push(`${healthSummary.value.qaIssue} 条质控未过`)
  if (healthSummary.value.pending) parts.push(`${healthSummary.value.pending} 条待质控`)
  return parts.join(' · ')
})

type SubjectHealth = 'ok' | 'warning' | 'danger'
function subjectHealth(recordings: DatasetRecordingRow[]): SubjectHealth {
  let tone: SubjectHealth = 'ok'
  for (const r of recordings) {
    const s = recStatus(r)
    if (s?.tone === 'danger') return 'danger'
    if (s) tone = 'warning'
  }
  return tone
}

const filteredGroups = computed(() =>
  recordingsBySubject.value
    .filter((g) => !subjectFilter.value || g.subject === subjectFilter.value)
    .map((g) => ({
      subject: g.subject,
      recordings: onlyProblems.value ? g.recordings.filter((r) => recStatus(r)) : g.recordings,
    }))
    .filter((g) => g.recordings.length),
)
const groupedRows = computed(() =>
  filteredGroups.value.map((g) => ({
    subject: g.subject,
    recordings: g.recordings.map((rec) => ({ rec, status: recStatus(rec) })),
  })),
)

// 覆盖矩阵：被试 × 任务
type CellState = 'ok' | 'warning' | 'danger' | 'gap'
const matrixTasks = computed(() => Array.from(new Set(selectedAssetRecordings.value.map((r) => r.task))).sort())
const matrixRows = computed(() =>
  recordingsBySubject.value.map((g) => {
    const cells: Record<string, CellState> = {}
    for (const task of matrixTasks.value) {
      const recs = g.recordings.filter((r) => r.task === task)
      if (!recs.length) {
        cells[task] = 'gap'
        continue
      }
      let tone: CellState = 'ok'
      for (const r of recs) {
        const s = recStatus(r)
        if (s?.tone === 'danger') {
          tone = 'danger'
          break
        }
        if (s) tone = 'warning'
      }
      cells[task] = tone
    }
    return { subject: g.subject, cells }
  }),
)
function cellTitle(state: CellState) {
  if (state === 'ok') return '就绪'
  if (state === 'gap') return '缺（未采集）'
  if (state === 'danger') return '有错误'
  return '有问题'
}

const selectedRecording = computed(
  () => selectedAssetRecordings.value.find((r) => r.id === selectedRecordingId.value) || null,
)
const selectedBuckets = computed(() =>
  selectedRecordingId.value ? recordingBucketsById.value[selectedRecordingId.value] : undefined,
)
function selectRecording(rec: DatasetRecordingRow) {
  selectedRecordingId.value = rec.id
  void loadRecordingFiles(rec)
}
</script>
