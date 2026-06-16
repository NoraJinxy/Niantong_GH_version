<template>
  <div ref="hostRef" class="tcc-host" :class="{ 'tcc-locked': locked }">
    <div v-if="loading" class="tcc-loading">加载中…</div>
  </div>
</template>

<script setup lang="ts">
// 时域 uPlot 宿主：只负责「拿数据画线 + 冒泡游标」，不持业务状态。
// 决策见 日志/10_观察作图与缓存架构260614/06 §4。1D 曲线统一走 uPlot（P-1）。
// 支持两种格内呈现：overlay(同轴叠加) / spread(纵向排列，多通道堆叠浏览)；
// 叠加层：统计区间着色 + 参考线(t=0/0µV) + 画内紧凑图例 + 多子图游标联动。
import { onMounted, onUnmounted, ref, shallowRef, watch, nextTick } from 'vue'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface SeriesCfg { name: string; color: string }
interface CursorItem { name: string; color: string; uv: number }

const props = withDefaults(
  defineProps<{
    /** uPlot AlignedData：[ x[], ...每条可见通道的 y[] ]。x 已是显示单位、y 已是 µV（父层换算好）。 */
    data: (number[])[]
    series: SeriesCfg[]
    xLabel?: string
    yLabel?: string
    /** null=自动；非 null=对称 ±yMax（µV）。spread 模式下作为每道幅值归一化的满量程。 */
    yMax?: number | null
    /** overlay=同轴叠加；spread=纵向排列（每道一条泳道）。 */
    displayMode?: 'overlay' | 'spread'
    showGrid?: boolean
    loading?: boolean
    /** 统计区间（x 显示单位）：在图上着色高亮，与右栏统计绑定。 */
    region?: { x0: number; x1: number } | null
    /** 画内紧凑图例（右上角）。 */
    showLegend?: boolean
    /** 参考线：t=0 竖线 + 0µV 基线（evoked/epochs 用）。 */
    refLines?: boolean
    /** 高亮某条序列（按名）：匹配的加粗、其余压细——点右栏行定位用。 */
    highlight?: string
    /** 密集坐标轴：多子图时去掉 μV/时间 标题、缩小刻度区，省空间。 */
    denseAxes?: boolean
    /** 共享 facet 轴：隐藏本格 x / y 刻度标签（保留刻度区宽度以对齐），只在边缘格显示。 */
    hideXLabels?: boolean
    hideYLabels?: boolean
    /** 锁定态：true 时隐藏跟随鼠标的实时游标（只保留锁定标记线，不随鼠标移动）。 */
    locked?: boolean
    /** 锁定时刻（x 显示单位）：非 null 时各子图在该处画一条常驻竖线。 */
    lockedX?: number | null
    /** 受控视图缩放（滚轮手势，父层广播给所有子图保持 facet 同窗）：x 可见范围（显示单位，null=数据全幅）。 */
    viewMin?: number | null
    viewMax?: number | null
    /** 幅度缩放系数（Ctrl+滚轮）：1=基准；overlay 改 y 量程、spread 改泳道波高。 */
    ampScale?: number
    /** 显式 y 量程 [min,max]（PSD dB 等非对称单位用）：非 null 时覆盖 ±yMax 对称量程；仅 overlay 生效。 */
    yDomain?: [number, number] | null
    /** 频段背景着色（PSD δθαβγ）：按 x 区间 [lo,hi] 画淡色带；active 加深。仅 overlay。 */
    bands?: { lo: number; hi: number; color: string; active?: boolean }[]
    /** 竖向标记（如 PSD 的 α 峰 / IAF）：在 x 处画虚线 + 顶部三角 + 标签。 */
    markers?: { x: number; label?: string; color?: string }[]
    /** 对数频率轴（PSD 看 1/f）：true=x 走对数刻度（uPlot distr=3，需正值）；默认线性。 */
    logX?: boolean
  }>(),
  { xLabel: '时间', yLabel: 'μV', yMax: null, displayMode: 'overlay', showGrid: true, loading: false, region: null, showLegend: true, refLines: false, highlight: '', denseAxes: false, hideXLabels: false, hideYLabels: false, locked: false, lockedX: null, viewMin: null, viewMax: null, ampScale: 1, yDomain: null, bands: () => [], markers: () => [], logX: false },
)

const emit = defineEmits<{
  (e: 'cursor', payload: { x: number; items: CursorItem[] } | null): void
  (e: 'select', region: { x0: number; x1: number } | null): void
  (e: 'lock', payload: { x: number; items: CursorItem[] }): void
  (e: 'unlock'): void
  /** 滚轮缩放时间轴：新可见范围（显示单位），null=退回全幅。父层广播给所有子图。 */
  (e: 'zoom', view: { min: number; max: number } | null): void
  /** Ctrl+滚轮调幅度：新幅度系数。 */
  (e: 'amp', scale: number): void
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<uPlot | null>(null)
let ro: ResizeObserver | null = null
// 游标 emit 合帧：uPlot 每次 pointermove 同步触发 setCursor；积一帧只 emit 一次、且采样下标变了才 emit，
// 把父层 topo / 右栏那条级联从「每次 mousemove」压到「每帧·每次跨采样」。
let cursorRaf = 0
let pendingIdx: number | null = null
let lastEmitIdx: number | null | undefined = undefined

// 画布内是 Canvas 绘制，CSS 变量不生效，必须用具体色值（对齐 elys token）。
const AXIS = '#51607A' // --c-text-2（原 text-3 #79859A ≈3:1 太淡，刻度数字/轴名拉到 AA 可读）
const GRID = '#D3DAE6' // --c-border-2（原 border #E4E9F1 ≈隐形，提一档让网格成形而不抢戏）
const REGION_FILL = 'rgba(63, 94, 143, 0.07)' // elys 主蓝低透明
const REGION_LINE = 'rgba(63, 94, 143, 0.32)'
const REF_LINE = '#C4CCD8'
const LOCK_LINE = '#D9822B' // 锁定标记：琥珀色，区别于参考线/区间
// uPlot 钩子里的 ctx 用「设备像素」坐标（bbox / valToPos(...,true) 均是），线宽/字号须按同一比例放大
// 用真实 dpr、上限 2：不再对 1x 屏强制 2x 超采样（白白多画 4 倍像素，弱机/多格直接拖垮）；>2x 屏封顶 2x 已够清晰。
const PX_RATIO = Math.min(window.devicePixelRatio || 1, 2)

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v
}

/** spread 归一化满量程：优先用 props.yMax，否则取数据峰值绝对值。 */
function effYMax(): number {
  if (props.yMax != null && props.yMax > 0) return props.yMax
  let m = 0
  for (let si = 1; si < props.data.length; si++) {
    const col = props.data[si] || []
    for (const v of col) m = Math.max(m, Math.abs(Number(v) || 0))
  }
  return Math.max(1, m)
}

/** 按显示模式生成喂给 uPlot 的数据（spread 会做泳道偏移；原始 µV 仍保留在 props.data 供游标读数）。 */
function buildDisplayData(): number[][] {
  if (props.displayMode !== 'spread') return props.data as number[][]
  const n = props.series.length
  const xs = props.data[0] || []
  // 幅度系数折进满量程：amp 越大→ey 越小→波形越高。不再限幅——曲线可超出本泳道、与相邻道重叠
  // （去掉「不能 overlap」的硬限制：原 clamp(±1) 把每道钉死在 ±0.45 泳道内，多通道时看着扁平）。
  // 用 0.9 的泳道填充（默认即明显起伏 + 轻度交叠），更密 / 更高靠 Ctrl+滚轮调幅。
  const amp = props.ampScale && props.ampScale > 0 ? props.ampScale : 1
  const ey = effYMax() / amp
  const out: number[][] = [xs]
  for (let si = 1; si <= n; si++) {
    const center = n - si // 第 i=si-1 道 → 泳道中心 n-1-i（首道在顶）
    const src = props.data[si] || []
    out.push(src.map((v) => center + ((Number(v) || 0) / ey) * 0.9))
  }
  return out
}

// 竖向标记（PSD α 峰 / IAF 等）：在 x 处画虚线 + 顶部三角 + 标签（series 之后画 → draw 钩子）
function drawMarkers(u: uPlot) {
  if (!props.markers || !props.markers.length) return
  const ctx = u.ctx
  const { left, top, width, height } = u.bbox
  ctx.save()
  ctx.font = `${11 * PX_RATIO}px monospace`
  ctx.textBaseline = 'top'
  ctx.textAlign = 'left'
  for (const m of props.markers) {
    if (!Number.isFinite(m.x)) continue
    const x = u.valToPos(m.x, 'x', true)
    if (x < left || x > left + width) continue
    const col = m.color || LOCK_LINE
    ctx.strokeStyle = col
    ctx.fillStyle = col
    ctx.lineWidth = 1.5 * PX_RATIO
    ctx.setLineDash([3 * PX_RATIO, 3 * PX_RATIO])
    ctx.beginPath()
    ctx.moveTo(x, top)
    ctx.lineTo(x, top + height)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(x - 4 * PX_RATIO, top)
    ctx.lineTo(x + 4 * PX_RATIO, top)
    ctx.lineTo(x, top + 6 * PX_RATIO)
    ctx.closePath()
    ctx.fill()
    if (m.label) ctx.fillText(m.label, x + 5 * PX_RATIO, top + 2 * PX_RATIO)
  }
  ctx.restore()
}

// 叠加层：统计区间着色 + 参考线（在 series 之前画 → drawClear 钩子）
function drawUnder(u: uPlot) {
  const ctx = u.ctx
  const { left, top, width, height } = u.bbox
  // 频段背景着色（PSD δθαβγ；最底层，先于区间/参考线/曲线）
  if (props.bands && props.bands.length && props.displayMode !== 'spread') {
    for (const b of props.bands) {
      const xa = clamp(u.valToPos(b.lo, 'x', true), left, left + width)
      const xb = clamp(u.valToPos(b.hi, 'x', true), left, left + width)
      if (xb <= xa) continue
      ctx.save()
      ctx.fillStyle = b.color
      ctx.globalAlpha = b.active ? 0.18 : 0.08
      ctx.fillRect(xa, top, xb - xa, height)
      ctx.restore()
    }
  }
  // 统计区间高亮
  const r = props.region
  if (r && r.x1 > r.x0) {
    const xa = clamp(u.valToPos(r.x0, 'x', true), left, left + width)
    const xb = clamp(u.valToPos(r.x1, 'x', true), left, left + width)
    if (xb > xa) {
      ctx.save()
      ctx.fillStyle = REGION_FILL
      ctx.fillRect(xa, top, xb - xa, height)
      ctx.strokeStyle = REGION_LINE
      ctx.lineWidth = PX_RATIO
      ctx.setLineDash([4 * PX_RATIO, 3 * PX_RATIO])
      ctx.strokeRect(xa, top, xb - xa, height)
      ctx.setLineDash([])
      ctx.restore()
    }
  }
  // 参考线：t=0 竖线 + 0µV 基线（仅 overlay；spread 是泳道无统一 0）
  if (props.refLines && props.displayMode !== 'spread') {
    ctx.save()
    ctx.strokeStyle = REF_LINE
    ctx.lineWidth = PX_RATIO
    const x0 = u.valToPos(0, 'x', true)
    if (x0 >= left && x0 <= left + width) {
      ctx.setLineDash([4 * PX_RATIO, 3 * PX_RATIO])
      ctx.beginPath()
      ctx.moveTo(x0, top)
      ctx.lineTo(x0, top + height)
      ctx.stroke()
      ctx.setLineDash([])
    }
    const y0 = u.valToPos(0, 'y', true)
    if (y0 >= top && y0 <= top + height) {
      ctx.beginPath()
      ctx.moveTo(left, y0)
      ctx.lineTo(left + width, y0)
      ctx.stroke()
    }
    ctx.restore()
  }
}

// 画内紧凑图例（series 之后画 → draw 钩子），右上角；带半透明背板防与曲线糊在一起
function drawLegend(u: uPlot) {
  if (!props.showLegend || props.series.length < 2 || props.displayMode === 'spread') return
  const ctx = u.ctx
  const { left, top, width } = u.bbox
  const dpr = PX_RATIO
  const max = 8
  const rowH = 15 * dpr
  const ipad = 6 * dpr // 块内边距
  const swatchW = 14 * dpr
  const gap = 6 * dpr
  ctx.save()
  ctx.font = `${12 * dpr}px var(--ff-mono, monospace)`
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  const items = props.series.slice(0, max).map((s) => ({
    color: s.color,
    label: s.name.length > 14 ? '…' + s.name.slice(-13) : s.name, // 截断保尾：留区分性的通道/序号后缀
  }))
  if (props.series.length > max) items.push({ color: '', label: `+${props.series.length - max}` })
  // 背板宽度按最长标签实测，避免硬编码留白或长名挤压
  let labelW = 0
  for (const it of items) labelW = Math.max(labelW, ctx.measureText(it.label).width)
  const blockW = swatchW + gap + labelW + ipad * 2
  const blockH = items.length * rowH + ipad * 2
  const bx = left + width - 6 * dpr - blockW
  const by = top + 6 * dpr
  ctx.fillStyle = 'rgba(255, 255, 255, 0.92)'
  ctx.fillRect(bx, by, blockW, blockH)
  ctx.strokeStyle = '#C4CCD8' // 实色卡片边（原 ≈ 网格色 → 卡片隐形）
  ctx.lineWidth = 1
  ctx.strokeRect(bx + 0.5, by + 0.5, blockW - 1, blockH - 1)
  let y = by + ipad + rowH / 2
  for (const it of items) {
    const sx = bx + ipad
    if (it.color) {
      ctx.strokeStyle = it.color
      ctx.lineWidth = 2 * dpr
      ctx.beginPath()
      ctx.moveTo(sx, y)
      ctx.lineTo(sx + swatchW, y)
      ctx.stroke()
      ctx.fillStyle = '#20293B' // --c-text：序列名要清晰可读
    } else {
      ctx.fillStyle = '#51607A' // --c-text-2：+N 溢出计数
    }
    ctx.fillText(it.label, sx + swatchW + gap, y)
    y += rowH
  }
  ctx.restore()
}

// 锁定标记：双击后在锁定时刻画常驻竖线（不随鼠标移动），各子图同位呈现
function drawLocked(u: uPlot) {
  if (props.lockedX == null) return
  const ctx = u.ctx
  const { left, top, width, height } = u.bbox
  const x = u.valToPos(props.lockedX, 'x', true)
  if (x < left || x > left + width) return
  ctx.save()
  ctx.strokeStyle = LOCK_LINE
  ctx.lineWidth = 1.5 * PX_RATIO
  ctx.beginPath()
  ctx.moveTo(x, top)
  ctx.lineTo(x, top + height)
  ctx.stroke()
  ctx.restore()
}

// x 数据真实极值（非退化）：每次重绘都从 u.data[0] 现算、强制 min<max。
// 规避 uPlot 偶发把某子图 x scale 留成 min===max（→ valToPos ±Inf → 曲线画到画外 → 空图）。
function xExtent(u: uPlot): [number, number] {
  const xs = u.data && (u.data[0] as number[] | undefined)
  if (xs && xs.length > 1) {
    let lo = Infinity
    let hi = -Infinity
    for (const v of xs) {
      if (v < lo) lo = v
      if (v > hi) hi = v
    }
    if (Number.isFinite(lo) && hi > lo) return [lo, hi]
    if (Number.isFinite(lo)) return [lo - 1, lo + 1]
  }
  return [0, 1]
}
// x 量程：优先受控视图（滚轮缩放，钳进数据范围），否则数据全幅。
// 声明式 range 比「创建后 setScale 一次」更稳——setSize / setData 都会再调它，缩放不会被自动量程覆盖回退化。
function xRange(u: uPlot): [number, number] {
  const ext = xExtent(u)
  const mn = props.viewMin
  const mx = props.viewMax
  if (mn != null && mx != null && mx > mn) {
    const lo = Math.max(ext[0], mn)
    const hi = Math.min(ext[1], mx)
    if (hi > lo) return [lo, hi]
  }
  return ext
}
// y 量程（仅 overlay）：基准(±yMax 或数据峰值) ÷ 幅度系数；spread 用固定泳道量程、幅度折进数据。
function yRange(u: uPlot): [number, number] {
  // 显式非对称量程（PSD dB 等）：直接用，不做 ±对称归一
  const yd = props.yDomain
  if (yd && yd[1] > yd[0]) return [yd[0], yd[1]]
  const amp = props.ampScale && props.ampScale > 0 ? props.ampScale : 1
  let base = props.yMax != null && props.yMax > 0 ? props.yMax : 0
  if (!base) {
    let m = 0
    for (let si = 1; si < u.data.length; si++) {
      const c = u.data[si] as number[]
      for (const v of c) m = Math.max(m, Math.abs(v))
    }
    base = Math.max(1, m)
  }
  const h = base / amp
  return [-h, h]
}

function buildOpts(w: number, h: number): uPlot.Options {
  const grid = props.showGrid
  const spread = props.displayMode === 'spread'
  const n = props.series.length
  // 高亮仅在「目标序列确实在本格」时生效，否则本格保持常规线宽（避免别的格被无谓压细）
  const hlActive = !!props.highlight && props.series.some((s) => s.name === props.highlight)
  const dense = props.denseAxes
  const axisFont = dense ? '11px var(--ff-mono, monospace)' : '13px var(--ff-mono, monospace)'
  // 共享 facet 轴：非边缘格把刻度标签置空（仍占同样刻度区宽度以对齐网格）
  const blank = (_u: uPlot, splits: number[]): string[] => splits.map(() => '')

  const yAxis: uPlot.Axis = spread
    ? {
        // 排列模式：y 轴显示通道名（在各泳道中心），不显示数值刻度
        stroke: AXIS,
        grid: { show: false },
        ticks: { show: false },
        size: 70,
        font: '12px var(--ff-mono, monospace)',
        splits: () => Array.from({ length: n }, (_, k) => k),
        values: (_u, splits) => splits.map((c) => props.series[n - 1 - Math.round(c)]?.name ?? ''),
      }
    : {
        label: dense ? undefined : props.yLabel,
        size: dense ? 40 : 56,
        stroke: AXIS,
        grid: { show: grid, stroke: GRID },
        ticks: { show: !props.hideYLabels, stroke: GRID },
        font: axisFont,
        values: props.hideYLabels ? blank : undefined,
      }

  // 框选区间用：drag 选区不缩放（setScale:false）。不开 cursor.sync——它会把 mousedown/up
  // 广播到每个子图、各自再处理一遍，踩坏框选（见排查：filters.pub 默认 retTrue）。
  // 游标常驻（show:true）：锁定态不再靠重建关游标，改用 CSS 隐藏十字线（.tcc-locked）+ 锁定时 setCursor 不再 emit。
  // points.show:false：关掉每条 series 跟随鼠标的游标点（54 条 = 54 个 DOM 每帧重定位，既卡又乱；读数本就走 setCursor 钩子）。
  const cursor: uPlot.Cursor = { show: true, points: { show: false }, drag: { x: true, y: false, setScale: false }, focus: { prox: 16 } }

  const opts: uPlot.Options = {
    width: w,
    height: h,
    legend: { show: false },
    cursor,
    scales: {
      x: { time: false, range: xRange, distr: props.logX ? 3 : 1 },
      y: spread ? { range: [-1, n] } : { range: yRange }, // spread 留 ±1 余量：曲线超出泳道交叠时首/末道不被裁掉
    },
    axes: [
      { label: dense ? undefined : props.xLabel, size: dense ? 30 : 44, stroke: AXIS, grid: { show: grid, stroke: GRID }, ticks: { show: !props.hideXLabels, stroke: GRID }, font: axisFont, values: props.hideXLabels ? blank : undefined },
      yAxis,
    ],
    series: [
      {},
      ...props.series.map((s) => ({
        label: s.name,
        stroke: s.color,
        // 命中本格高亮目标：加粗、其余压细；本格无该目标则统一 1.25
        width: hlActive ? (s.name === props.highlight ? 2.6 : 0.7) : 1.25,
        points: { show: false },
      })),
    ],
    hooks: {
      drawClear: [(u: uPlot) => drawUnder(u)],
      draw: [(u: uPlot) => { drawLegend(u); drawLocked(u); drawMarkers(u) }],
      setSelect: [
        (u: uPlot) => {
          const sel = u.select
          if (!sel || sel.width <= 2) {
            emit('select', null)
            return
          }
          const a = u.posToVal(sel.left, 'x')
          const b = u.posToVal(sel.left + sel.width, 'x')
          emit('select', { x0: Math.min(a, b), x1: Math.max(a, b) })
        },
      ],
      setCursor: [
        (u: uPlot) => {
          if (props.locked) return // 锁定态：读数冻结，不 emit / 不排帧
          // 只记下最新下标 + 排一帧；真正 emit 交给 flushCursor（每帧一次、下标变了才发）
          pendingIdx = (u.cursor.idx ?? null) as number | null
          if (!cursorRaf) cursorRaf = requestAnimationFrame(flushCursor)
        },
      ],
    },
  }
  // pxRatio：强制 ≥2x 超采样抗锯齿（uPlot 运行时支持，类型未声明 → 断言赋值）；1x 屏按 2 倍像素渲染再缩放，线条更细腻
  ;(opts as unknown as { pxRatio: number }).pxRatio = PX_RATIO
  return opts
}

// rAF 回调：emit 本帧最后的游标读数（永远报原始 µV，不受 spread 偏移影响）。
function flushCursor() {
  cursorRaf = 0
  if (!chart.value) return
  const idx = pendingIdx
  if (idx === lastEmitIdx) return // 下标没变 → 不重复 emit（省掉父层 topo / 右栏整轮重算）
  lastEmitIdx = idx
  if (idx == null) { emit('cursor', null); return }
  const xv = props.data[0]?.[idx]
  if (xv == null) { emit('cursor', null); return }
  const items: CursorItem[] = props.series.map((s, si) => ({
    name: s.name,
    color: s.color,
    uv: Number(props.data[si + 1]?.[idx] ?? 0),
  }))
  emit('cursor', { x: Number(xv), items })
}

// 高亮就地生效：只改各 series 线宽再 redraw（保留缩放/游标），不重建整图。
// （原来 highlight 进了重建监听 → 每次悬停右栏一行都 destroy+new 54 条 series，是头号卡顿源。）
function applyHighlight() {
  const u = chart.value
  if (!u) return
  const hlActive = !!props.highlight && props.series.some((s) => s.name === props.highlight)
  for (let i = 0; i < props.series.length; i++) {
    const us = u.series[i + 1] as unknown as { width?: number } | undefined
    if (!us) continue
    us.width = hlActive ? (props.series[i].name === props.highlight ? 2.6 : 0.7) : 1.25
  }
  u.redraw(false) // false=不重建路径，仅用现有路径按新线宽重描，最省
}

function rebuild() {
  const host = hostRef.value
  if (!host) return
  // 旧 chart 即将丢弃：清掉挂起的游标帧 + 下标记忆，避免回调对新图发陈旧读数
  if (cursorRaf) { cancelAnimationFrame(cursorRaf); cursorRaf = 0 }
  pendingIdx = null
  lastEmitIdx = undefined
  chart.value?.destroy()
  chart.value = null
  if (!props.series.length || !props.data[0]?.length) return
  const w = host.clientWidth || 800
  const h = host.clientHeight || 400
  const dd = buildDisplayData()
  chart.value = new uPlot(buildOpts(w, h), dd as unknown as uPlot.AlignedData, host)
}

// 双击锁定游标 / 右键解锁（锁定 state 由父层持有，本组件只发事件 + 收 locked/lockedX 入参）
function onHostDblClick() {
  const u = chart.value
  if (!u || props.locked) return
  const idx = u.cursor.idx
  if (idx == null) return
  const xv = props.data[0]?.[idx]
  if (xv == null) return
  const items: CursorItem[] = props.series.map((s, si) => ({ name: s.name, color: s.color, uv: Number(props.data[si + 1]?.[idx] ?? 0) }))
  emit('lock', { x: Number(xv), items })
}
function onHostContextMenu(e: MouseEvent) {
  e.preventDefault()
  emit('unlock')
}

// 滚轮缩放（绕游标处的时间轴）/ Ctrl+滚轮调幅度。
// 缩放态由父层持有并广播给所有子图 → facet 各格同窗；本格乐观就地应用，避免一帧延迟。
function onWheel(e: WheelEvent) {
  const u = chart.value
  if (!u) return
  e.preventDefault()
  // Ctrl/⌘ + 滚轮：调幅度（向上滚=波形放大）
  if (e.ctrlKey || e.metaKey) {
    const cur = props.ampScale && props.ampScale > 0 ? props.ampScale : 1
    let next = e.deltaY < 0 ? cur * 1.15 : cur / 1.15
    next = clamp(next, 0.1, 50)
    if (Math.abs(Math.log(next)) < 0.07) next = 1 // 回到基准附近吸附到 1×
    emit('amp', next)
    return
  }
  // 滚轮：缩放时间轴，保持游标下的时刻不动
  const ext = xExtent(u)
  const sx = u.scales.x as { min?: number; max?: number }
  const min = sx?.min ?? ext[0]
  const max = sx?.max ?? ext[1]
  if (!(max > min)) return
  let cx = u.posToVal(u.cursor.left ?? -1, 'x')
  if (!Number.isFinite(cx)) cx = (min + max) / 2
  cx = clamp(cx, min, max)
  const factor = e.deltaY < 0 ? 0.82 : 1 / 0.82 // 向上滚=放大（窗口收窄）
  let nmin = cx - (cx - min) * factor
  let nmax = cx + (max - cx) * factor
  nmin = Math.max(ext[0], nmin)
  nmax = Math.min(ext[1], nmax)
  const minSpan = (ext[1] - ext[0]) / 1000 // 防无限放大
  if (nmax - nmin < minSpan) {
    const c = (nmin + nmax) / 2
    nmin = c - minSpan / 2
    nmax = c + minSpan / 2
  }
  if (nmin <= ext[0] && nmax >= ext[1]) {
    emit('zoom', null) // 缩到全幅 → 退回自动
    u.setScale('x', { min: ext[0], max: ext[1] })
    return
  }
  emit('zoom', { min: nmin, max: nmax })
  u.setScale('x', { min: nmin, max: nmax }) // 本格乐观应用；兄弟格走父层广播
}

onMounted(async () => {
  await nextTick()
  rebuild()
  ro = new ResizeObserver(() => {
    const host = hostRef.value
    if (host && chart.value) chart.value.setSize({ width: host.clientWidth, height: host.clientHeight })
  })
  const host = hostRef.value
  if (host) {
    ro.observe(host)
    host.addEventListener('dblclick', onHostDblClick)
    host.addEventListener('contextmenu', onHostContextMenu)
    host.addEventListener('wheel', onWheel, { passive: false }) // passive:false 才能 preventDefault 阻止页面滚动
  }
})

onUnmounted(() => {
  if (cursorRaf) { cancelAnimationFrame(cursorRaf); cursorRaf = 0 }
  ro?.disconnect()
  ro = null
  const host = hostRef.value
  if (host) {
    host.removeEventListener('dblclick', onHostDblClick)
    host.removeEventListener('contextmenu', onHostContextMenu)
    host.removeEventListener('wheel', onWheel)
  }
  chart.value?.destroy()
  chart.value = null
})

// 数据/序列/Y档/显示模式/网格 = 结构性变化 → 重建（最稳）。
// highlight / locked 已移出：分别走「就地改线宽」与「CSS 隐藏十字线」，不再为悬停高亮 / 双击锁定整图重建。
watch(
  () => [props.data, props.series, props.yMax, props.displayMode, props.showGrid, props.denseAxes, props.hideXLabels, props.hideYLabels, props.logX],
  () => rebuild(),
  { deep: false },
)
// 高亮 = 就地改线宽 + redraw（不重建）。
watch(() => props.highlight, () => applyHighlight())
// 区间/图例/参考线/锁定标记 = 轻量重绘（不重建，保留缩放/游标）。
watch(
  () => [props.region, props.showLegend, props.refLines, props.lockedX, props.bands, props.markers],
  () => chart.value?.redraw(),
  { deep: true },
)
// 受控视图缩放（滚轮，父层广播）→ 就地 setScale x，不重建（保留游标 / 高亮）。
watch(
  () => [props.viewMin, props.viewMax],
  () => {
    const u = chart.value
    if (!u) return
    const [mn, mx] = xRange(u)
    u.setScale('x', { min: mn, max: mx })
  },
)
// 幅度系数（Ctrl+滚轮）→ overlay 改 y 量程；spread 改泳道波高（重灌数据，x 视图由 range 函数保留）。
watch(
  () => props.ampScale,
  () => {
    const u = chart.value
    if (!u) return
    if (props.displayMode === 'spread') u.setData(buildDisplayData() as unknown as uPlot.AlignedData)
    else { const [mn, mx] = yRange(u); u.setScale('y', { min: mn, max: mx }) }
  },
)
// 显式 y 量程变化（PSD 切频窗/通道致 dB 范围变）→ overlay 就地 setScale y（不重建，保留缩放/游标）。
watch(
  () => props.yDomain,
  () => {
    const u = chart.value
    if (!u || props.displayMode === 'spread') return
    const [mn, mx] = yRange(u)
    u.setScale('y', { min: mn, max: mx })
  },
  { deep: true },
)
</script>

<style scoped>
.tcc-host { position: relative; width: 100%; height: 100%; min-height: 0; }
.tcc-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--c-text-3); font-size: 13px; }
/* 锁定态：隐藏跟随鼠标的十字线（琥珀锁定标记线由 drawLocked 画在 canvas 上，不受影响） */
.tcc-locked :deep(.u-cursor-x),
.tcc-locked :deep(.u-cursor-y) { display: none !important; }
</style>
