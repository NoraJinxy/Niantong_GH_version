<template>
  <WorkbenchShell active-key="ica" active-top-key="analysis">
    <div class="ica-shell">
      <!-- 顶部工具条 -->
      <div class="ica-toolbar">
        <h1 class="page__title ica-title" style="font-size: 22px; margin: 0">
          <IconLine name="brain" :size="24" /> ICA 成分审核
        </h1>
        <span v-if="isLive && overview" class="muted text-sm">
          {{ overview.method || 'ICA' }} · {{ overview.n_components }} 成分 · {{ overview.n_channels }} 通道
          <template v-if="overview.total_variance_explained != null">
            · 解释方差 {{ overview.total_variance_explained.toFixed(1) }}%
          </template>
          <template v-if="overview.iclabel_available"> · ICLabel 已自动标注</template>
        </span>
        <span class="ica-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实 ICA 数据' : '查看模式' }}</span>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="load">刷新</button>
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

      <!-- 两区主体 + 底部操作条 -->
      <template v-else>
        <div class="ica-main">
          <!-- 左：成分选择 + 剔除 + 选中频谱 + 通道 -->
          <section class="ica-left">
            <div class="ica-sec-head">
              <span>成分 · {{ components.length }}</span>
              <label class="ic-sort">
                <select v-model="sortMode" class="ic-sort-sel">
                  <option value="variance">方差 ↓</option>
                  <option value="iclabel">伪迹概率 ↓</option>
                  <option value="index">编号</option>
                </select>
              </label>
            </div>
            <div class="ica-sec-hint">单击看频谱/时域 · 勾选框 / 双击 = 标记剔除（红色 = 已标记，ICLabel 建议的伪迹已默认勾选）</div>
            <div class="ica-wall-body">
              <TopoStrip
                layout="grid"
                selectable
                checkable
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

            <!-- 选中成分频谱（替代原右栏） -->
            <div class="ica-leftspec">
              <div class="ica-spec-head">
                <template v-if="activeComp">
                  <span class="ica-spec-title">{{ activeComp.label }}</span>
                  <span v-if="activeComp.iclabel" class="ica-tag" :class="activeComp.iclabel.category === 'brain' ? 'is-brain' : 'is-artifact'">
                    {{ activeComp.iclabel.label_cn }}<template v-if="activeComp.iclabel.probability != null"> {{ Math.round(activeComp.iclabel.probability * 100) }}%</template>
                  </span>
                  <span v-if="activeComp.explained_variance != null" class="muted text-sm">方差 {{ activeComp.explained_variance.toFixed(1) }}%</span>
                </template>
                <span v-else class="muted text-sm">点成分看频谱</span>
              </div>
              <div class="ica-spec-host">
                <TimeCourseCanvas v-if="activeComp" :data="specData" :series="specSeries" x-label="Hz" y-label="dB" :show-legend="false" use-spline :loading="detailLoading" />
              </div>
              <div v-if="activeComp" class="muted text-sm ica-spec-chans">主导：{{ activeComp.top_channels.join(' · ') || '—' }}</div>
            </div>

            <!-- 通道列表（点选，不下拉） -->
            <div class="ica-chan">
              <div class="ica-sec-head ica-sec-head--sub">
                <span>对比通道</span>
                <span class="muted text-sm">{{ cmpChannel || '—' }}</span>
              </div>
              <div class="ica-chan-list">
                <button
                  v-for="ch in overview?.ch_names || []"
                  :key="ch"
                  class="ica-chan-chip"
                  :class="{ 'is-on': ch === cmpChannel }"
                  @click="cmpChannel = ch"
                >
                  {{ ch }}
                </button>
              </div>
            </div>
          </section>

          <!-- 中：整体去除前后对比（主视图）+ 选中成分时域激活（下方全宽） -->
          <section class="ica-center">
            <div class="ica-center-head">
              <div class="ica-center-title">
                整体去除前后对比
                <span v-if="cmpChannel" class="muted text-sm">· 通道 {{ cmpChannel }}</span>
              </div>
              <div class="ica-center-controls">
                <button v-if="isZoomed" class="btn btn--sm btn--ghost" @click="resetZoom">复位缩放</button>
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

            <!-- 选中成分时域激活：全宽、窄高，与主图 X 轴同步缩放 -->
            <div class="ica-tc-body">
              <div class="ica-tc-cap">
                选中成分时域激活（源）<template v-if="activeComp">· {{ activeComp.label }}</template>
              </div>
              <div class="ica-tc-host">
                <TimeCourseCanvas
                  v-if="activeComp"
                  :data="tcData"
                  :series="tcSeries"
                  x-label="时间 (s)"
                  y-label=""
                  :show-legend="false"
                  dense-axes
                  pan-on-drag
                  :view-min="viewMin"
                  :view-max="viewMax"
                  :amp-scale="tcAmp"
                  :loading="detailLoading"
                  @zoom="onZoom"
                  @amp="tcAmp = $event"
                />
                <div v-else class="ica-tc-empty muted text-sm">点击左侧成分查看其时域激活</div>
              </div>
            </div>
          </section>
        </div>

        <!-- 底部操作条：去除清单 + 应用并续跑 -->
        <div class="ica-bottom">
          <div class="ica-removelist">
            <span class="muted text-sm">待去除 {{ removeList.length }}：</span>
            <span v-if="!removeList.length" class="muted text-sm">未标记任何成分</span>
            <button v-for="idx in removeList" :key="idx" class="ica-rmtag" title="点击取消剔除" @click="toggleRemove(idx)">
              {{ labelOf(idx) }} <span class="ica-rmtag-x">✕</span>
            </button>
          </div>
          <span v-if="applyMsg" class="ica-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</span>
          <button v-if="applyDone" class="btn btn--sm" @click="closeSelf">关闭本页</button>
          <template v-else-if="!jobContext">
            <span class="muted text-sm">查看模式 · 在工作流「ICA Apply」节点处打开才能提交</span>
          </template>
          <button v-else class="btn btn--primary" :disabled="!canApply" @click="applyDecision">
            <AppIcon name="check" :size="16" />
            {{ applying ? '提交中…' : '应用并继续' }}
          </button>
        </div>
      </template>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, dataApi } from '@/api/client'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import { useIcaComparison } from '@/composables/observe/useIcaComparison'

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
  components: IcaComponent[]
}
interface IcaDetail {
  index: number
  label: string
  explained_variance: number | null
  sfreq: number
  timecourse: { times: number[]; values: number[] }
  spectrum: { frequencies: number[]; power_db: number[]; fmax: number }
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
const GRAY = '#79859A' // 对比图"原始"用灰

// 去除前后对比 / 时域激活载入的时窗（秒）：固定窗，缩放在前端做（拖动 / 滚轮），不再用时窗下拉。
const WINDOW_SECONDS = 30

const route = useRoute()
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return (raw as string | null) ?? fallback
}

const studyId = qstr('studyId') || qstr('study')
const outputId = qstr('study_output_id') || qstr('dd')
// 交互上下文（从工作流 waiting_user_input 的 ICA Apply 节点打开时带上），用于提交剔除决策
const executionId = qstr('executionId') || qstr('execution_id')
const jobId = qstr('jobId') || qstr('job_id')
const decisionVersion = Number(qstr('decisionVersion') || qstr('decision_version') || '0')

const isLive = computed(() => Boolean(studyId && outputId))
const jobContext = computed(() => Boolean(isLive.value && executionId && jobId && decisionVersion > 0))

const loading = ref(false)
const error = ref('')
const overview = ref<IcaComponentsResponse | null>(null)
const components = ref<IcaComponent[]>([])

const selectedIndex = ref<number | null>(null)
const detail = ref<IcaDetail | null>(null)
const detailLoading = ref(false)
let detailSeq = 0

const applying = ref(false)
const applyMsg = ref('')
const applyError = ref(false)
const applyDone = ref(false)

// 前端视觉缩放（与三观察页同一套手感）：viewMin/Max=可见时间窗（两图共享，X 同步），*Amp=各自幅度系数。
const viewMin = ref<number | null>(null)
const viewMax = ref<number | null>(null)
const cmpAmp = ref(1)
const tcAmp = ref(1)
const isZoomed = computed(() => viewMin.value != null || Math.abs(cmpAmp.value - 1) > 1e-3 || Math.abs(tcAmp.value - 1) > 1e-3)
function onZoom(v: { min: number; max: number } | null) {
  viewMin.value = v ? v.min : null
  viewMax.value = v ? v.max : null
}
function resetZoom() {
  viewMin.value = null
  viewMax.value = null
  cmpAmp.value = 1
  tcAmp.value = 1
}

// 中心「整体去除前后对比」编排：剔除集是唯一事实源，墙/清单/应用都从这里派生。
const studyIdRef = ref(studyId)
const outputIdRef = ref(outputId)
const {
  excludedSet,
  preview,
  previewLoading,
  channel: cmpChannel,
  maxSeconds: cmpSeconds,
  toggle: toggleExcluded,
  setExcluded,
} = useIcaComparison(studyIdRef, outputIdRef, () => isLive.value)
cmpSeconds.value = WINDOW_SECONDS

const activeComp = computed(() => components.value.find((c) => c.index === selectedIndex.value) || null)
const removeList = computed(() => [...excludedSet.value].sort((a, b) => a - b))
const canApply = computed(() => jobContext.value && !applying.value)

function isRemoved(index: number): boolean {
  return excludedSet.value.has(index)
}
function toggleRemove(index: number) {
  toggleExcluded(index)
}
function labelOf(idx: number): string {
  return components.value.find((c) => c.index === idx)?.label || `IC${String(idx).padStart(3, '0')}`
}

// 单成分权重 → TopoStrip 电极点：除以该成分自身 vmax 归一到 [-1,1]，配合 TopoStrip vmax=1 实现"每成分独立归一"。
function cellPoints(c: IcaComponent): TopoCell['points'] {
  if (!c.has_positions) return null
  const m = c.vmax > 0 ? c.vmax : 1
  return c.topography.map((p) => ({ name: p.name, x: p.x, y: p.y, value: p.weight / m }))
}

// 成分墙排序：默认按方差↓；可切「伪迹概率↓」（先看 ICLabel 判为伪迹且置信度高的）或编号。
const sortMode = ref<'index' | 'variance' | 'iclabel'>('variance')
function artifactScore(c: IcaComponent): number {
  const l = c.iclabel
  if (!l || l.category === 'brain' || l.category === 'other' || l.probability == null) return -1
  return l.probability
}
const sortedComponents = computed(() => {
  const list = [...components.value]
  if (sortMode.value === 'variance') {
    list.sort((a, b) => (b.explained_variance ?? -Infinity) - (a.explained_variance ?? -Infinity))
  } else if (sortMode.value === 'iclabel') {
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

// 时域激活（中心下方）+ 频谱（左栏）数据（喂 TimeCourseCanvas：data=[x, ...ys]）
const tcSeries = [{ name: '激活', color: PRIMARY }]
const specSeries = [{ name: '功率', color: ACCENT }]
const tcData = computed<number[][]>(() => (detail.value ? [detail.value.timecourse.times, detail.value.timecourse.values] : [[], []]))
const specData = computed<number[][]>(() => (detail.value ? [detail.value.spectrum.frequencies, detail.value.spectrum.power_db] : [[], []]))

// 中心整体对比：原始（灰） vs 去除后（蓝），同轴叠加；后端给 Volts，×1e6 换 µV。
const cmpSeries = [
  { name: '原始', color: GRAY },
  { name: '去除后', color: PRIMARY },
]
const previewData = computed<number[][]>(() => {
  const p = preview.value
  if (!p || !p.has_comparison || !p.times || !p.original || !p.filtered) return [[], []]
  return [p.times, p.original.map((v) => v * 1e6), p.filtered.map((v) => v * 1e6)]
})

async function load() {
  if (!isLive.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await dataApi.get<IcaComponentsResponse>(`/studies/${studyId}/outputs/${outputId}/ica-components`)
    overview.value = res.data
    components.value = res.data.components || []
    // 通道默认首通道
    if (res.data.ch_names?.length && !cmpChannel.value) cmpChannel.value = res.data.ch_names[0]
    // 默认剔除集：已保存的人工决策优先；否则用 ICLabel 自动建议（auto-flag + human-confirm，可取消）。
    const serverExclude = res.data.exclude || []
    const suggested = res.data.suggested_exclude || []
    setExcluded(new Set(serverExclude.length ? serverExclude : suggested))
    if (components.value.length) {
      selectComponent(selectedIndex.value ?? components.value[0].index)
    }
    document.title = `ICA 审核 · ${res.data.n_components} 成分 — 念析`
  } catch (err: unknown) {
    error.value = describeError(err)
    components.value = []
    overview.value = null
  } finally {
    loading.value = false
  }
}

// 单击成分 → 拉详情（时域激活 + 频谱；去除前后对比交给中心视图，这里不再重复算，更快）
async function selectComponent(index: number) {
  selectedIndex.value = index
  const myId = ++detailSeq
  detailLoading.value = true
  try {
    const res = await dataApi.get<IcaDetail>(`/studies/${studyId}/outputs/${outputId}/ica-components/${index}`, {
      params: { max_seconds: WINDOW_SECONDS },
    })
    if (myId !== detailSeq) return
    detail.value = res.data
  } catch {
    if (myId === detailSeq) detail.value = null
  } finally {
    if (myId === detailSeq) detailLoading.value = false
  }
}

function onCellClick(index: number) {
  selectComponent(index)
}

function closeSelf() {
  try {
    window.close()
  } catch {
    /* 浏览器可能拦截非脚本打开的标签关闭 */
  }
}

async function applyDecision() {
  if (!jobContext.value) return
  applying.value = true
  applyMsg.value = ''
  applyError.value = false
  try {
    await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/decision`, {
      excluded_components: removeList.value,
      decision_version: decisionVersion,
    })
    // 提交决策后顺势恢复运行——职责合一：本页既能选也能续跑。
    try {
      await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/resume`, {})
      applyMsg.value = `已提交剔除 ${removeList.value.length} 个成分，流水线已继续运行。`
    } catch {
      applyMsg.value = `已提交剔除 ${removeList.value.length} 个成分；自动继续未成功，请回工作流点「继续运行」。`
    }
    // 本页一般是从工作流暂停处新标签打开的——提交完直接关闭返回工作流；关不掉则保留「关闭本页」按钮兜底。
    applyDone.value = true
    setTimeout(closeSelf, 500)
  } catch (err: unknown) {
    applyError.value = true
    applyMsg.value = describeError(err)
  } finally {
    applying.value = false
  }
}

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
  height: 56px;
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

/* ── 两区主体 ── */
.ica-main { flex: 1; display: flex; min-height: 0; overflow: hidden; }

/* 左：成分缩略图墙（选择 + 剔除）+ 选中频谱 + 通道 */
.ica-left {
  width: 420px; min-width: 420px;
  border-right: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.ica-sec-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px 2px; font-size: 13px; font-weight: 600; color: var(--c-text); }
.ica-sec-head--sub { font-size: 12px; padding: 8px 12px 4px; }
.ica-sec-hint { padding: 0 12px 6px; font-size: 11px; color: var(--c-text-3); border-bottom: 1px solid var(--c-border); }
.ic-sort { display: inline-flex; align-items: center; }
.ic-sort-sel { font-size: 12px; padding: 2px 6px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; }
.ica-wall-body { flex: 1; overflow-y: auto; padding: 8px; min-height: 0; }

/* 选中成分频谱（替代原右栏） */
.ica-leftspec { flex-shrink: 0; border-top: 1px solid var(--c-border); padding: 8px 12px 6px; display: flex; flex-direction: column; gap: 4px; }
.ica-spec-head { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.ica-spec-title { font-weight: 600; font-size: 13px; color: var(--c-text); }
.ica-tag { font-size: 11px; padding: 1px 7px; border-radius: 999px; font-weight: 500; }
.ica-tag.is-artifact { background: rgba(239, 68, 68, .12); color: var(--c-danger); }
.ica-tag.is-brain { background: rgba(34, 197, 94, .14); color: #15803d; }
.ica-spec-host { height: 116px; position: relative; }
.ica-spec-chans { font-size: 11px; }

/* 通道列表：chip 点选（不下拉），可换行滚动 */
.ica-chan { flex-shrink: 0; border-top: 1px solid var(--c-border); max-height: 116px; display: flex; flex-direction: column; }
.ica-chan-list { overflow-y: auto; padding: 4px 10px 10px; display: flex; flex-wrap: wrap; gap: 4px; align-content: flex-start; }
.ica-chan-chip { font-size: 11px; padding: 2px 8px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; line-height: 1.5; }
.ica-chan-chip:hover { border-color: var(--c-primary); color: var(--c-text); }
.ica-chan-chip.is-on { background: var(--c-primary); border-color: var(--c-primary); color: #fff; }

/* 中：整体对比（主视图，flex 高）+ 选中成分时域激活（窄高） */
.ica-center { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.ica-center-head { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.ica-center-title { font-weight: 600; font-size: 14px; color: var(--c-text); }
.ica-center-controls { display: inline-flex; align-items: center; gap: 12px; font-size: 12px; color: var(--c-text-3); }
.ica-live { color: var(--c-primary); font-size: 12px; }
.ica-vr { color: var(--c-success); font-size: 12px; font-weight: 600; }
.ica-cmp-body { flex: 1; min-height: 0; padding: 12px 16px 6px; display: flex; }
.ica-cmp-host { flex: 1; min-height: 0; position: relative; }
.ica-zoom-hint { position: absolute; right: 8px; top: 4px; font-size: 10px; color: var(--c-text-3); pointer-events: none; background: color-mix(in srgb, var(--c-surface) 80%, transparent); padding: 1px 5px; border-radius: 4px; }
.ica-cmp-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; color: var(--c-text-3); padding: 24px; }
/* 选中成分时域激活：全宽、窄高 */
.ica-tc-body { flex-shrink: 0; height: 132px; border-top: 1px solid var(--c-border); display: flex; flex-direction: column; padding: 6px 16px 10px; }
.ica-tc-cap { font-size: 11px; font-weight: 600; color: var(--c-text-2); padding-bottom: 4px; }
.ica-tc-host { flex: 1; min-height: 0; position: relative; }
.ica-tc-empty { display: flex; align-items: center; justify-content: center; height: 100%; }

/* 底部操作条 */
.ica-bottom {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}
.ica-removelist { flex: 1; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
.ica-rmtag { display: inline-flex; align-items: center; gap: 4px; background: rgba(239, 68, 68, .1); color: var(--c-danger); border: 1px solid rgba(239, 68, 68, .25); border-radius: var(--r-sm); padding: 2px 8px; font-size: 12px; cursor: pointer; }
.ica-rmtag:hover { background: rgba(239, 68, 68, .16); }
.ica-rmtag-x { opacity: .55; }
.ica-applymsg { font-size: 12px; color: var(--c-success); }
.ica-applymsg.is-error { color: var(--c-danger); }
</style>
