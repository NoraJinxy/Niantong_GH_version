<template>
  <WorkbenchShell active-key="ica" active-top-key="analysis">
    <div class="ica-shell">
      <HotkeyHelp v-if="helpOpen" :groups="helpGroups" :mouse-hints="mouseHints" @close="helpOpen = false" />
      <PerfBadge :perf="probe.perf" />
      <!-- 顶部工具条 -->
      <div class="ica-toolbar">
        <h1 class="page__title ica-title" style="font-size: 22px; margin: 0">
          <IconLine name="brain" :size="24" /> ICA 成分审核
        </h1>
        <span v-if="isLive && overview" class="muted text-sm">
          {{ currentDatasetLabel }} · {{ overview.method || 'ICA' }} · {{ overview.n_components }} 成分 · {{ overview.n_channels }} 通道
          <template v-if="overview.total_variance_explained != null">
            · 解释方差 {{ overview.total_variance_explained.toFixed(1) }}%
          </template>
          <template v-if="labelsLoading"> · <span class="ica-live">标注加载中…</span></template>
          <template v-else-if="overview.iclabel_available"> · ICLabel 已自动标注</template>
        </span>
        <span class="ica-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实 ICA 数据' : '查看模式' }}</span>
        <div style="flex: 1"></div>
        <button type="button" class="btn btn--sm" @click="helpOpen = true" title="操作与快捷键（快捷键 ?）">🖱 操作提示</button>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="load">刷新</button>
        <!-- 应用决策（原底栏移到顶栏，常驻不占画布高度） -->
        <template v-if="isLive">
          <span class="ica-tb-div"></span>
          <span class="muted text-sm" :class="{ 'ica-rm-count': totalRemoveCount }">
            待去除 {{ removeList.length }}<template v-if="datasetOptions.length > 1"> / 合计 {{ totalRemoveCount }}</template>
          </span>
          <span v-if="applyMsg" class="ica-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</span>
          <button v-if="applyDone" class="btn btn--sm" @click="returnToPipeline">返回工作流</button>
          <span v-else-if="!jobContext" class="muted text-sm" title="在工作流「ICA Apply」节点处打开才能提交">查看模式</span>
          <template v-else>
            <button class="btn btn--sm" :disabled="applying" @click="returnToPipeline">取消</button>
            <button class="btn btn--primary btn--sm" :disabled="!canApply" @click="submitAndReturn" title="应用剔除并续跑工作流（Ctrl+Enter）">
              <AppIcon name="check" :size="15" /> {{ applying ? '提交中…' : '应用并继续' }}
            </button>
          </template>
        </template>
      </div>

      <!-- 空态 / 错误 / 加载 -->
      <div v-if="!isLive" class="ica-empty ica-empty--full">
        <AppIcon name="brain" :size="40" />
        <p class="ica-empty-title">从结果选择一个 ICA 结果查看成分</p>
        <p class="muted text-sm">
          在工作流运行「Compute ICA」节点后，于结果页或 ICA Apply 节点处打开本页，
          即可看到真实的成分地形图、时域、频谱与去除前后对比。
        </p>
      </div>
      <div v-else-if="error" class="ica-empty ica-empty--full is-error">
        <AppIcon name="warning" :size="32" />
        <p class="ica-empty-title">{{ error }}</p>
        <button class="btn btn--sm" :disabled="loading" @click="load">重试</button>
      </div>
      <div v-else-if="loading && !components.length" class="ica-empty ica-empty--full">
        <p class="muted">加载 ICA 成分中…</p>
      </div>

      <!-- 三区主体：左·数据/通道切换 / 中·验证 / 右·成分墙（无底栏，应用决策在顶栏） -->
      <template v-else>
        <div class="ica-main">
          <!-- 左·数据集 / 通道：观察页同款紧凑列表 -->
          <section class="ica-left">
            <div class="ica-picker">
              <section class="ica-pick-sec">
                <div class="ica-sec-head ica-sec-head--sub">
                  <span>数据集</span>
                  <span class="muted text-sm">{{ datasetOptions.length ? `${datasetOptions.findIndex((item) => item.key === selectedDatasetKey) + 1}/${datasetOptions.length}` : '—' }}</span>
                </div>
                <div class="ica-pick-list">
                  <button
                    v-for="item in datasetOptions"
                    :key="item.key"
                    class="ica-pick-row"
                    :class="{ 'is-on': item.key === selectedDatasetKey }"
                    :title="item.title"
                    @click="selectDataset(item.key)"
                  >
                    <span class="ica-pick-dot"></span>
                    <span class="ica-pick-name">{{ item.label }}</span>
                    <span v-if="item.componentCount" class="ica-pick-tag">{{ item.componentCount }} IC</span>
                  </button>
                </div>
              </section>
              <section class="ica-pick-sec">
                <div class="ica-sec-head ica-sec-head--sub">
                  <span>通道</span>
                  <span class="muted text-sm">{{ cmpChannel || '—' }}</span>
                </div>
                <div class="ica-pick-list ica-pick-list--channels">
                  <button
                    v-for="ch in overview?.ch_names || []"
                    :key="ch"
                    class="ica-pick-row"
                    :class="{ 'is-on': ch === cmpChannel }"
                    @click="cmpChannel = ch"
                  >
                    <span class="ica-pick-dot"></span>
                    <span class="ica-pick-name text-mono">{{ ch }}</span>
                  </button>
                </div>
              </section>
            </div>
          </section>

          <!-- 中：整体去除前后对比（主视图）+ 下方详情双栏 -->
          <section class="ica-center">
            <div class="ica-center-head">
              <div class="ica-center-title">
                <span class="ica-chart-title">整体去除前后对比</span>
                <span class="ica-chart-meta">· {{ currentDatasetLabel }}</span>
                <span v-if="cmpChannel" class="ica-chart-meta">· 通道 {{ cmpChannel }}</span>
              </div>
              <div class="ica-center-controls">
                <div class="ica-windowseg" role="group" aria-label="显示时长">
                  <button type="button" :class="{ 'is-on': previewWindowMode === 'short' }" @click="setPreviewWindowMode('short')">10s</button>
                  <button type="button" :class="{ 'is-on': previewWindowMode === 'full' }" @click="setPreviewWindowMode('full')">全部</button>
                </div>
                <button v-if="isZoomed" class="btn btn--sm btn--ghost" @click="resetZoom">复位视图</button>
                <span v-if="previewLoading" class="ica-live">● 刷新中</span>
                <span v-else-if="preview?.has_comparison && removeList.length && preview.variance_reduction != null" class="ica-vr">
                  方差 ↓ {{ preview.variance_reduction }}%
                </span>
              </div>
            </div>
            <div class="ica-cmp-body">
              <div v-if="preview?.has_comparison" class="ica-cmp-host">
                <TimeCourseCanvas
                  :data="previewData"
                  :series="cmpSeries"
                  x-label="时间 (s)"
                  y-label="µV"
                  show-legend
                  pan-on-drag
                  :view-min="viewMin"
                  :view-max="viewMax"
                  :x-tick-step="timeAxisStep"
                  :amp-scale="cmpAmp"
                  @zoom="onZoom"
                  @amp="cmpAmp = $event"
                />
                <div class="ica-zoom-hint">拖动平移 · 滚轮缩放时间 · Ctrl+滚轮缩放幅度</div>
              </div>
              <div v-else class="ica-cmp-empty muted text-sm">
                <AppIcon name="brain" :size="32" />
                <p>{{ cmpChannel ? '加载对比波形…' : '选择一个对比通道' }}</p>
              </div>
            </div>

            <div class="ica-detail-row">
              <section class="ica-detail-panel">
                <div class="ica-panel-cap">
                  <span class="ica-chart-title">选中成分时域激活（源）</span>
                  <span v-if="activeComp" class="ica-chart-meta">· {{ activeComp.label }}</span>
                </div>
                <div class="ica-panel-host">
                  <TimeCourseCanvas
                    v-if="activeComp"
                    :data="tcData"
                    :series="tcSeries"
                    x-label="时间 (s)"
                    y-label="a.u."
                    :show-legend="false"
                    pan-on-drag
                    :view-min="viewMin"
                    :view-max="viewMax"
                    :x-tick-step="timeAxisStep"
                    :amp-scale="tcAmp"
                    :loading="detailLoading"
                    @zoom="onZoom"
                    @amp="tcAmp = $event"
                  />
                  <div v-else class="ica-panel-empty muted text-sm">点击右侧成分查看其时域激活</div>
                </div>
              </section>
              <section class="ica-detail-panel">
                <div class="ica-panel-cap">
                  <span class="ica-chart-title">Welch 频谱</span>
                  <template v-if="activeComp">
                    <span class="ica-chart-meta">· {{ activeComp.label }}</span>
                    <span v-if="activeComp.iclabel" class="ica-chart-meta">
                      · {{ activeComp.iclabel.label_cn }}<template v-if="activeComp.iclabel.probability != null"> {{ Math.round(activeComp.iclabel.probability * 100) }}%</template>
                    </span>
                    <span v-if="activeComp.explained_variance != null" class="ica-chart-meta">· 方差 {{ activeComp.explained_variance.toFixed(1) }}%</span>
                  </template>
                  <span v-else class="ica-chart-meta">· 选择成分看频谱</span>
                </div>
                <div class="ica-panel-host">
                  <TimeCourseCanvas v-if="activeComp" :data="specData" :series="specSeries" x-label="Hz" y-label="dB" :show-legend="false" use-spline :loading="detailLoading" />
                  <div v-else class="ica-panel-empty muted text-sm">选择成分看频谱</div>
                </div>
              </section>
            </div>
          </section>

          <!-- 右·遍历挑选：成分墙（扫描 / 点选 / 标记剔除） -->
          <aside class="ica-right">
            <div class="ica-sec-head">
              <span>成分 · {{ components.length }}</span>
              <div class="ica-sortseg" role="group" aria-label="成分排序">
                <button type="button" :class="{ 'is-on': sortMode === 'index' }" @click="sortMode = 'index'">编号</button>
                <button type="button" :class="{ 'is-on': sortMode === 'iclabel' }" @click="sortMode = 'iclabel'">伪迹概率 ↓</button>
              </div>
            </div>
            <div class="ica-sec-hint">单击看详情 · 双击 / 勾选 = 标记剔除（红 = 已标记）· 更多见「操作提示」</div>
            <div class="ica-active-topo">
              <div class="ica-active-topo-head">
                <span class="ica-chart-title">选中成分地形图</span>
                <template v-if="activeComp">
                  <span class="ica-chart-meta">· {{ activeComp.label }}</span>
                  <span v-if="activeComp.iclabel" class="ica-chart-meta">
                    · {{ activeComp.iclabel.label_cn }}<template v-if="activeComp.iclabel.probability != null"> {{ Math.round(activeComp.iclabel.probability * 100) }}%</template>
                  </span>
                </template>
                <span v-else class="ica-chart-meta">· 点击下方成分</span>
              </div>
              <TopoStrip v-if="activeComp" bare :cells="activeTopoCells" :vmax="1" subtitle="" unit="" lo-label="−" hi-label="+" />
              <div v-else class="ica-active-topo-empty muted text-sm">点击下方成分查看大图</div>
            </div>
            <div class="ica-wall-body">
              <TopoStrip
                layout="grid"
                selectable
                checkable
                :grid-cols="wallCols"
                :cells="componentCells"
                :vmax="1"
                :active-seg="selectedIndex"
                subtitle=""
                unit=""
                lo-label="−"
                hi-label="+"
                @cell-click="onCellClick"
                @cell-dblclick="toggleRemove"
                @cell-check="toggleRemove"
              />
            </div>
          </aside>
        </div>
      </template>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { dataApi } from '@/api/client'
import { pipelineApi } from '@/api/pipelines'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import { useIcaComparison } from '@/composables/observe/useIcaComparison'
import { useReviewerHandoff } from '@/composables/pipeline/useReviewerHandoff'
import { useTieredFetch } from '@/composables/observe/useTieredFetch'
import { usePerfProbe } from '@/composables/observe/usePerfProbe'
import PerfBadge from '@/components/observe/PerfBadge.vue'
import { useObserveHotkeys, type HotkeyDef } from '@/composables/observe/useObserveHotkeys'
import HotkeyHelp from '@/components/observe/HotkeyHelp.vue'
import { compactDatasetLabels } from '@/composables/observe/outputLabels'
import type { PipelineInteraction, StudyOutput } from '@/types'

// ---- 后端返回结构（对齐 app/pipeline/ica_inspect.py） ----
interface TopoPoint { name: string; x: number; y: number; weight: number }
interface IcaLabel { category: string; label_cn: string; probability: number | null; suggested: boolean }
interface IcaComponent {
  index: number
  label: string
  vmax: number
  explained_variance: number | null
  topography: TopoPoint[]
  top_channels: string[]
  has_positions: boolean
  iclabel?: IcaLabel | null
}
interface IcaComponentsResponse {
  n_components: number
  method: string | null
  exclude: number[]
  ch_names: string[]
  n_channels: number
  total_variance_explained: number | null
  study_output_id: string
  has_source_raw: boolean
  iclabel_available?: boolean
  suggested_exclude?: number[]
  labels_pending?: boolean // 快路径标记：true→去拉 /labels 补方差+ICLabel
  components: IcaComponent[]
}
// /labels 慢路径（异步补）：每成分方差% + ICLabel 标签 + 建议剔除
interface IcaLabelsResponse {
  has_source_raw: boolean
  iclabel_available: boolean
  total_variance_explained: number | null
  suggested_exclude: number[]
  variances: Record<string, number>
  iclabel: Record<string, IcaLabel>
}
interface IcaDetail {
  index: number
  label: string
  explained_variance: number | null
  sfreq: number
  timecourse: { times: number[]; values: number[] }
  spectrum: { frequencies: number[]; power_db: number[]; fmax: number }
}
interface IcaInteractionDataset {
  dataset_id?: string | null
  source_dataset_id?: string | null
  ica_artifact_id?: string | null
  data_info?: Record<string, unknown> | null
  ica_info?: Record<string, unknown> | null
  components?: IcaComponent[]
}
interface IcaDatasetOption {
  key: string
  outputId: string
  label: string
  title: string
  datasetId?: string | null
  sourceDatasetId?: string | null
  componentCount?: number | null
}

// TopoStrip 的 cell 形状（与组件内 TopoCell 结构兼容）
interface TopoCell {
  seg: number
  label: string
  color: string
  points: { name: string; x: number; y: number; value: number }[] | null
  sub?: string
  marked?: boolean
}

// 成分墙配色：中性灰=保留、红=标记剔除（选中态由 TopoStrip 自身的 active 环表达）。
const NEUTRAL = '#C4CCD8'
const DANGER = '#EF4444'
const PRIMARY = '#3F5E8F' // elys 招牌蓝（画布内硬编码，与观察页一致）
const ACCENT = '#7A5AA6' // 频谱用紫
const COMPARE_ORIGINAL = '#D55E00' // 原始：暖橙，与去除后蓝形成强对比
const COMPARE_CLEAN = '#0072B2' // 去除后：色盲友好深蓝

// 去除前后对比 / 时域激活载入的时窗（秒）：默认看 10s；“全部”交给后端按真实长度截断并下采样。
const SHORT_WINDOW_SECONDS = 10
const FULL_WINDOW_SECONDS = 86400

const route = useRoute()
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return (raw as string | null) ?? fallback
}

const studyId = qstr('studyId') || qstr('study')
const routeOutputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
const outputId = routeOutputIds[0] || ''
const probe = usePerfProbe('ica') // 临时性能探针，测完删

// ICA 成分详情(时程+频谱，信号派生、不可变)三级缓存：重点击同一成分秒回。键用 outputId+成分序号。
// 注：成分网格(components)含可变的 exclude 决策，不进 IDB（避免陈旧命中显示旧决策），且本就小、gzip 够。
const icaDetailFetch = useTieredFetch<IcaDetail>({
  namespace: 'ica_detail',
  endpoint: (p) => `/studies/${studyId}/outputs/${String(p.outputId)}/ica-components/${String(p.index)}`,
  keyOf: (p) => `${studyId}::${String(p.outputId)}::${String(p.index)}::${String(p.max_seconds)}`,
})
// 交互上下文（从工作流 waiting_user_input 的 ICA Apply 节点打开时带上），用于提交剔除决策
const executionId = qstr('executionId') || qstr('execution_id')
const jobId = qstr('jobId') || qstr('job_id')
const decisionVersion = Number(qstr('decisionVersion') || qstr('decision_version') || '0')

const datasetOptions = ref<IcaDatasetOption[]>([])
const selectedDatasetKey = ref('')
const excludedByOutput = ref<Record<string, number[]>>({})
const globalDecisionExcluded = ref<number[] | null>(null)
const currentDataset = computed(() => datasetOptions.value.find((item) => item.key === selectedDatasetKey.value) || datasetOptions.value[0] || null)
const currentOutputId = computed(() => currentDataset.value?.outputId || outputId)
const currentDatasetLabel = computed(() => currentDataset.value?.label || '当前数据集')

const isLive = computed(() => Boolean(studyId && currentOutputId.value))
const jobContext = computed(() => Boolean(studyId && executionId && jobId && decisionVersion > 0))

const loading = ref(false)
const labelsLoading = ref(false) // 阶段二（方差+ICLabel）异步加载中
let loadSeq = 0
const error = ref('')
const overview = ref<IcaComponentsResponse | null>(null)
const components = ref<IcaComponent[]>([])

const selectedIndex = ref<number | null>(null)
const detail = ref<IcaDetail | null>(null)
const detailLoading = ref(false)
let detailSeq = 0

// 前端视觉缩放（与三观察页同一套手感）：viewMin/Max=可见时间窗（两图共享，X 同步），*Amp=各自幅度系数。
const previewWindowMode = ref<'short' | 'full'>('short')
const requestedSeconds = computed(() => (previewWindowMode.value === 'full' ? FULL_WINDOW_SECONDS : SHORT_WINDOW_SECONDS))
const defaultViewMin = computed<number | null>(() => (previewWindowMode.value === 'short' ? 0 : null))
const defaultViewMax = computed<number | null>(() => (previewWindowMode.value === 'short' ? SHORT_WINDOW_SECONDS : null))
const viewMin = ref<number | null>(defaultViewMin.value)
const viewMax = ref<number | null>(defaultViewMax.value)
const cmpAmp = ref(1)
const tcAmp = ref(1)
const isZoomed = computed(() =>
  viewMin.value !== defaultViewMin.value
  || viewMax.value !== defaultViewMax.value
  || Math.abs(cmpAmp.value - 1) > 1e-3
  || Math.abs(tcAmp.value - 1) > 1e-3,
)
function onZoom(v: { min: number; max: number } | null) {
  viewMin.value = v ? v.min : null
  viewMax.value = v ? v.max : null
}
function resetZoom() {
  viewMin.value = defaultViewMin.value
  viewMax.value = defaultViewMax.value
  cmpAmp.value = 1
  tcAmp.value = 1
}
function setPreviewWindowMode(mode: 'short' | 'full') {
  if (previewWindowMode.value === mode) return
  previewWindowMode.value = mode
  cmpSeconds.value = requestedSeconds.value
  resetZoom()
  if (selectedIndex.value != null) void selectComponent(selectedIndex.value)
}

// 中心「整体去除前后对比」编排：剔除集是唯一事实源，墙/清单/应用都从这里派生。
const studyIdRef = ref(studyId)
const outputIdRef = ref(currentOutputId.value)
const {
  excludedSet,
  preview,
  previewLoading,
  channel: cmpChannel,
  maxSeconds: cmpSeconds,
  setExcluded,
  clearPreview,
} = useIcaComparison(studyIdRef, outputIdRef, () => isLive.value)
cmpSeconds.value = requestedSeconds.value

const activeComp = computed(() => components.value.find((c) => c.index === selectedIndex.value) || null)
const removeList = computed(() => [...excludedSet.value].sort((a, b) => a - b))
const allExcludedByOutput = computed<Record<string, number[]>>(() => {
  const outputIds = datasetOptions.value.length ? datasetOptions.value.map((item) => item.outputId) : [currentOutputId.value].filter(Boolean)
  const current = currentOutputId.value
  const out: Record<string, number[]> = {}
  for (const id of outputIds) {
    if (!id) continue
    out[id] = id === current
      ? removeList.value
      : [...(Object.prototype.hasOwnProperty.call(excludedByOutput.value, id) ? excludedByOutput.value[id] : (globalDecisionExcluded.value || []))]
  }
  return out
})
const totalRemoveCount = computed(() => Object.values(allExcludedByOutput.value).reduce((sum, items) => sum + items.length, 0))

// 「应用并返回」收尾（提交 decision→续跑→router.back 回工作流），与伪迹审核页共用同一套。
const { applying, applyMsg, applyError, applyDone, submitAndReturn, returnToPipeline } = useReviewerHandoff({
  studyId, executionId, jobId,
  decisionVersion: () => decisionVersion,
  buildBody: () => ({
    excluded_components: removeList.value,
    excluded_components_by_dataset: allExcludedByOutput.value,
  }),
  summary: () => (datasetOptions.value.length > 1
    ? `${datasetOptions.value.length} 个数据集共剔除 ${totalRemoveCount.value} 个成分标记`
    : `剔除 ${removeList.value.length} 个成分`),
})
const canApply = computed(() => jobContext.value && !applying.value)

function setCurrentExcluded(next: Set<number>) {
  const output = currentOutputId.value
  const list = [...next].sort((a, b) => a - b)
  if (output) {
    excludedByOutput.value = { ...excludedByOutput.value, [output]: list }
  }
  setExcluded(new Set(list))
}
function hasStoredExcluded(output: string): boolean {
  return Object.prototype.hasOwnProperty.call(excludedByOutput.value, output) || globalDecisionExcluded.value !== null
}
function storedExcluded(output: string, fallback: number[] = []): number[] {
  if (Object.prototype.hasOwnProperty.call(excludedByOutput.value, output)) return [...(excludedByOutput.value[output] || [])]
  if (globalDecisionExcluded.value !== null) return [...globalDecisionExcluded.value]
  return [...fallback]
}

function isRemoved(index: number): boolean {
  return excludedSet.value.has(index)
}
function toggleRemove(index: number) {
  const next = new Set(excludedSet.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  setCurrentExcluded(next)
}
// 单成分权重 → TopoStrip 电极点：除以该成分自身 vmax 归一到 [-1,1]，配合 TopoStrip vmax=1 实现"每成分独立归一"。
function cellPoints(c: IcaComponent): TopoCell['points'] {
  if (!c.has_positions) return null
  const m = c.vmax > 0 ? c.vmax : 1
  return c.topography.map((p) => ({ name: p.name, x: p.x, y: p.y, value: p.weight / m }))
}

// 成分墙排序：默认「编号」(稳定 native 顺序)；可切「伪迹概率↓」(ICLabel 判为伪迹且置信度高的顶上来，
// 对审核最有用)。去掉「方差↓」——ICA 不按方差排是固有属性，且高方差≠是伪迹(α 也高方差却要留)，对挑伪迹无益。
const sortMode = ref<'index' | 'iclabel'>('index')
function artifactScore(c: IcaComponent): number {
  const l = c.iclabel
  if (!l || l.category === 'brain' || l.category === 'other' || l.probability == null) return -1
  return l.probability
}
const sortedComponents = computed(() => {
  const list = [...components.value]
  if (sortMode.value === 'iclabel') {
    list.sort((a, b) => artifactScore(b) - artifactScore(a))
  }
  return list
})

// 成分墙：每成分一格插值地形图缩略图，颜色/标记态由剔除集驱动，sub 显 ICLabel 标签+概率（无则显方差%）。
function cellSub(c: IcaComponent): string {
  const l = c.iclabel
  if (l && l.probability != null) return `${l.label_cn} ${Math.round(l.probability * 100)}%`
  if (l) return l.label_cn
  return c.explained_variance != null ? `方差 ${c.explained_variance.toFixed(1)}%` : ''
}
// 成分墙固定 3 列，右侧加宽后让每张地形图自动放大。
const wallCols = computed(() => 3)
const componentCells = computed<TopoCell[]>(() =>
  sortedComponents.value.map((c) => {
    const removed = excludedSet.value.has(c.index)
    return {
      seg: c.index,
      label: `IC ${c.index}`,
      color: removed ? DANGER : NEUTRAL,
      marked: removed,
      sub: cellSub(c),
      points: cellPoints(c),
    }
  }),
)
const activeTopoCells = computed<TopoCell[]>(() => {
  const c = activeComp.value
  if (!c) return []
  const removed = excludedSet.value.has(c.index)
  return [{
    seg: c.index,
    label: c.label,
    color: removed ? DANGER : PRIMARY,
    marked: removed,
    sub: cellSub(c),
    points: cellPoints(c),
  }]
})

// 时域激活 + 频谱底部并列显示（喂 TimeCourseCanvas：data=[x, ...ys]）
const tcSeries = [{ name: '激活', color: PRIMARY }]
const specSeries = [{ name: '功率', color: ACCENT }]
const tcData = computed<number[][]>(() => (detail.value ? [detail.value.timecourse.times, detail.value.timecourse.values] : [[], []]))
const specData = computed<number[][]>(() => (detail.value ? [detail.value.spectrum.frequencies, detail.value.spectrum.power_db] : [[], []]))

// 中心整体对比：原始（橙） vs 去除后（蓝），同轴叠加；后端给 Volts，×1e6 换 µV。
const cmpSeries = [
  { name: '原始', color: COMPARE_ORIGINAL },
  { name: '去除后', color: COMPARE_CLEAN },
]
const previewData = computed<number[][]>(() => {
  const p = preview.value
  if (!p || !p.has_comparison || !p.times || !p.original || !p.filtered) return [[], []]
  return [p.times, p.original.map((v) => v * 1e6), p.filtered.map((v) => v * 1e6)]
})

function niceTimeAxisStep(duration: number): number {
  if (!Number.isFinite(duration) || duration <= 0) return 1
  const raw = duration / 5
  if (raw <= 1) return 1
  let step = Math.round(raw)
  if (step > 50) return Math.max(10, Math.round(step / 10) * 10)
  if (step > 10) return Math.max(5, Math.round(step / 5) * 5)
  if (step > 2 && step % 2 === 1) step += 1
  return Math.max(1, step)
}
const timeAxisStep = computed(() => {
  if (viewMin.value != null && viewMax.value != null && viewMax.value > viewMin.value) {
    return niceTimeAxisStep(viewMax.value - viewMin.value)
  }
  const xs = previewData.value[0]?.length ? previewData.value[0] : tcData.value[0]
  if (xs && xs.length >= 2) {
    return niceTimeAxisStep(Math.max(0, xs[xs.length - 1] - xs[0]))
  }
  return niceTimeAxisStep(requestedSeconds.value === FULL_WINDOW_SECONDS ? SHORT_WINDOW_SECONDS : requestedSeconds.value)
})

function normalizeIndexList(value: unknown): number[] {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item >= 0))].sort((a, b) => a - b)
}
function normalizeExcludedMap(value: unknown): Record<string, number[]> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  const out: Record<string, number[]> = {}
  for (const [key, items] of Object.entries(value as Record<string, unknown>)) {
    const text = String(key || '').trim()
    if (text) out[text] = normalizeIndexList(items)
  }
  return out
}
function idTail(value?: string | null): string {
  const text = String(value || '').trim()
  return text ? text.slice(0, 8) : ''
}
function taskPart(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return ''
  return text.startsWith('task-') ? text : `task-${text}`
}
function dataInfoText(info?: Record<string, unknown> | null): string {
  if (!info) return ''
  return [
    info.bids_subject_id || info.subject,
    info.session,
    taskPart(info.task as string | undefined),
    info.run,
  ].map((item) => String(item || '').trim()).filter(Boolean).join('_')
}
function outputText(meta: StudyOutput | null, fallback: IcaInteractionDataset | null, index: number): string {
  const parts = meta
    ? [meta.bids_subject_id || meta.subject_id || '', meta.session || '', taskPart(meta.task), meta.run_label || '']
        .map((item) => String(item || '').trim())
        .filter(Boolean)
    : []
  return parts.join('_')
    || dataInfoText(fallback?.data_info)
    || meta?.display_name
    || `数据集 ${index + 1}${idTail(fallback?.source_dataset_id || fallback?.dataset_id) ? ` · ${idTail(fallback?.source_dataset_id || fallback?.dataset_id)}` : ''}`
}
function applyInteractionDecision(interaction: PipelineInteraction) {
  const decision = interaction.decision
  if (!decision) return
  const byDataset = normalizeExcludedMap(decision.excluded_components_by_dataset)
  if (Object.keys(byDataset).length) excludedByOutput.value = { ...excludedByOutput.value, ...byDataset }
  const global = normalizeIndexList(decision.excluded_components)
  globalDecisionExcluded.value = global.length || !Object.keys(byDataset).length ? global : globalDecisionExcluded.value
}
function interactionDatasets(interaction: PipelineInteraction): IcaInteractionDataset[] {
  const preview = interaction.preview_json || {}
  const raw = Array.isArray(preview.datasets) ? preview.datasets : []
  return raw.filter((item): item is IcaInteractionDataset => Boolean(item && typeof item === 'object' && (item as IcaInteractionDataset).ica_artifact_id))
}
async function loadDatasetOptions() {
  let raw: IcaInteractionDataset[] = []
  if (jobContext.value) {
    try {
      const res = await pipelineApi.getNodeInteraction(studyId, executionId, jobId)
      applyInteractionDecision(res.data)
      raw = interactionDatasets(res.data)
    } catch {
      raw = []
    }
  }
  if (!raw.length) {
    raw = (routeOutputIds.length ? routeOutputIds : [outputId]).filter(Boolean).map((id) => ({ ica_artifact_id: id }))
  }
  const seen = new Set<string>()
  raw = raw.filter((item) => {
    const id = String(item.ica_artifact_id || '').trim()
    if (!id || seen.has(id)) return false
    seen.add(id)
    return true
  })
  const metas = await Promise.all(raw.map(async (item) => {
    try {
      const { data } = await pipelineApi.getStudyOutput(studyId, String(item.ica_artifact_id))
      return data
    } catch {
      return null
    }
  }))
  const fullLabels = raw.map((item, index) => outputText(metas[index], item, index))
  const shortLabels = compactDatasetLabels(fullLabels)
  datasetOptions.value = raw.map((item, index) => {
    const output = String(item.ica_artifact_id)
    return {
      key: output,
      outputId: output,
      label: shortLabels[index] || fullLabels[index] || `数据集 ${index + 1}`,
      title: fullLabels[index] || shortLabels[index] || output,
      datasetId: item.dataset_id || null,
      sourceDatasetId: item.source_dataset_id || null,
      componentCount: Array.isArray(item.components) ? item.components.length : null,
    }
  })
  const keys = datasetOptions.value.map((item) => item.key)
  selectedDatasetKey.value = keys.includes(selectedDatasetKey.value)
    ? selectedDatasetKey.value
    : (keys.includes(outputId) ? outputId : (keys[0] || ''))
}

// 阶段一（快）：当前数据集成分地形图网格——秒出，不等 raw / ICLabel。
async function load() {
  if (!studyId || (!outputId && !jobContext.value)) return
  await loadDatasetOptions()
  await loadCurrentOutput()
}

async function loadCurrentOutput() {
  const activeOutput = currentOutputId.value
  if (!studyId || !activeOutput) return
  const mySeq = ++loadSeq
  outputIdRef.value = activeOutput
  clearPreview()
  detail.value = null
  labelsLoading.value = false
  loading.value = true
  error.value = ''
  try {
    const res = await dataApi.get<IcaComponentsResponse>(`/studies/${studyId}/outputs/${activeOutput}/ica-components`)
    if (mySeq !== loadSeq) return
    overview.value = res.data
    components.value = res.data.components || []
    probe.done('数据'); probe.paint(); probe.log() // 临时探针
    if (res.data.ch_names?.length && (!cmpChannel.value || !res.data.ch_names.includes(cmpChannel.value))) {
      cmpChannel.value = res.data.ch_names[0]
    }
    const initialExcluded = storedExcluded(activeOutput, res.data.exclude || [])
    if (initialExcluded.length && !hasStoredExcluded(activeOutput)) {
      excludedByOutput.value = { ...excludedByOutput.value, [activeOutput]: initialExcluded }
    }
    setExcluded(new Set(initialExcluded))
    document.title = `ICA 审核 · ${currentDatasetLabel.value} · ${res.data.n_components} 成分 — 念析`
    if (components.value.length) {
      void selectComponent(selectedIndex.value ?? components.value[0].index)
    }
    // 阶段二（慢，异步）：方差 + ICLabel 标签 + 默认勾选——网格已显示，不挡首屏。
    if (res.data.labels_pending !== false) void loadLabels(activeOutput, mySeq)
  } catch (err: unknown) {
    if (mySeq !== loadSeq) return
    error.value = describeError(err)
    components.value = []
    overview.value = null
  } finally {
    if (mySeq === loadSeq) loading.value = false
  }
}

// 阶段二：拉方差 + ICLabel，合并进已显示的成分网格；无已存决策则套用 ICLabel 建议作默认勾选。
async function loadLabels(activeOutput = currentOutputId.value, parentSeq = loadSeq) {
  labelsLoading.value = true
  try {
    const res = await dataApi.get<IcaLabelsResponse>(`/studies/${studyId}/outputs/${activeOutput}/ica-components/labels`)
    if (parentSeq !== loadSeq || activeOutput !== currentOutputId.value) return
    const vmap = res.data.variances || {}
    const lmap = res.data.iclabel || {}
    components.value = components.value.map((c) => ({
      ...c,
      explained_variance: vmap[String(c.index)] ?? c.explained_variance ?? null,
      iclabel: lmap[String(c.index)] ?? c.iclabel ?? null,
    }))
    if (overview.value) {
      overview.value = {
        ...overview.value,
        iclabel_available: res.data.iclabel_available,
        total_variance_explained: res.data.total_variance_explained,
      }
    }
    if (!hasStoredExcluded(activeOutput) && (res.data.suggested_exclude || []).length) {
      excludedByOutput.value = { ...excludedByOutput.value, [activeOutput]: res.data.suggested_exclude }
      setExcluded(new Set(res.data.suggested_exclude))
    }
  } catch {
    /* 标签加载失败：网格照常用，只是没方差 / 标签（best-effort） */
  } finally {
    if (parentSeq === loadSeq && activeOutput === currentOutputId.value) labelsLoading.value = false
  }
}

async function selectDataset(key: string) {
  if (!key || key === selectedDatasetKey.value) return
  selectedDatasetKey.value = key
  selectedIndex.value = null
  resetZoom()
  await loadCurrentOutput()
}

// 单击成分 → 拉详情（时域激活 + 频谱；去除前后对比交给中心视图，这里不再重复算，更快）
async function selectComponent(index: number) {
  const activeOutput = currentOutputId.value
  if (!activeOutput) return
  selectedIndex.value = index
  const myId = ++detailSeq
  detailLoading.value = true
  try {
    const { data } = await icaDetailFetch.fetch({ outputId: activeOutput, index, max_seconds: requestedSeconds.value })
    if (myId !== detailSeq || activeOutput !== currentOutputId.value) return
    detail.value = data
  } catch {
    if (myId === detailSeq) detail.value = null
  } finally {
    if (myId === detailSeq) detailLoading.value = false
  }
}

function onCellClick(index: number) {
  selectComponent(index)
}

// ---------- 键盘审阅 + 快捷键（共享 useObserveHotkeys 引擎；按 ? 唤出速查卡）----------
function selectNextComponent() {
  const list = sortedComponents.value
  if (!list.length) return
  const cur = list.findIndex((c) => c.index === selectedIndex.value)
  selectComponent(list[cur < 0 ? 0 : Math.min(cur + 1, list.length - 1)].index)
}
function selectPrevComponent() {
  const list = sortedComponents.value
  if (!list.length) return
  const cur = list.findIndex((c) => c.index === selectedIndex.value)
  selectComponent(list[cur < 0 ? 0 : Math.max(cur - 1, 0)].index)
}
function cycleCompareChannel(dir: 1 | -1) {
  const chans = overview.value?.ch_names || []
  if (!chans.length) return
  const cur = chans.indexOf(cmpChannel.value)
  cmpChannel.value = chans[((cur < 0 ? 0 : cur) + dir + chans.length) % chans.length]
}
function toggleCurrentRemove() {
  if (selectedIndex.value != null) toggleRemove(selectedIndex.value)
}
// 「操作提示」鼠标操作：与键盘快捷键并入同一张卡（HotkeyHelp 的「鼠标」分区）
const mouseHints = [
  { keys: ['单击成分'], label: '看频谱 / 时域' },
  { keys: ['双击'], label: '标记 / 取消剔除' },
  { keys: ['勾选框'], label: '标记剔除' },
  { keys: ['拖动'], label: '平移对比图' },
  { keys: ['滚轮'], label: '缩放时间' },
  { keys: ['Ctrl', '滚轮'], label: '缩放幅度' },
]

function buildHotkeys(): HotkeyDef[] {
  return [
    { key: 'j', label: '下一个成分', group: 'nav', run: () => selectNextComponent() },
    { key: 'k', label: '上一个成分', group: 'nav', run: () => selectPrevComponent() },
    { key: 'ArrowDown', label: '下一个成分', group: 'nav', run: () => selectNextComponent() },
    { key: 'ArrowUp', label: '上一个成分', group: 'nav', run: () => selectPrevComponent() },
    { key: ',', label: '上一个对比通道', group: 'nav', run: () => cycleCompareChannel(-1) },
    { key: '.', label: '下一个对比通道', group: 'nav', run: () => cycleCompareChannel(1) },
    { key: ' ', label: '标记 / 取消剔除当前成分', group: 'mark', when: () => selectedIndex.value != null, run: () => toggleCurrentRemove() },
    { key: 'x', label: '标记 / 取消剔除当前成分', group: 'mark', when: () => selectedIndex.value != null, run: () => toggleCurrentRemove() },
    { key: '0', label: '复位缩放', group: 'zoom', when: () => isZoomed.value, run: () => resetZoom() },
    { key: 'Ctrl+Enter', label: '应用并继续（提交剔除决策）', group: 'general', when: () => canApply.value, run: () => submitAndReturn() },
  ]
}
const { helpOpen, helpGroups } = useObserveHotkeys(buildHotkeys, {
  escLayers: [
    () => { if (isZoomed.value) { resetZoom(); return true } return false },
  ],
})

function describeError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: { message?: string } | string } }; message?: string }
  const detailField = e?.response?.data?.detail
  if (typeof detailField === 'string') return detailField
  if (detailField?.message) return detailField.message
  return e?.message || '加载失败'
}

onMounted(load)
</script>

<style scoped>
:deep(.page) { padding: 0; }
.ica-shell {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - var(--header-h));
  max-height: calc(100vh - var(--header-h));
}
.ica-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 0 var(--s-5);
  min-height: 56px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}
.ica-title { display: flex; align-items: center; gap: 8px; }
.ica-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.ica-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.ica-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }

.ica-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.ica-empty--full { flex: 1; }
.ica-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.ica-empty.is-error .ica-empty-title { color: var(--c-danger); }

/* ── 三区主体 ── */
.ica-main { flex: 1; display: flex; min-height: 0; overflow: hidden; }

/* 左·数据集 / 通道：观察页同款紧凑列表 */
.ica-left {
  width: 280px; min-width: 280px;
  border-right: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.ica-sec-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px 2px; font-size: 13px; font-weight: 600; color: var(--c-text); }
.ica-sec-head--sub { font-size: 12px; padding: 8px 12px 4px; }
.ica-sec-hint { padding: 0 12px 6px; font-size: 11px; color: var(--c-text-3); border-bottom: 1px solid var(--c-border); }
/* 成分排序：二选一分段切换条（编号 / 伪迹概率），替代下拉 */
.ica-sortseg { display: inline-flex; border: 1px solid var(--c-border); border-radius: var(--r-sm); overflow: hidden; }
.ica-sortseg button { font-size: 12px; padding: 2px 9px; border: none; background: var(--c-surface); color: var(--c-text-3); cursor: pointer; line-height: 1.6; }
.ica-sortseg button + button { border-left: 1px solid var(--c-border); }
.ica-sortseg button:hover { color: var(--c-text-2); }
.ica-sortseg button.is-on { background: var(--c-primary); color: #fff; }
.ica-wall-body { flex: 1; overflow-y: auto; padding: 8px; min-height: 0; }
.ica-active-topo {
  flex: 0 0 auto;
  padding: 8px 10px 10px;
  border-bottom: 1px solid var(--c-border);
  background: color-mix(in srgb, var(--c-surface) 94%, var(--c-bg));
}
.ica-active-topo-head { min-height: 22px; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.ica-active-topo-empty { height: 168px; display: flex; align-items: center; justify-content: center; border: 1px dashed var(--c-border); border-radius: var(--r-sm); background: var(--c-bg); }
.ica-active-topo :deep(.topo-strip.is-bare) { margin-top: 6px; }
.ica-active-topo :deep(.topo-cards) { overflow: visible; }
.ica-active-topo :deep(.topo-card) { padding: 6px 8px 4px; }
.ica-active-topo :deep(.topo-cv) { height: 156px; }

/* 右·成分缩略图墙：固定三列，宽度约为旧左栏的 1.5 倍 */
.ica-right {
  width: 384px; min-width: 384px;
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex; flex-direction: column;
  overflow: hidden;
}
/* 数据集 / 通道列表 */
.ica-picker { flex: 1; min-height: 0; display: grid; grid-template-rows: minmax(92px, auto) minmax(0, 1fr); overflow: hidden; }
.ica-pick-sec { min-height: 0; display: flex; flex-direction: column; border-top: 1px solid var(--c-border); }
.ica-pick-sec:first-child { border-top: 0; }
.ica-pick-list { min-height: 0; overflow-y: auto; padding: 4px 10px 8px; display: flex; flex-direction: column; gap: 3px; }
.ica-pick-list--channels { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; }
.ica-pick-row { width: 100%; min-height: 24px; border: 1px solid transparent; border-radius: var(--r-sm); background: transparent; color: var(--c-text-2); display: flex; align-items: center; gap: 6px; padding: 2px 7px; cursor: pointer; text-align: left; font-size: 11px; line-height: 1.35; overflow: hidden; }
.ica-pick-row:hover { border-color: color-mix(in srgb, var(--c-primary) 45%, var(--c-border)); background: color-mix(in srgb, var(--c-primary) 5%, var(--c-surface)); color: var(--c-text); }
.ica-pick-row.is-on { border-color: color-mix(in srgb, var(--c-primary) 55%, var(--c-border)); background: color-mix(in srgb, var(--c-primary) 12%, var(--c-surface)); color: var(--c-text); font-weight: 600; }
.ica-pick-dot { width: 6px; height: 6px; border-radius: 50%; background: #cbd2dc; flex: 0 0 auto; }
.ica-pick-row.is-on .ica-pick-dot { background: var(--c-primary); }
.ica-pick-name { min-width: 0; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ica-pick-tag { flex: 0 0 auto; font-size: 10px; color: var(--c-text-3); font-weight: 500; }

/* 中：整体对比（主视图，flex 高）+ 底部详情双栏 */
.ica-center { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.ica-center-head { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.ica-center-title { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.ica-chart-title { font-size: 12px; font-weight: 600; line-height: 1.45; color: var(--c-text); }
.ica-chart-meta { font-size: 12px; font-weight: 600; line-height: 1.45; color: var(--c-text-3); }
.ica-center-controls { display: inline-flex; align-items: center; gap: 12px; font-size: 12px; color: var(--c-text-3); }
.ica-windowseg { display: inline-flex; border: 1px solid var(--c-border); border-radius: var(--r-sm); overflow: hidden; background: var(--c-surface); }
.ica-windowseg button { border: none; border-left: 1px solid var(--c-border); background: transparent; color: var(--c-text-3); font-size: 12px; line-height: 1.6; padding: 2px 10px; cursor: pointer; }
.ica-windowseg button:first-child { border-left: 0; }
.ica-windowseg button:hover { color: var(--c-text); }
.ica-windowseg button.is-on { background: var(--c-primary); color: #fff; }
.ica-live { color: var(--c-primary); font-size: 12px; }
.ica-vr { color: var(--c-success); font-size: 12px; font-weight: 600; }
.ica-cmp-body { flex: 1 1 0; min-height: 260px; padding: 12px 16px 6px; display: flex; }
.ica-cmp-host { flex: 1; min-height: 0; position: relative; }
.ica-zoom-hint { position: absolute; right: 8px; top: 4px; font-size: 10px; color: var(--c-text-3); pointer-events: none; background: color-mix(in srgb, var(--c-surface) 80%, transparent); padding: 1px 5px; border-radius: 4px; }
.ica-cmp-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; color: var(--c-text-3); padding: 24px; }
.ica-detail-row {
  flex: 1 1 0;
  min-height: 260px;
  border-top: 1px solid var(--c-border);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  background: var(--c-surface);
}
.ica-detail-panel {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 7px 16px 10px;
}
.ica-detail-panel + .ica-detail-panel { border-left: 1px solid var(--c-border); }
.ica-panel-cap { min-height: 22px; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; padding-bottom: 4px; }
.ica-panel-host { flex: 1; min-height: 0; position: relative; }
.ica-panel-empty { display: flex; align-items: center; justify-content: center; height: 100%; }

/* 顶栏应用决策组（原底栏移上来，常驻不占画布高度） */
.ica-tb-div { width: 1px; height: 18px; background: var(--c-border); margin: 0 2px; }
.ica-rm-count { color: var(--c-danger); font-weight: 600; }
.ica-applymsg { font-size: 12px; color: var(--c-success); }
.ica-applymsg.is-error { color: var(--c-danger); }
</style>
