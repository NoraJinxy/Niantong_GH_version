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
            <template v-if="ts?.segment_label">
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
      <!-- 段（epoch / 条件）选择 -->
      <template v-if="hasSegments">
        <span class="wf-lbl">{{ segKindLabel }}</span>
        <button class="wf-step" :disabled="loading || segIndex <= 0" @click="stepSeg(-1)" title="上一个">‹</button>
        <select
          v-if="segOptions"
          class="wf-sel"
          :value="segIndex"
          :disabled="loading"
          @change="onSegSelect"
        >
          <option v-for="(o, i) in segOptions" :key="i" :value="i">{{ o }}</option>
        </select>
        <span v-else class="wf-seg-idx text-mono">{{ segIndex + 1 }} / {{ ts?.n_segments }}</span>
        <button class="wf-step" :disabled="loading || segIndex >= (ts?.n_segments || 1) - 1" @click="stepSeg(1)" title="下一个">›</button>
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
      <label class="wf-chk"><input type="checkbox" v-model="showGrid" />网格</label>
      <label class="wf-chk"><input type="checkbox" v-model="showZero" />基线/起始</label>

      <div style="flex: 1"></div>
      <span class="wf-readout" v-if="cursor">
        <span class="text-mono">{{ fmtX(cursor.x) }} {{ xUnit }}</span>
        <span v-for="it in cursor.items.slice(0, 6)" :key="it.name" class="wf-readout-v" :style="{ color: it.color }">
          {{ it.name }} {{ it.uv.toFixed(2) }}
        </span>
        <span v-if="cursor.items.length > 6" class="wf-readout-more">+{{ cursor.items.length - 6 }}</span>
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
        <!-- 左侧通道 listbox（参考 LoadData Include 风格） -->
        <aside class="wf-chanbox">
          <div class="wf-chanbox-header">
            <strong>通道</strong>
            <span class="wf-chanbox-count">{{ selected.size }}/{{ plot.chans.length }}</span>
            <button v-if="selected.size < plot.chans.length" type="button" class="wf-chanbox-link" @click="selectAll">全选</button>
            <button v-if="selected.size > 0" type="button" class="wf-chanbox-link" @click="selectNone">清空</button>
          </div>
          <div ref="chanListRef" class="wf-chanlist" tabindex="0">
            <div
              v-for="(c, i) in plot.chans"
              :key="c.name"
              class="wf-chanitem"
              :class="{ 'is-sel': selected.has(c.name) }"
              @click="onChannelClick(i, $event)"
            >
              <span class="wf-leg-dot" :style="{ background: c.color }"></span>
              <span class="wf-chanitem-name">{{ c.name }}</span>
            </div>
          </div>
          <p class="wf-chanbox-hint" v-if="ts && ts.n_channels_total > plot.chans.length">
            仅列出前 {{ plot.chans.length }} / {{ ts.n_channels_total }} 通道
          </p>
          <p class="wf-chanbox-hint" v-else>单击 · Ctrl 加减 · Shift 连选 · Ctrl+A 全选</p>
        </aside>

        <!-- 右侧绘图 -->
        <div class="wf-plot-area">
          <div class="wf-plot-wrap">
            <svg
              ref="svgEl"
              class="wf-plot"
              :viewBox="`0 0 ${VBW} ${VBH}`"
              preserveAspectRatio="xMidYMid meet"
              @mousemove="onMove"
              @mouseleave="cursorX = null"
            >
              <rect :x="M.l" :y="M.t" :width="plotW" :height="plotH" fill="#fff" stroke="var(--c-border)" />

              <g>
                <g v-for="t in render.yTicks" :key="'y' + t.v">
                  <line
                    v-if="showGrid || t.v === 0"
                    :x1="M.l" :y1="t.y" :x2="M.l + plotW" :y2="t.y"
                    :stroke="t.v === 0 ? 'var(--c-border-2)' : 'var(--c-border)'"
                    :stroke-dasharray="t.v === 0 ? '0' : '3 3'"
                  />
                  <text :x="M.l - 8" :y="t.y + 3" class="wf-axis" text-anchor="end">{{ t.v }}</text>
                </g>
                <text :x="14" :y="M.t + 12" class="wf-axis-unit">μV</text>
              </g>

              <g>
                <g v-for="t in render.xTicks" :key="'x' + t.x">
                  <line v-if="showGrid" :x1="t.x" :y1="M.t" :x2="t.x" :y2="M.t + plotH" stroke="var(--c-border)" stroke-dasharray="3 3" />
                  <text :x="t.x" :y="M.t + plotH + 16" class="wf-axis" text-anchor="middle">{{ t.label }}</text>
                </g>
                <text :x="M.l + plotW" :y="M.t + plotH + 32" class="wf-axis-unit" text-anchor="end">时间 ({{ xUnit }})</text>
              </g>

              <line v-if="showZero && render.zeroX !== null" :x1="render.zeroX" :y1="M.t" :x2="render.zeroX" :y2="M.t + plotH" stroke="var(--c-danger)" stroke-width="1.1" stroke-dasharray="4 3" />
              <text v-if="showZero && render.zeroX !== null" :x="render.zeroX + 4" :y="M.t + 12" class="wf-stim">0</text>

              <g :clip-path="`url(#${clipId})`">
                <path v-for="c in render.lines" :key="c.name" :d="c.d" :stroke="c.color" stroke-width="1.5" fill="none" />
              </g>
              <clipPath :id="clipId"><rect :x="M.l" :y="M.t" :width="plotW" :height="plotH" /></clipPath>

              <g v-if="cursor">
                <line :x1="cursor.px" :y1="M.t" :x2="cursor.px" :y2="M.t + plotH" stroke="var(--c-text-3)" stroke-width="1" stroke-dasharray="2 2" />
                <circle v-for="it in cursor.items" :key="'c' + it.name" :cx="cursor.px" :cy="it.y" r="2.6" :fill="it.color" stroke="#fff" stroke-width="1.2" />
              </g>
            </svg>
          </div>
          <div v-if="!selected.size" class="wf-empty-hint">未选择通道 —— 在左侧列表里选择要绘制的通道</div>
        </div>
      </template>

      <div v-else class="wf-state">该数据没有可绘制的通道曲线。</div>
    </div>

    <!-- 底部摘要 -->
    <footer class="wf-foot" v-if="ts && !error">
      <div class="wf-metrics">
        <div class="wf-metric"><span class="k">类型</span><span class="v">{{ dataType }}</span></div>
        <div class="wf-metric"><span class="k">sfreq</span><span class="v">{{ ts.sfreq.toFixed(0) }} Hz</span></div>
        <div class="wf-metric"><span class="k">通道</span><span class="v">{{ plot.chans.length }}/{{ ts.n_channels_total }}</span></div>
        <div class="wf-metric"><span class="k">窗口</span><span class="v">{{ fmtX(ts.tmin * xFactor) }}–{{ fmtX(ts.tmax * xFactor) }} {{ xUnit }}</span></div>
        <div class="wf-metric" v-if="hasSegments"><span class="k">{{ segKindLabel }}</span><span class="v">{{ segIndex + 1 }}/{{ ts.n_segments }}</span></div>
        <div class="wf-metric"><span class="k">可用</span><span class="v">{{ fmtX(ts.available_tmin * xFactor) }}–{{ fmtX(ts.available_tmax * xFactor) }} {{ xUnit }}</span></div>
      </div>
      <p class="wf-note">
        数据来自 <code>GET /studies/&#123;id&#125;/outputs/&#123;dd&#125;/timeseries</code>，按时间窗 / 段 / 通道下采样（每通道最多 {{ MAX_POINTS }} 点、最多 {{ MAX_CHANNELS }} 通道）。
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { pipelineApi } from '@/api/pipelines'
import type { StudyOutputTimeseries } from '@/types'

const route = useRoute()

// ---------- 绘图几何 ----------
const VBW = 940
const VBH = 460
const M = { l: 60, r: 26, t: 22, b: 42 }
const plotW = VBW - M.l - M.r
const plotH = VBH - M.t - M.b
const clipId = 'wf-clip'

const MAX_CHANNELS = 64
const MAX_POINTS = 800 // 屏幕宽 ~850px，再多点也看不出来，少取点显著加快后端序列化/传输/渲染
const CONTINUOUS = ['raw', 'filtered_raw', 'ica_cleaned']
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
const studyId = qstr('study')
const datasetId = qstr('dd')
const nameHint = qstr('name')
const typeHint = qstr('type')

// ---------- 状态 ----------
const ts = ref<StudyOutputTimeseries | null>(null)
const loading = ref(true)
const error = ref('')
const segIndex = ref(0)
const reqTmin = ref<number | null>(null) // 秒
const reqTmax = ref<number | null>(null)
const winLoInput = ref<number | string>('') // 显示单位
const winHiInput = ref<number | string>('')
const yScaleIdx = ref(0)
const showGrid = ref(true)
const showZero = ref(true)
const cursorX = ref<number | null>(null) // 显示单位
const selected = ref<Set<string>>(new Set())
const anchorIndex = ref(-1)
const svgEl = ref<SVGSVGElement | null>(null)
const chanListRef = ref<HTMLDivElement | null>(null)

// ---------- 类型 / 单位 ----------
const dataType = computed(() => String(ts.value?.data_type ?? typeHint ?? '').toLowerCase())
const isContinuous = computed(() => CONTINUOUS.includes(dataType.value))
const xUnit = computed(() => (isContinuous.value ? 's' : 'ms'))
const xFactor = computed(() => (isContinuous.value ? 1 : 1000)) // 后端秒 → 显示单位
const xStep = computed(() => (isContinuous.value ? 0.5 : 50))
const xPrec = computed(() => (isContinuous.value ? 3 : 0))

const dataTypeLabel = computed(() => DATA_TYPE_LABELS[dataType.value] ?? (dataType.value || '派生数据'))
const typeShort = computed(() => (dataType.value === 'evoked' ? 'ERP' : dataType.value.slice(0, 3).toUpperCase() || 'DD'))
const typeColor = computed(() => (dataType.value === 'evoked' ? '#2E6BFF' : isContinuous.value ? '#0891B2' : '#8B5CF6'))
const displayName = computed(() => nameHint || dataTypeLabel.value)

const hasSegments = computed(() => !!ts.value?.n_segments && (ts.value?.n_segments || 0) > 1)
const segKindLabel = computed(() => (ts.value?.segment_kind === 'condition' ? '条件' : 'Epoch'))
const segOptions = computed(() => ts.value?.segment_options ?? null)

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

// ---------- 拉取时域数据 ----------
async function load() {
  if (!studyId || !datasetId) {
    error.value = '缺少参数：需要 study 和 dd（派生数据 ID）。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await pipelineApi.getStudyOutputTimeseries(studyId, datasetId, {
      index: segIndex.value,
      tmin: reqTmin.value ?? undefined,
      tmax: reqTmax.value ?? undefined,
      maxPoints: MAX_POINTS,
      maxChannels: MAX_CHANNELS,
    })
    ts.value = res.data
    if (res.data.segment_index != null) segIndex.value = res.data.segment_index
    winLoInput.value = round(res.data.tmin * xFactor.value, xPrec.value)
    winHiInput.value = round(res.data.tmax * xFactor.value, xPrec.value)
    document.title = `时域 · ${displayName.value} — 念析`
  } catch (err: unknown) {
    ts.value = null
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
  if (status === 404) return '该派生数据的文件不存在或已被清理（可能是未保留的中间结果）。'
  if (status === 409) return '文件校验和与记录不一致，数据可能已损坏。'
  if (status === 400) return serverMsg || '该数据类型不支持时域曲线。'
  if (status === 422) return serverMsg || '该派生数据缺少可解析的存储路径或为空。'
  return serverMsg || '读取时域数据失败，请稍后重试。'
}

// ---------- 控制动作 ----------
function applyWindow() {
  reqTmin.value = (() => {
    const n = toNum(winLoInput.value)
    return n === null ? null : n / xFactor.value
  })()
  reqTmax.value = (() => {
    const n = toNum(winHiInput.value)
    return n === null ? null : n / xFactor.value
  })()
  void load()
}
function resetWindow() {
  reqTmin.value = null
  reqTmax.value = null
  void load()
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
  void load()
}
function setSeg(i: number) {
  segIndex.value = i
  reqTmin.value = null // 切段时回到完整窗口
  reqTmax.value = null
  void load()
}
function stepSeg(d: number) {
  const n = ts.value?.n_segments || 1
  const next = Math.max(0, Math.min(n - 1, segIndex.value + d))
  if (next !== segIndex.value) setSeg(next)
}
function onSegSelect(e: Event) {
  setSeg(Number((e.target as HTMLSelectElement).value))
}

// ---------- 解析曲线 ----------
const uvScale = computed(() => {
  let maxAbs = 0
  for (const c of ts.value?.channels || []) for (const v of c.values) maxAbs = Math.max(maxAbs, Math.abs(v))
  return maxAbs > 0 && maxAbs < 0.01 ? 1e6 : 1
})

const plot = computed(() => {
  const t = ts.value
  if (!t || !t.channels.length) return { chans: [] as { name: string; color: string; pts: { x: number; uv: number }[] }[], xMin: 0, xMax: 1 }
  const scale = uvScale.value
  const xs = t.times.map((s) => s * xFactor.value)
  const chans = t.channels.map((c, i) => ({
    name: c.name,
    color: `hsl(${Math.round((i * 137.508) % 360)}, 62%, 47%)`,
    pts: c.values.map((v, j) => ({ x: xs[j] ?? 0, uv: v * scale })),
  }))
  return { chans, xMin: xs.length ? xs[0] : 0, xMax: xs.length ? xs[xs.length - 1] : 1 }
})

const hasCurves = computed(() => plot.value.chans.length > 0 && plot.value.chans[0].pts.length > 1)
const visibleChans = computed(() => plot.value.chans.filter((c) => selected.value.has(c.name)))

const autoYMax = computed(() => {
  let m = 0
  for (const c of visibleChans.value) for (const p of c.pts) m = Math.max(m, Math.abs(p.uv))
  return Math.max(2, Math.ceil((m * 1.2) / 2) * 2)
})

function niceStep(span: number): number {
  const target = span / 6 || 1
  const pow = Math.pow(10, Math.floor(Math.log10(target)))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * pow >= target) return m * pow
  return 10 * pow
}

const render = computed(() => {
  const xMin = plot.value.xMin
  const xMax = plot.value.xMax
  const span = xMax - xMin || 1
  const yMax = Y_SCALES[yScaleIdx.value].max || autoYMax.value
  const xOf = (x: number) => M.l + ((x - xMin) / span) * plotW
  const yOf = (uv: number) => M.t + ((yMax - uv) / (2 * yMax)) * plotH

  const lines = visibleChans.value.map((c) => {
    let d = ''
    c.pts.forEach((p, i) => {
      d += (i === 0 ? 'M' : 'L') + xOf(p.x).toFixed(1) + ',' + yOf(p.uv).toFixed(1) + ' '
    })
    return { name: c.name, color: c.color, d }
  })

  const yTicks = [-yMax, -yMax / 2, 0, yMax / 2, yMax].map((v) => ({ v, y: yOf(v) }))

  const step = niceStep(span)
  const xTicks: { x: number; label: number }[] = []
  const start = Math.ceil(xMin / step) * step
  for (let t = start; t <= xMax + step * 0.01; t += step) xTicks.push({ x: xOf(t), label: Number(t.toFixed(xPrec.value)) })

  const zeroX = xMin <= 0 && xMax >= 0 ? xOf(0) : null
  return { xMin, xMax, yMax, xOf, yOf, lines, yTicks, xTicks, zeroX }
})

// ---------- 通道选择 ----------
function channelNames(): string[] {
  return plot.value.chans.map((c) => c.name)
}
function onChannelClick(index: number, e: MouseEvent) {
  const names = channelNames()
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
  const names = channelNames()
  selected.value = new Set(names)
  anchorIndex.value = names.length - 1
}
function selectNone() {
  selected.value = new Set()
}

watch(
  () => channelNames().join(''),
  (key) => {
    if (!key) return
    if (selected.value.size === 0) {
      const names = channelNames()
      const init = names.slice(0, Math.min(names.length, DEFAULT_SELECT))
      selected.value = new Set(init)
      anchorIndex.value = init.length - 1
    }
  },
  { immediate: true },
)

// ---------- 悬停游标 ----------
function onMove(e: MouseEvent) {
  const svg = svgEl.value
  if (!svg) return
  const rect = svg.getBoundingClientRect()
  const scale = Math.min(rect.width / VBW, rect.height / VBH)
  const offX = (rect.width - VBW * scale) / 2
  const offY = (rect.height - VBH * scale) / 2
  const vx = (e.clientX - rect.left - offX) / scale
  const vy = (e.clientY - rect.top - offY) / scale
  if (vx < M.l || vx > M.l + plotW || vy < M.t || vy > M.t + plotH) {
    cursorX.value = null
    return
  }
  const r = render.value
  cursorX.value = r.xMin + ((vx - M.l) / plotW) * (r.xMax - r.xMin)
}

const cursor = computed(() => {
  if (cursorX.value === null || !hasCurves.value || !visibleChans.value.length) return null
  const r = render.value
  const x = cursorX.value
  const items = visibleChans.value.map((c) => {
    let best = c.pts[0]
    for (const p of c.pts) if (Math.abs(p.x - x) < Math.abs(best.x - x)) best = p
    return { name: c.name, color: c.color, uv: best.uv, y: r.yOf(best.uv) }
  })
  return { x, px: r.xOf(x), items }
})

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

/* 左侧通道 listbox —— 参考 LoadData 节点 Include/Exclude 列表风格 */
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

/* 右侧绘图 */
.wf-plot-area { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.wf-plot-wrap { flex: 1; display: flex; align-items: center; justify-content: center; padding: 14px 16px 4px; min-height: 0; }
.wf-plot { width: 100%; height: 100%; }
.wf-axis { font-size: 10px; fill: var(--c-text-3); font-family: var(--ff-mono); }
.wf-axis-unit { font-size: 10px; fill: var(--c-text-2); }
.wf-stim { font-size: 9px; fill: var(--c-danger); font-family: var(--ff-mono); }
.wf-empty-hint { text-align: center; color: var(--c-text-3); font-size: 12px; padding: 8px 0 12px; }

.wf-foot { background: var(--c-surface); border-top: 1px solid var(--c-border); padding: 10px 16px; }
.wf-metrics { display: flex; gap: 8px; flex-wrap: wrap; }
.wf-metric { display: flex; gap: 6px; align-items: baseline; border: 1px solid var(--c-border); border-radius: var(--r-sm); padding: 4px 10px; font-size: 12px; }
.wf-metric .k { color: var(--c-text-3); }
.wf-metric .v { font-family: var(--ff-mono); font-weight: 600; }
.wf-note { margin: 8px 0 0; font-size: 11px; color: var(--c-text-3); line-height: 1.5; }
.wf-note code { font-family: var(--ff-mono); background: var(--c-bg-tint); padding: 1px 4px; border-radius: 3px; color: var(--c-text-2); }
</style>
