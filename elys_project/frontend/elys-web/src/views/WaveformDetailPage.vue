<template>
  <div class="wf-page">
    <!-- 顶部信息条 -->
    <header class="wf-head">
      <div class="wf-id">
        <span class="wf-badge" :style="{ background: typeColor }">{{ typeShort }}</span>
        <div class="wf-id-text">
          <div class="wf-title">{{ displayName }}<span class="wf-region">{{ dataTypeLabel }}</span></div>
          <div class="wf-sub">
            <span class="text-mono">{{ shortId(datasetId) }}</span>
            <template v-if="ts?.segment_label && overlayFactor === 'none'">
              <span class="wf-dot">·</span>
              <span class="wf-cond">{{ segKindLabel }} {{ ts.segment_label }}</span>
            </template>
          </div>
        </div>
      </div>
      <div class="wf-head-right">
        <span class="wf-source is-real">真实时域数据</span>
        <button class="wf-btn wf-btn--ghost" @click="load" :disabled="loading">刷新</button>
      </div>
    </header>

    <!-- 工具条 -->
    <div class="wf-toolbar">
      <!-- 段（epoch / 条件）：关闭=单段切换，开启=多选对比 -->
      <template v-if="hasSegments">
        <span class="wf-lbl">对比</span>
        <select v-model="overlayFactor" class="wf-sel" style="max-width: 110px" :disabled="loading">
          <option value="none">关闭</option>
          <option value="segment">按{{ segKindLabel }}</option>
          <option value="channel">按通道</option>
        </select>

        <template v-if="overlayFactor === 'none'">
          <button class="wf-step" :disabled="loading || primarySeg <= 0" @click="stepSeg(-1)" title="上一个">‹</button>
          <select v-if="segOptions" class="wf-sel" :value="primarySeg" :disabled="loading" @change="onSegSelect">
            <option v-for="(o, i) in segOptions" :key="i" :value="i">{{ o }}</option>
          </select>
          <span v-else class="wf-seg-idx text-mono">{{ primarySeg + 1 }} / {{ segCount }}</span>
          <button class="wf-step" :disabled="loading || primarySeg >= (segCount || 1) - 1" @click="stepSeg(1)" title="下一个">›</button>
        </template>
        <template v-else>
          <div class="wf-seg-pills">
            <button
              v-for="i in segPills"
              :key="i"
              class="wf-pill"
              :class="{ 'is-on': selectedSegs.has(i) }"
              :disabled="loading"
              @click="toggleSeg(i)"
            >{{ segOptions?.[i] ?? ('#' + (i + 1)) }}</button>
            <span v-if="segCount > segPills.length" class="wf-pill-more">+{{ segCount - segPills.length }}</span>
          </div>
        </template>
        <span class="wf-div"></span>
      </template>

      <!-- X 时间窗 -->
      <span class="wf-lbl">时间窗 ({{ xUnit }})</span>
      <button v-if="isContinuous" class="wf-step" :disabled="loading" @click="pageWindow(-1)" title="上一段">«</button>
      <input v-model="winLoInput" class="wf-num" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
      <span class="wf-dash">–</span>
      <input v-model="winHiInput" class="wf-num" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
      <button v-if="isContinuous" class="wf-step" :disabled="loading" @click="pageWindow(1)" title="下一段">»</button>
      <button class="wf-mini" :disabled="loading" @click="applyWindow">应用</button>
      <button class="wf-mini" :disabled="loading" @click="resetWindow">重置</button>
      <span class="wf-div"></span>

      <!-- Y 幅值 -->
      <span class="wf-lbl">Y(μV)</span>
      <select v-model.number="yScaleIdx" class="wf-sel">
        <option v-for="(y, i) in Y_SCALES" :key="i" :value="i">{{ y.label }}</option>
      </select>
      <span class="wf-div"></span>
      <span class="wf-lbl">显示</span>
      <select v-model="displayMode" class="wf-sel" style="max-width: 72px">
        <option value="overlay">叠加</option>
        <option value="spread">排列</option>
      </select>
      <span class="wf-div"></span>
      <label class="wf-chk"><input type="checkbox" v-model="showGrid" />网格</label>

      <div style="flex: 1"></div>
      <span class="wf-readout" v-if="cursorReadout">
        <span class="text-mono">{{ fmtX(cursorReadout.x) }} {{ xUnit }}</span>
        <span v-for="it in cursorReadout.items.slice(0, 6)" :key="it.name" class="wf-readout-v" :style="{ color: it.color }">
          {{ it.name }} {{ it.uv.toFixed(2) }}
        </span>
        <span v-if="cursorReadout.items.length > 6" class="wf-readout-more">+{{ cursorReadout.items.length - 6 }}</span>
        <span class="wf-readout-unit">μV</span>
      </span>
    </div>

    <!-- 主体 -->
    <div class="wf-body">
      <div v-if="loading && !ts" class="wf-state">正在读取时域数据…</div>

      <div v-else-if="error" class="wf-state wf-state--err">
        <div class="wf-err-title">无法加载该节点的时域数据</div>
        <div class="wf-err-msg">{{ error }}</div>
        <button class="wf-btn" @click="load">重试</button>
      </div>

      <template v-else-if="hasCurves">
        <!-- 左侧通道 listbox -->
        <aside class="wf-chanbox">
          <div class="wf-chanbox-header">
            <strong>通道</strong>
            <span class="wf-chanbox-count">{{ selected.size }}/{{ allChanNames.length }}</span>
            <button v-if="selected.size < allChanNames.length" type="button" class="wf-chanbox-link" @click="selectAll">全选</button>
            <button v-if="selected.size > 0" type="button" class="wf-chanbox-link" @click="selectNone">清空</button>
          </div>
          <div ref="chanListRef" class="wf-chanlist" tabindex="0">
            <div
              v-for="(name, i) in allChanNames"
              :key="name"
              class="wf-chanitem"
              :class="{ 'is-sel': selected.has(name) }"
              @click="onChannelClick(i, $event)"
            >
              <span class="wf-leg-dot" :style="{ background: channelColor(i) }"></span>
              <span class="wf-chanitem-name">{{ name }}</span>
            </div>
          </div>
          <p class="wf-chanbox-hint" v-if="ts && ts.n_channels_total > allChanNames.length">
            仅列出前 {{ allChanNames.length }} / {{ ts.n_channels_total }} 通道
          </p>
          <p class="wf-chanbox-hint" v-else>单击 · Ctrl 加减 · Shift 连选 · Ctrl+A 全选</p>
        </aside>

        <!-- 中间绘图（facet 子图网格） -->
        <div class="wf-plot-area">
          <div v-if="!selected.size" class="wf-empty-hint">未选择通道 —— 在左侧列表里选择要绘制的通道</div>
          <div v-else class="wf-facet" :class="{ 'is-single': cells.length <= 1 }">
            <section v-for="cell in cells" :key="cell.key" class="wf-cell">
              <div v-if="cell.title" class="wf-cell-title">{{ cell.title }}</div>
              <div class="wf-cell-plot">
                <TimeCourseCanvas
                  :data="cell.data"
                  :series="cell.series"
                  :x-label="`时间 (${xUnit})`"
                  y-label="μV"
                  :y-max="yMaxValue"
                  :display-mode="displayMode"
                  :show-grid="showGrid"
                  :loading="loading"
                  @cursor="onCursor"
                  @select="onSelect"
                />
              </div>
            </section>
          </div>
        </div>

        <!-- 右侧区间统计（框选后出现） -->
        <aside v-if="region && intervalStats.length" class="wf-stats">
          <div class="wf-stats-head">
            <strong>区间统计</strong>
            <span class="text-mono wf-stats-range">{{ fmtX(region.x0) }}–{{ fmtX(region.x1) }} {{ xUnit }}</span>
            <button type="button" class="wf-chanbox-link" @click="region = null">清除</button>
          </div>
          <div class="wf-stats-scroll">
            <table class="wf-stats-tbl">
              <thead><tr><th>序列</th><th>均值</th><th>峰值</th><th>峰值@</th></tr></thead>
              <tbody>
                <tr v-for="(s, i) in intervalStats" :key="i">
                  <td class="wf-stats-name"><span class="wf-leg-dot" :style="{ background: s.color }"></span>{{ s.label }}</td>
                  <td class="text-mono">{{ s.mean.toFixed(2) }}</td>
                  <td class="text-mono">{{ s.peak.toFixed(2) }}</td>
                  <td class="text-mono">{{ fmtX(s.peakX) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="wf-chanbox-hint">单位 μV · 在任一子图上横向拖拽选区</p>
        </aside>
      </template>

      <div v-else class="wf-state">该数据没有可绘制的通道曲线。</div>
    </div>

    <!-- 底部摘要 -->
    <footer class="wf-foot" v-if="ts && !error">
      <div class="wf-metrics">
        <div class="wf-metric"><span class="k">类型</span><span class="v">{{ dataType }}</span></div>
        <div class="wf-metric"><span class="k">sfreq</span><span class="v">{{ ts.sfreq.toFixed(0) }} Hz</span></div>
        <div class="wf-metric"><span class="k">通道</span><span class="v">{{ selected.size }}/{{ ts.n_channels_total }}</span></div>
        <div class="wf-metric"><span class="k">窗口</span><span class="v">{{ fmtX(ts.tmin * xFactor) }}–{{ fmtX(ts.tmax * xFactor) }} {{ xUnit }}</span></div>
        <div class="wf-metric" v-if="hasSegments && overlayFactor !== 'none'"><span class="k">{{ segKindLabel }}</span><span class="v">{{ selectedSegs.size }} 选</span></div>
        <div class="wf-metric" v-else-if="hasSegments"><span class="k">{{ segKindLabel }}</span><span class="v">{{ primarySeg + 1 }}/{{ segCount }}</span></div>
      </div>
      <p class="wf-note">
        数据来自 <code>GET /studies/&#123;id&#125;/outputs/&#123;dd&#125;/timeseries</code>，按时间窗 / 段 / 通道下采样（每通道最多 {{ MAX_POINTS }} 点、最多 {{ MAX_CHANNELS }} 通道）。
      </p>
    </footer>

    <CacheDebugOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { StudyOutputTimeseries } from '@/types'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import CacheDebugOverlay from '@/components/observe/CacheDebugOverlay.vue'
import { channelColor } from '@/composables/observe/channelColor'
import { fetchTimeseries } from '@/composables/observe/plotCache'

const route = useRoute()

// ---------- 常量 ----------
const MAX_CHANNELS = 64
const MAX_POINTS = 2000 // uPlot Canvas 比 SVG 可承载更多点；仍由后端按窗下采样（上限 8000）
const CONTINUOUS = ['raw', 'filtered_raw', 'ica_cleaned']
const MAX_SEG_PILLS = 40
const Y_SCALES = [
  { label: '自动', max: 0 },
  { label: '±5', max: 5 },
  { label: '±10', max: 10 },
  { label: '±20', max: 20 },
  { label: '±50', max: 50 },
  { label: '±100', max: 100 },
  { label: '±200', max: 200 },
]
const DATA_TYPE_LABELS: Record<string, string> = {
  raw: '连续原始 (raw)',
  filtered_raw: '滤波后 (filtered_raw)',
  ica_cleaned: 'ICA 清理 (ica_cleaned)',
  epochs: '分段 (epochs)',
  evoked: '平均 (evoked / ERP)',
}
const DEFAULT_SELECT = 8

// ---------- 查询参数 ----------
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return raw ?? fallback
}
// 参数统一为 studyId / study_output_id（与 PSD/TFR 一致）；兼容旧 study / dd 命名
const studyId = qstr('studyId') || qstr('study')
// study_output_id 支持逗号分隔的多产物（多数据集对比，如 ERP 各条件分别落成独立 evoked 产物）
const outputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
const datasetId = outputIds[0] || ''
const isMultiOutput = outputIds.length > 1
const nameHint = qstr('name')
const typeHint = qstr('type')

// ---------- 状态 ----------
const tsMap = ref<Map<number, StudyOutputTimeseries>>(new Map()) // segIndex -> 时域数据
const loading = ref(true)
const error = ref('')
// 多产物模式：默认全选 + 自动按"数据集"对比（一进来就同屏看到各条件叠加）
const selectedSegs = ref<Set<number>>(new Set(isMultiOutput ? outputIds.map((_, i) => i) : [0]))
const overlayFactor = ref<'none' | 'segment' | 'channel'>(isMultiOutput ? 'segment' : 'none')
const reqTmin = ref<number | null>(null) // 秒
const reqTmax = ref<number | null>(null)
const winLoInput = ref<number | string>('') // 显示单位
const winHiInput = ref<number | string>('')
const yScaleIdx = ref(0)
const showGrid = ref(true)
const displayMode = ref<'overlay' | 'spread'>('overlay')
const selected = ref<Set<string>>(new Set())
const anchorIndex = ref(-1)
const chanListRef = ref<HTMLDivElement | null>(null)
const cursorReadout = ref<{ x: number; items: { name: string; color: string; uv: number }[] } | null>(null)
const region = ref<{ x0: number; x1: number } | null>(null) // 显示单位

// ---------- 主 / 段 ----------
const sortedSegs = computed(() => [...selectedSegs.value].sort((a, b) => a - b))
const primarySeg = computed(() => (sortedSegs.value.length ? sortedSegs.value[0] : 0))
const ts = computed<StudyOutputTimeseries | null>(
  () => tsMap.value.get(primarySeg.value) ?? tsMap.value.values().next().value ?? null,
)

// ---------- 类型 / 单位 ----------
const dataType = computed(() => String(ts.value?.data_type ?? typeHint ?? '').toLowerCase())
const isContinuous = computed(() => CONTINUOUS.includes(dataType.value))
const xUnit = computed(() => (isContinuous.value ? 's' : 'ms'))
const xFactor = computed(() => (isContinuous.value ? 1 : 1000))
const xStep = computed(() => (isContinuous.value ? 0.5 : 50))
const xPrec = computed(() => (isContinuous.value ? 3 : 0))

const dataTypeLabel = computed(() => DATA_TYPE_LABELS[dataType.value] ?? (dataType.value || '结果'))
const typeShort = computed(() => (dataType.value === 'evoked' ? 'ERP' : dataType.value.slice(0, 3).toUpperCase() || 'DD'))
const typeColor = computed(() => (dataType.value === 'evoked' ? '#2E6BFF' : isContinuous.value ? '#0891B2' : '#8B5CF6'))
const displayName = computed(() => nameHint || dataTypeLabel.value)

// 段数：单产物=该产物 n_segments；多产物=产物个数（把"数据集"映射到段维度，复用对比/网格机制）
const segCount = computed(() => (isMultiOutput ? outputIds.length : ts.value?.n_segments || 0))
const hasSegments = computed(() => segCount.value > 1)
const segKindLabel = computed(() => (isMultiOutput ? '数据集' : ts.value?.segment_kind === 'condition' ? '条件' : 'Epoch'))
const segOptions = computed(() =>
  isMultiOutput
    ? outputIds.map((_, i) => tsMap.value.get(i)?.segment_label || `数据集 ${i + 1}`)
    : ts.value?.segment_options ?? null,
)
const segPills = computed(() => Array.from({ length: Math.min(segCount.value, MAX_SEG_PILLS) }, (_, k) => k))

// ---------- 工具 ----------
function shortId(value?: string | null) {
  if (!value) return ''
  return value.length > 10 ? value.slice(0, 8) + '…' : value
}
function round(n: number, p: number) {
  const f = Math.pow(10, p)
  return Math.round(n * f) / f
}
function fmtX(v: number) {
  return Number(v.toFixed(xPrec.value))
}
function toNum(v: number | string): number | null {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
function clampInt(v: number, lo: number, hi: number) {
  return v < lo ? lo : v > hi ? hi : v
}
function segLabel(seg: number) {
  const t = tsMap.value.get(seg)
  if (t?.segment_label) return t.segment_label
  if (isMultiOutput) return `数据集 ${seg + 1}`
  return ts.value?.segment_options?.[seg] ?? `#${seg + 1}`
}
function segColor(seg: number) {
  const idx = sortedSegs.value.indexOf(seg)
  return channelColor(idx < 0 ? seg : idx)
}

// ---------- 单位缩放（V → µV）----------
const uvScale = computed(() => {
  let maxAbs = 0
  for (const t of tsMap.value.values()) for (const c of t.channels) for (const v of c.values) maxAbs = Math.max(maxAbs, Math.abs(v))
  return maxAbs > 0 && maxAbs < 0.01 ? 1e6 : 1
})

const allChanNames = computed(() => (ts.value?.channels ?? []).map((c) => c.name))
const orderedSel = computed(() => allChanNames.value.filter((n) => selected.value.has(n)))

function xsFor(t: StudyOutputTimeseries) {
  return t.times.map((s) => s * xFactor.value)
}

// ---------- facet 单元 ----------
interface Cell {
  key: string
  title: string
  data: number[][]
  series: { name: string; color: string }[]
}
const cells = computed<Cell[]>(() => {
  const sel = orderedSel.value
  const scale = uvScale.value
  if (!sel.length) return []

  if (overlayFactor.value === 'segment') {
    // 行=通道，叠加=段
    return sel.map((name) => {
      let xs: number[] = []
      const cols: number[][] = []
      const series: { name: string; color: string }[] = []
      for (const seg of sortedSegs.value) {
        const t = tsMap.value.get(seg)
        if (!t) continue
        const ch = t.channels.find((c) => c.name === name)
        if (!ch) continue
        if (!xs.length) xs = xsFor(t)
        cols.push(ch.values.map((v) => v * scale))
        series.push({ name: segLabel(seg), color: segColor(seg) })
      }
      return { key: 'ch:' + name, title: name, data: [xs, ...cols], series }
    })
  }

  if (overlayFactor.value === 'channel') {
    // 行=段，叠加=通道
    return sortedSegs.value.map((seg) => {
      const t = tsMap.value.get(seg)
      if (!t) return { key: 'seg:' + seg, title: segLabel(seg), data: [[]], series: [] }
      const xs = xsFor(t)
      const cols: number[][] = []
      const series: { name: string; color: string }[] = []
      sel.forEach((name) => {
        const ch = t.channels.find((c) => c.name === name)
        if (!ch) return
        cols.push(ch.values.map((v) => v * scale))
        series.push({ name, color: channelColor(allChanNames.value.indexOf(name)) })
      })
      return { key: 'seg:' + seg, title: segLabel(seg), data: [xs, ...cols], series }
    })
  }

  // none：单图，主段，所有选中通道叠加
  const t = ts.value
  if (!t) return []
  const xs = xsFor(t)
  const cols: number[][] = []
  const series: { name: string; color: string }[] = []
  sel.forEach((name) => {
    const ch = t.channels.find((c) => c.name === name)
    if (!ch) return
    cols.push(ch.values.map((v) => v * scale))
    series.push({ name, color: channelColor(allChanNames.value.indexOf(name)) })
  })
  return [{ key: 'all', title: '', data: [xs, ...cols], series }]
})

const hasCurves = computed(() => allChanNames.value.length > 0 && (ts.value?.times.length || 0) > 1)

const autoYMax = computed(() => {
  let m = 0
  for (const cell of cells.value) for (let i = 1; i < cell.data.length; i++) for (const v of cell.data[i]) m = Math.max(m, Math.abs(v))
  return Math.max(2, Math.ceil((m * 1.2) / 2) * 2)
})
const yMaxValue = computed(() => Y_SCALES[yScaleIdx.value].max || autoYMax.value)

// ---------- 区间统计 ----------
const intervalStats = computed(() => {
  const r = region.value
  if (!r) return [] as { label: string; color: string; mean: number; peak: number; peakX: number }[]
  const out: { label: string; color: string; mean: number; peak: number; peakX: number }[] = []
  for (const cell of cells.value) {
    const xs = cell.data[0] || []
    const idxs: number[] = []
    xs.forEach((x, i) => {
      if (x >= r.x0 && x <= r.x1) idxs.push(i)
    })
    if (!idxs.length) continue
    for (let si = 1; si < cell.data.length; si++) {
      const col = cell.data[si]
      const s = cell.series[si - 1]
      let sum = 0
      let peak = 0
      let peakX = xs[idxs[0]]
      for (const i of idxs) {
        const v = col[i] ?? 0
        sum += v
        if (Math.abs(v) > Math.abs(peak)) {
          peak = v
          peakX = xs[i]
        }
      }
      out.push({ label: (cell.title ? cell.title + '·' : '') + s.name, color: s.color, mean: sum / idxs.length, peak, peakX })
    }
  }
  return out.slice(0, 200)
})

// ---------- 拉取时域数据 ----------
async function load() {
  if (!studyId || !outputIds.length) {
    error.value = '缺少参数：需要 studyId 和 study_output_id（结果 ID）。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    let prim: StudyOutputTimeseries
    if (isMultiOutput) {
      // 多产物对比：每个产物取默认段，键=产物序号(0..N-1)，把"数据集"摆到段维度复用对比/网格机制
      const results = await Promise.all(
        outputIds.map(async (oid, i) => {
          const { ts: data } = await fetchTimeseries(studyId, oid, {
            tmin: reqTmin.value,
            tmax: reqTmax.value,
            maxPoints: MAX_POINTS,
            maxChannels: MAX_CHANNELS,
          })
          return [i, data] as const
        }),
      )
      const m = new Map<number, StudyOutputTimeseries>()
      for (const [i, data] of results) m.set(i, data)
      tsMap.value = m
      prim = m.get(primarySeg.value) ?? results[0][1]
    } else {
      const useMulti = overlayFactor.value !== 'none' && selectedSegs.value.size > 0
      const segs = useMulti ? sortedSegs.value : [primarySeg.value]
      const results = await Promise.all(
        segs.map(async (seg) => {
          const { ts: data } = await fetchTimeseries(studyId, datasetId, {
            index: seg,
            tmin: reqTmin.value,
            tmax: reqTmax.value,
            maxPoints: MAX_POINTS,
            maxChannels: MAX_CHANNELS,
          })
          return [seg, data] as const
        }),
      )
      const m = new Map<number, StudyOutputTimeseries>()
      for (const [seg, data] of results) m.set(data.segment_index ?? seg, data)
      tsMap.value = m
      prim = m.get(primarySeg.value) ?? results[0][1]
    }
    winLoInput.value = round(prim.tmin * xFactor.value, xPrec.value)
    winHiInput.value = round(prim.tmax * xFactor.value, xPrec.value)
    document.title = `时域 · ${displayName.value} — 念析`
  } catch (err: unknown) {
    tsMap.value = new Map()
    error.value = describeError(err)
  } finally {
    loading.value = false
  }
}

function describeError(err: unknown): string {
  const e = err as { response?: { status?: number; data?: { detail?: { message?: string } | string } } }
  const status = e?.response?.status
  const detail = e?.response?.data?.detail
  const serverMsg = typeof detail === 'string' ? detail : detail?.message
  if (status === 404) return '该结果的文件不存在或已被清理（可能是未保留的中间结果）。'
  if (status === 409) return '文件校验和与记录不一致，数据可能已损坏。'
  if (status === 400) return serverMsg || '该数据类型不支持时域曲线。'
  if (status === 422) return serverMsg || '该结果缺少可解析的存储路径或为空。'
  return serverMsg || '读取时域数据失败，请稍后重试。'
}

// ---------- 控制动作（改状态，由 watch 触发 load）----------
function applyWindow() {
  const lo = toNum(winLoInput.value)
  const hi = toNum(winHiInput.value)
  reqTmin.value = lo === null ? null : lo / xFactor.value
  reqTmax.value = hi === null ? null : hi / xFactor.value
}
function resetWindow() {
  reqTmin.value = null
  reqTmax.value = null
}
function pageWindow(dir: number) {
  const t = ts.value
  if (!t) return
  const len = t.tmax - t.tmin
  if (len <= 0) return
  let lo = t.tmin + dir * len
  let hi = t.tmax + dir * len
  if (lo < t.available_tmin) {
    lo = t.available_tmin
    hi = lo + len
  }
  if (hi > t.available_tmax) {
    hi = t.available_tmax
    lo = Math.max(t.available_tmin, hi - len)
  }
  reqTmin.value = lo
  reqTmax.value = hi
}
function setSeg(i: number) {
  selectedSegs.value = new Set([i])
  reqTmin.value = null
  reqTmax.value = null
}
function stepSeg(d: number) {
  const n = ts.value?.n_segments || 1
  const next = clampInt(primarySeg.value + d, 0, n - 1)
  if (next !== primarySeg.value) setSeg(next)
}
function onSegSelect(e: Event) {
  setSeg(Number((e.target as HTMLSelectElement).value))
}
function toggleSeg(i: number) {
  const s = new Set(selectedSegs.value)
  if (s.has(i)) s.delete(i)
  else s.add(i)
  if (!s.size) s.add(i)
  selectedSegs.value = s
}

watch(overlayFactor, (mode) => {
  region.value = null
  // 切到对比且只有 1 段时，自动补第 2 段，方便直接看到对比
  if (mode !== 'none' && selectedSegs.value.size < 2 && segCount.value >= 2) {
    selectedSegs.value = new Set([primarySeg.value, primarySeg.value === 0 ? 1 : 0])
  }
})

// 段集合 / 窗口 / 对比模式变化 → 重新取数（通道选择是客户端过滤，不触发）
watch([overlayFactor, () => sortedSegs.value.join(','), reqTmin, reqTmax], () => {
  void load()
})

// ---------- 通道选择 ----------
function onChannelClick(index: number, e: MouseEvent) {
  const names = allChanNames.value
  if (!names.length) return
  chanListRef.value?.focus()
  const name = names[index]
  const additive = e.ctrlKey || e.metaKey
  if (e.shiftKey && anchorIndex.value >= 0) {
    const lo = Math.min(anchorIndex.value, index)
    const hi = Math.max(anchorIndex.value, index)
    const next = additive ? new Set(selected.value) : new Set<string>()
    for (let i = lo; i <= hi; i++) next.add(names[i])
    selected.value = next
  } else if (additive) {
    const next = new Set(selected.value)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    selected.value = next
    anchorIndex.value = index
  } else {
    selected.value = new Set([name])
    anchorIndex.value = index
  }
}
function selectAll() {
  selected.value = new Set(allChanNames.value)
  anchorIndex.value = allChanNames.value.length - 1
}
function selectNone() {
  selected.value = new Set()
}

watch(
  () => allChanNames.value.join(''),
  (key) => {
    if (!key) return
    if (selected.value.size === 0) {
      const init = allChanNames.value.slice(0, Math.min(allChanNames.value.length, DEFAULT_SELECT))
      selected.value = new Set(init)
      anchorIndex.value = init.length - 1
    }
  },
  { immediate: true },
)

// ---------- 游标 / 选区（来自 TimeCourseCanvas）----------
function onCursor(payload: { x: number; items: { name: string; color: string; uv: number }[] } | null) {
  cursorReadout.value = payload
}
function onSelect(r: { x0: number; x1: number } | null) {
  region.value = r
}

// ---------- Ctrl+A 全选 ----------
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
    const tag = document.activeElement?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    e.preventDefault()
    if (hasCurves.value) selectAll()
  }
}

onMounted(() => {
  document.title = '时域 — 念析'
  window.addEventListener('keydown', onKeydown)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.wf-page { display: flex; flex-direction: column; height: 100vh; background: var(--c-bg-soft); color: var(--c-text); font-family: var(--ff-sans); }
.text-mono { font-family: var(--ff-mono); }

.wf-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); }
.wf-id { display: flex; align-items: center; gap: 12px; min-width: 0; }
.wf-badge { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: var(--r); color: #fff; font-weight: 700; font-size: 12px; flex-shrink: 0; }
.wf-title { font-size: 15px; font-weight: 600; }
.wf-region { margin-left: 8px; font-size: 12px; font-weight: 400; color: var(--c-text-3); }
.wf-sub { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--c-text-2); margin-top: 2px; flex-wrap: wrap; }
.wf-dot { color: var(--c-text-3); }
.wf-cond { display: inline-flex; align-items: center; gap: 4px; background: var(--c-bg-tint); padding: 1px 7px; border-radius: var(--r-pill); }
.wf-head-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wf-source { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); }
.wf-source.is-real { color: var(--c-success); background: var(--c-success-soft); border: 1px solid rgba(16, 185, 129, .3); }
.wf-btn { height: 28px; padding: 0 12px; border-radius: var(--r-sm); border: 1px solid var(--c-border-2); background: var(--c-surface); color: var(--c-text); font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; }
.wf-btn:hover { background: var(--c-bg-tint); }
.wf-btn:disabled { opacity: .5; cursor: default; }
.wf-btn--ghost { color: var(--c-text-2); }

.wf-toolbar { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.wf-lbl { font-size: 11px; color: var(--c-text-3); }
.wf-sel { height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; max-width: 160px; }
.wf-num { width: 64px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; font-family: var(--ff-mono); }
.wf-dash { color: var(--c-text-3); }
.wf-step { width: 24px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; font-size: 13px; padding: 0; }
.wf-step:hover:not(:disabled) { background: var(--c-bg-tint); color: var(--c-text); }
.wf-step:disabled { opacity: .4; cursor: default; }
.wf-seg-idx { font-size: 12px; color: var(--c-text-2); min-width: 56px; text-align: center; }
.wf-seg-pills { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; max-width: 360px; }
.wf-pill { height: 24px; padding: 0 8px; border: 1px solid var(--c-border-2); border-radius: var(--r-pill); background: var(--c-surface); color: var(--c-text-2); font-size: 11px; cursor: pointer; }
.wf-pill:hover:not(:disabled) { background: var(--c-bg-tint); }
.wf-pill.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.wf-pill:disabled { opacity: .5; cursor: default; }
.wf-pill-more { font-size: 10px; color: var(--c-text-3); }
.wf-mini { height: 26px; padding: 0 8px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 11px; cursor: pointer; }
.wf-mini:hover:not(:disabled) { background: var(--c-bg-tint); }
.wf-mini:disabled { opacity: .5; cursor: default; }
.wf-div { width: 1px; height: 20px; background: var(--c-border); margin: 0 2px; }
.wf-chk { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--c-text-2); cursor: pointer; }
.wf-readout { display: inline-flex; align-items: center; gap: 8px; font-size: 12px; flex-wrap: wrap; justify-content: flex-end; }
.wf-readout-v { font-family: var(--ff-mono); font-weight: 600; }
.wf-readout-more { font-family: var(--ff-mono); color: var(--c-text-3); }
.wf-readout-unit { color: var(--c-text-3); }

.wf-body { flex: 1; display: flex; min-height: 0; }
.wf-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--c-text-2); font-size: 13px; }
.wf-state--err { color: var(--c-danger); }
.wf-err-title { font-size: 15px; font-weight: 600; }
.wf-err-msg { color: var(--c-text-2); font-size: 13px; max-width: 480px; text-align: center; }

/* 左侧通道 listbox */
.wf-chanbox { width: 178px; flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; padding: 8px; background: var(--c-surface); border-right: 1px solid var(--c-border); }
.wf-chanbox-header { display: flex; align-items: center; gap: 6px; padding: 2px; font-size: 11px; }
.wf-chanbox-header strong { font-size: 12px; font-weight: 600; color: var(--c-text); }
.wf-chanbox-count { font-size: 9px; padding: 0 5px; background: var(--c-bg-tint); border-radius: 8px; font-weight: 500; color: var(--c-text-2); min-width: 30px; text-align: center; }
.wf-chanbox-link { background: none; border: none; color: var(--c-primary); cursor: pointer; font-size: 11px; padding: 0 2px; }
.wf-chanbox-link:first-of-type { margin-left: auto; }
.wf-chanbox-link:hover { text-decoration: underline; }
.wf-chanlist { flex: 1; overflow-y: auto; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: #fff; outline: none; user-select: none; -webkit-user-select: none; transition: box-shadow .18s, background .18s; }
.wf-chanlist:focus { box-shadow: inset 3px 0 0 var(--c-primary); background: linear-gradient(to right, rgba(46, 107, 255, .05), transparent 60%); }
.wf-chanitem { display: flex; align-items: center; gap: 7px; padding: 3px 8px; font-size: 12px; cursor: pointer; user-select: none; border-left: 3px solid transparent; line-height: 1.5; }
.wf-chanitem:hover { background: var(--c-bg-tint); }
.wf-chanitem.is-sel { background: rgba(46, 107, 255, .14); border-left-color: var(--c-primary); color: var(--c-primary); font-weight: 500; }
.wf-chanitem-name { font-family: var(--ff-mono); }
.wf-leg-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.wf-chanbox-hint { margin: 0; padding: 0 2px; font-size: 10px; color: var(--c-text-3); line-height: 1.4; }

/* 中间绘图区 + facet 网格 */
.wf-plot-area { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 10px 14px; }
.wf-facet { flex: 1; min-height: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 10px; overflow: auto; align-content: start; }
.wf-facet.is-single { display: flex; }
.wf-cell { display: flex; flex-direction: column; min-height: 200px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); overflow: hidden; }
.wf-facet.is-single .wf-cell { flex: 1; }
.wf-cell-title { font-size: 11px; font-weight: 600; color: var(--c-text-2); padding: 4px 8px; border-bottom: 1px solid var(--c-border); font-family: var(--ff-mono); background: var(--c-bg-soft); }
.wf-cell-plot { flex: 1; min-height: 0; padding: 6px 8px; }
.wf-empty-hint { text-align: center; color: var(--c-text-3); font-size: 12px; padding: 8px 0 12px; }

/* 右侧区间统计 */
.wf-stats { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; padding: 8px; background: var(--c-surface); border-left: 1px solid var(--c-border); }
.wf-stats-head { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.wf-stats-head strong { font-size: 12px; font-weight: 600; }
.wf-stats-range { font-size: 10px; color: var(--c-text-2); }
.wf-stats-head .wf-chanbox-link { margin-left: auto; }
.wf-stats-scroll { flex: 1; overflow: auto; border: 1px solid var(--c-border); border-radius: var(--r-sm); }
.wf-stats-tbl { width: 100%; border-collapse: collapse; font-size: 11px; }
.wf-stats-tbl th { position: sticky; top: 0; background: var(--c-bg-soft); color: var(--c-text-3); font-weight: 500; text-align: right; padding: 4px 8px; border-bottom: 1px solid var(--c-border); }
.wf-stats-tbl th:first-child { text-align: left; }
.wf-stats-tbl td { padding: 3px 8px; text-align: right; border-bottom: 1px solid var(--c-border); color: var(--c-text); }
.wf-stats-tbl td:first-child { text-align: left; }
.wf-stats-name { display: flex; align-items: center; gap: 6px; }

.wf-foot { background: var(--c-surface); border-top: 1px solid var(--c-border); padding: 10px 16px; }
.wf-metrics { display: flex; gap: 8px; flex-wrap: wrap; }
.wf-metric { display: flex; gap: 6px; align-items: baseline; border: 1px solid var(--c-border); border-radius: var(--r-sm); padding: 4px 10px; font-size: 12px; }
.wf-metric .k { color: var(--c-text-3); }
.wf-metric .v { font-family: var(--ff-mono); font-weight: 600; }
.wf-note { margin: 8px 0 0; font-size: 11px; color: var(--c-text-3); line-height: 1.5; }
.wf-note code { font-family: var(--ff-mono); background: var(--c-bg-tint); padding: 1px 4px; border-radius: 3px; color: var(--c-text-2); }
</style>
