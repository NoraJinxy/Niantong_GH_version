<template>
  <section class="dataset-tab-panel dmt" aria-label="数据维护中心">
    <!-- 电极位置文件（数据集资产级，供「通道定位」节点选用）：常驻顶部，先于采集记录列表 -->
    <DatasetMontagePanel v-if="selectedAssetId" :asset-id="selectedAssetId" />

    <!-- 空 / 加载 / 错误态 -->
    <EmptyState
      v-if="!recordsStudyContext"
      icon="database"
      title="还没有数据"
      description="先到「上传」准备导入目标并上传 EEG 原始数据，这里就会按被试列出采集记录与维护入口。"
    >
      <button class="btn btn--primary" type="button" @click="activeTab = 'import'">去上传</button>
    </EmptyState>
    <EmptyState v-else-if="isLoadingRecordings" description="正在读取采集记录…" compact />
    <div v-else-if="recordingsError" class="inline-error">{{ recordingsError }}</div>
    <EmptyState
      v-else-if="!selectedAssetRecordings.length"
      icon="file"
      title="还没有采集记录"
      description="上传 EEG 原始数据后，这里会按被试 / 任务列出记录与状态。"
    >
      <button class="btn btn--primary" type="button" @click="activeTab = 'import'">去上传</button>
    </EmptyState>

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
          <button type="button" :class="{ 'is-active': mainView === 'matrix' }" @click="mainView = 'matrix'">覆盖</button>
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
                <th v-if="showRun">轮次</th>
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

          <!-- 归类：BIDS 标签，可调整（relabel：改实体 + 后端物理重排派生层，原始数据不碰） -->
          <div class="dmt-drawer__label dmt-label-row">
            <span>归类（标签）</span>
            <button v-if="!relabelEditing" class="dmt-link-btn" type="button" @click="openRelabel">调整</button>
          </div>

          <div v-if="!relabelEditing" class="dmt-tags">
            <span class="dmt-tag">被试 <b>{{ selectedRecording.subject }}</b></span>
            <span v-if="selectedRecording.session" class="dmt-tag">会话 <b>{{ selectedRecording.session }}</b></span>
            <span class="dmt-tag">任务 <b>{{ selectedRecording.task }}</b></span>
            <span v-if="selectedRecording.run" class="dmt-tag">轮次 <b>{{ selectedRecording.run }}</b></span>
            <span class="dmt-tag dmt-tag--muted">{{ selectedRecording.channelEventLabel }}</span>
          </div>

          <form v-else class="dmt-relabel" @submit.prevent="saveRelabel">
            <div class="dmt-relabel__grid">
              <label>被试<input v-model.trim="relabelForm.subject" class="input" placeholder="093" :disabled="relabelSaving" /></label>
              <label>会话<input v-model.trim="relabelForm.session" class="input" placeholder="可空" :disabled="relabelSaving" /></label>
              <label>任务<input v-model.trim="relabelForm.task" class="input" placeholder="rest" :disabled="relabelSaving" /></label>
              <label>轮次<input v-model.trim="relabelForm.run" class="input" placeholder="可空" :disabled="relabelSaving" /></label>
            </div>
            <p class="dmt-relabel__hint">改标签只重排 BIDS 组织方式，不动你上传的原始数据。</p>
            <div v-if="relabelError" class="inline-error">{{ relabelError }}</div>
            <div class="dmt-relabel__actions">
              <button class="btn btn--sm" type="button" :disabled="relabelSaving" @click="cancelRelabel">取消</button>
              <button
                class="btn btn--sm btn--primary"
                type="submit"
                :disabled="relabelSaving || !relabelForm.subject || !relabelForm.task"
              >
                <span v-if="relabelSaving" class="spinner"></span>{{ relabelSaving ? '保存中…' : '保存' }}
              </button>
            </div>
          </form>

          <!-- 原始数据：你上传的，按第几次上传存档、不可改 -->
          <div class="dmt-drawer__label">原始数据（你上传的）· 存档不可改</div>
          <EmptyState
            v-if="recordingVersionsLoading[selectedRecording.id] || recordingFilesLoading[selectedRecording.id]"
            description="正在读取上传历史…"
            compact
          />
          <div v-else class="dmt-uploads">
            <template v-if="selectedVersions.length">
              <div
                v-for="v in selectedVersions"
                :key="v.id"
                class="dmt-upload"
                :class="{ 'is-current': v.version_seq === selectedRecording.currentVersionSeq }"
              >
                <div class="dmt-upload__head">
                  <strong>第 {{ v.version_seq }} 次上传</strong>
                  <span v-if="v.version_seq === selectedRecording.currentVersionSeq" class="badge badge--success">当前使用</span>
                  <span v-else class="dmt-upload__hist">已替换 · 留作历史</span>
                </div>
                <div class="dmt-upload__meta">
                  {{ formatSourceFormat(v.source_format) }} · {{ v.source_files.length }} 个文件 · {{ formatFileSize(v.file_size || 0) }}<template v-if="v.uploaded_at"> · {{ formatDate(v.uploaded_at) }}</template>
                </div>
                <ul v-if="v.version_seq === selectedRecording.currentVersionSeq && v.source_files.length" class="dmt-upload__files">
                  <li v-for="(f, i) in v.source_files" :key="i">{{ baseName(f) }}</li>
                </ul>
              </div>
            </template>
            <div v-else class="dmt-upload is-current">
              <div class="dmt-upload__head">
                <strong>已上传</strong>
                <span class="badge badge--success">当前使用</span>
              </div>
              <div class="dmt-upload__meta">
                {{ selectedRecording.sourceFormat }} · {{ selectedBuckets?.upload.length || 0 }} 个文件 · {{ formatFileSize(selectedBuckets?.uploadSize || 0) }}
              </div>
              <ul v-if="(selectedBuckets?.upload.length || 0) > 0" class="dmt-upload__files">
                <li v-for="f in selectedBuckets?.upload" :key="f.id">{{ getFileShortPath(f) }}</li>
              </ul>
            </div>
          </div>
          <p class="dmt-drawer__note">上传过的原始数据不会被修改或删除。要换数据，请到「上传」重新上传这条记录。</p>
          <button class="btn btn--sm dmt-reupload" type="button" @click="activeTab = 'import'">
            <AppIcon name="import" :size="13" /> 重新上传这条记录
          </button>

          <!-- 分析数据：系统自动准备、跟随「当前」那次上传；不暴露标准化/派生说法 -->
          <div class="dmt-drawer__label">分析数据</div>
          <div class="dmt-analysis" :class="selectedRecording.hasCanonicalFif ? 'is-ready' : 'is-pending'">
            <AppIcon v-if="selectedRecording.hasCanonicalFif" name="check" :size="14" />
            <span>{{ selectedRecording.hasCanonicalFif ? '已整理好，可直接分析' : '原始数据已就绪，分析数据稍后自动准备' }}</span>
          </div>

          <!-- 质控（mock）：状态 + 跑质控 + 人工复核 -->
          <div class="dmt-drawer__label">质控</div>
          <div class="dmt-qa">
            <div class="dmt-qa__row">
              <span class="badge" :class="qaStatusBadge">{{ qaStatusText }}</span>
              <button class="btn btn--sm" type="button" :disabled="qaRunning" @click="onRunQa">
                <span v-if="qaRunning" class="spinner"></span>{{ qaRunning ? '运行中…' : (selectedQaHasReport ? '重跑质控' : '跑质控') }}
              </button>
            </div>
            <div v-if="selectedQaHasReport" class="dmt-qa__report">
              <p v-for="(issue, i) in qaBlocking" :key="`b${i}`" class="dmt-qa__issue dmt-qa__issue--blocking">{{ issue }}</p>
              <p v-for="(warn, i) in qaWarnings" :key="`w${i}`" class="dmt-qa__issue">{{ warn }}</p>
              <p v-if="!qaBlocking.length && !qaWarnings.length" class="dmt-qa__ok">未发现问题</p>
              <div class="dmt-qa__review">
                <span v-if="selectedQaReviewed" class="dmt-muted">人工复核：{{ qaReviewText }}</span>
                <template v-else>
                  <button
                    class="btn btn--sm btn--primary"
                    type="button"
                    :disabled="qaReviewing || qaHasBlocking"
                    :title="qaHasBlocking ? '存在阻塞问题，不能确认通过' : ''"
                    @click="onReviewQa('accept')"
                  >标记通过</button>
                  <button class="btn btn--sm btn--danger" type="button" :disabled="qaReviewing" @click="onReviewQa('reject')">驳回</button>
                </template>
              </div>
            </div>
            <div v-if="qaError" class="inline-error">{{ qaError }}</div>
          </div>

          <details v-if="(selectedBuckets?.tech.length || 0) > 0" class="dmt-tech">
            <summary>技术与元数据文件（{{ selectedBuckets?.tech.length }}）· 排错 / 高级</summary>
            <div v-for="f in selectedBuckets?.tech" :key="f.id" class="dmt-tech__item">
              <span>{{ getFileShortPath(f) }}</span>
              <span class="dmt-muted">{{ formatFileSize(f.file_size || 0) }}</span>
            </div>
          </details>

          <!-- 危险操作：删除/排除这条记录（两步确认，不可恢复） -->
          <div class="dmt-danger">
            <button
              v-if="!deleteConfirming"
              class="btn btn--sm dmt-danger__btn"
              type="button"
              @click="deleteConfirming = true"
            >
              <AppIcon name="trash" :size="13" /> 删除这条记录
            </button>
            <template v-else>
              <p class="dmt-danger__q">确认永久删除？这条记录的原始数据与分析数据一并清除，不可恢复。</p>
              <div class="dmt-danger__actions">
                <button class="btn btn--sm" type="button" :disabled="deleting" @click="deleteConfirming = false">取消</button>
                <button class="btn btn--sm btn--danger" type="button" :disabled="deleting" @click="confirmDelete">
                  <span v-if="deleting" class="spinner"></span>{{ deleting ? '删除中…' : '永久删除' }}
                </button>
              </div>
            </template>
            <div v-if="deleteError" class="inline-error">{{ deleteError }}</div>
          </div>

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
import EmptyState from '@/components/common/EmptyState.vue'
import DatasetMontagePanel from '@/components/datasets/DatasetMontagePanel.vue'
import {
  formatDate,
  formatFileSize,
  formatSourceFormat,
  getFileShortPath,
  getQaStatusClass,
  getQaStatusLabel,
} from '@/composables/datasets/datasetsFormatters'
import { datasetContextKey } from '@/composables/datasets/datasetContext'
import type { DatasetRecordingRow } from '@/composables/datasets/useDatasetRecordings'

const ctx = inject(datasetContextKey)!
// 当前数据集资产 id（电极位置文件面板用；本 tab 仅在选中资产时渲染，故一般非空）
const selectedAssetId = computed(() => ctx.catalog.selectedDatasetAssetId.value || '')
const {
  selectedAssetRecordings,
  recordingsBySubject,
  recordingBucketsById,
  recordingFilesLoading,
  recordingVersionsById,
  recordingVersionsLoading,
  recordingQaById,
  isLoadingRecordings,
  recordingsError,
  loadSelectedAssetRecordings,
  loadRecordingFiles,
  loadRecordingVersions,
  relabelRecording,
  deleteRecording,
  loadRecordingQa,
  runRecordingQa,
  reviewRecordingQa,
} = ctx.recordings
const { recordsStudyContext } = ctx.importTarget
const { activeTab, handleUploaded } = ctx

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
  if (!rec.hasCanonicalFif) return { tone: 'warning', label: '待标准化' }
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
    if (s.label === '待标准化') noFif += 1
    else if (s.tone === 'info') pending += 1
    else qaIssue += 1
  }
  return { noFif, qaIssue, pending, total: noFif + qaIssue + pending }
})
const healthText = computed(() => {
  const parts: string[] = []
  if (healthSummary.value.noFif) parts.push(`${healthSummary.value.noFif} 条待标准化`)
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
// 这条记录的上传历史（第几次上传），最新一次在前；版本接口无数据时为空数组、抽屉走文件桶退路。
const selectedVersions = computed(() =>
  selectedRecordingId.value ? recordingVersionsById.value[selectedRecordingId.value] || [] : [],
)
// source_files 是相对路径，抽屉里只显文件名
function baseName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path
}
function selectRecording(rec: DatasetRecordingRow) {
  selectedRecordingId.value = rec.id
  relabelEditing.value = false
  deleteConfirming.value = false
  deleteError.value = ''
  qaError.value = ''
  void loadRecordingFiles(rec)
  void loadRecordingVersions(rec)
  void loadRecordingQa(rec)
}

// 「调整归类」：抽屉内联改 BIDS 标签
const relabelEditing = ref(false)
const relabelForm = ref({ subject: '', session: '', task: '', run: '' })
const relabelError = ref('')
const relabelSaving = ref(false)

function openRelabel() {
  const rec = selectedRecording.value
  if (!rec) return
  relabelForm.value = {
    subject: rec.subject === '-' ? '' : rec.subject,
    session: rec.session || '',
    task: rec.task === '-' ? '' : rec.task,
    run: rec.run || '',
  }
  relabelError.value = ''
  relabelEditing.value = true
}

function cancelRelabel() {
  relabelEditing.value = false
  relabelError.value = ''
}

async function saveRelabel() {
  const rec = selectedRecording.value
  if (!rec) return
  relabelSaving.value = true
  relabelError.value = ''
  try {
    await relabelRecording(rec, {
      subject: relabelForm.value.subject,
      session: relabelForm.value.session || null,
      task: relabelForm.value.task,
      run: relabelForm.value.run || null,
    })
    relabelEditing.value = false
    await loadSelectedAssetRecordings()
    const updated = selectedRecording.value
    if (updated) {
      await loadRecordingVersions(updated, true)
      await loadRecordingFiles(updated, true)
    }
  } catch (err: any) {
    relabelError.value = extractRelabelError(err)
  } finally {
    relabelSaving.value = false
  }
}

function extractRelabelError(err: any): string {
  return extractDetailError(err, '调整归类失败，请稍后重试')
}

function extractDetailError(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  if (detail && typeof detail === 'object' && detail.message) return detail.message
  if (typeof detail === 'string') return detail
  return fallback
}

// ===== 删除 / 排除记录（两步内联确认，不可恢复）=====
const deleteConfirming = ref(false)
const deleting = ref(false)
const deleteError = ref('')

async function confirmDelete() {
  const rec = selectedRecording.value
  if (!rec) return
  deleting.value = true
  deleteError.value = ''
  try {
    await deleteRecording(rec)
    selectedRecordingId.value = null
    deleteConfirming.value = false
    await handleUploaded() // 与上传后同一刷新：重载资产计数 + 记录列表
  } catch (err: any) {
    deleteError.value = extractDetailError(err, '删除失败，请稍后重试')
  } finally {
    deleting.value = false
  }
}

// ===== 质控（mock）=====
const qaRunning = ref(false)
const qaReviewing = ref(false)
const qaError = ref('')

const selectedQa = computed(() =>
  selectedRecordingId.value ? recordingQaById.value[selectedRecordingId.value] : undefined,
)
const selectedQaReport = computed(() => selectedQa.value?.qa_report || null)
const selectedQaHasReport = computed(() => Boolean(selectedQa.value?.has_report || selectedQaReport.value))
const selectedQaReviewed = computed(() => Boolean(selectedQaReport.value?.human_review?.conclusion))
const qaHasBlocking = computed(() => (selectedQaReport.value?.summary?.blocking_issues?.length || 0) > 0)
const qaWarnings = computed(() => selectedQaReport.value?.summary?.warnings || [])
const qaBlocking = computed(() => selectedQaReport.value?.summary?.blocking_issues || [])
// 状态优先用质控接口返回的最新值，回退到记录行
const qaStatusValue = computed(() => selectedQa.value?.qa_status ?? selectedRecording.value?.qaStatus ?? null)
const qaStatusText = computed(() => getQaStatusLabel(qaStatusValue.value))
const qaStatusBadge = computed(() => getQaStatusClass(qaStatusValue.value))
const qaReviewText = computed(() => {
  const c = selectedQaReport.value?.human_review?.conclusion
  if (c === 'accept') return '已通过'
  if (c === 'reject') return '已驳回'
  if (c === 'hold') return '已暂存'
  return ''
})

async function onRunQa() {
  const rec = selectedRecording.value
  if (!rec) return
  qaRunning.value = true
  qaError.value = ''
  try {
    await runRecordingQa(rec)
  } catch (err: any) {
    qaError.value = extractDetailError(err, '运行质控失败，请稍后重试')
  } finally {
    qaRunning.value = false
  }
}

async function onReviewQa(conclusion: 'accept' | 'reject') {
  const rec = selectedRecording.value
  if (!rec) return
  qaReviewing.value = true
  qaError.value = ''
  try {
    await reviewRecordingQa(rec, { conclusion })
  } catch (err: any) {
    qaError.value = extractDetailError(err, '复核质控失败，请稍后重试')
  } finally {
    qaReviewing.value = false
  }
}
</script>
