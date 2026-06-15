<template>
  <div ref="hostRef" class="tcc-host">
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
    /** 多子图游标联动的同步键（同键的子图共享游标 x）。 */
    syncKey?: string
  }>(),
  { xLabel: '时间', yLabel: 'μV', yMax: null, displayMode: 'overlay', showGrid: true, loading: false, region: null, showLegend: true, refLines: false, syncKey: '' },
)

const emit = defineEmits<{
  (e: 'cursor', payload: { x: number; items: CursorItem[] } | null): void
  (e: 'select', region: { x0: number; x1: number } | null): void
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<uPlot | null>(null)
let ro: ResizeObserver | null = null

// 画布内是 Canvas 绘制，CSS 变量不生效，必须用具体色值（对齐 elys token）。
const AXIS = '#79859A' // --c-text-3
const GRID = '#E4E9F1' // --c-border
const REGION_FILL = 'rgba(63, 94, 143, 0.07)' // elys 主蓝低透明
const REGION_LINE = 'rgba(63, 94, 143, 0.32)'
const REF_LINE = '#C4CCD8'
// uPlot 钩子里的 ctx 用「设备像素」坐标（bbox / valToPos(...,true) 均是），线宽/字号须按同一比例放大
const PX_RATIO = Math.max(window.devicePixelRatio || 1, 2)

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
  const ey = effYMax()
  const out: number[][] = [xs]
  for (let si = 1; si <= n; si++) {
    const center = n - si // 第 i=si-1 道 → 泳道中心 n-1-i（首道在顶）
    const src = props.data[si] || []
    out.push(src.map((v) => center + clamp((Number(v) || 0) / ey, -1, 1) * 0.45))
  }
  return out
}

// 叠加层：统计区间着色 + 参考线（在 series 之前画 → drawClear 钩子）
function drawUnder(u: uPlot) {
  const ctx = u.ctx
  const { left, top, width, height } = u.bbox
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

// 画内紧凑图例（series 之后画 → draw 钩子），右上角
function drawLegend(u: uPlot) {
  if (!props.showLegend || props.series.length < 2 || props.displayMode === 'spread') return
  const ctx = u.ctx
  const { left, top, width } = u.bbox
  const dpr = PX_RATIO
  const max = 8
  const rowH = 13 * dpr
  const pad = 6 * dpr
  ctx.save()
  ctx.font = `${10 * dpr}px var(--ff-mono, monospace)`
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  const items = props.series.slice(0, max)
  let y = top + pad + rowH / 2
  for (const s of items) {
    const tx = left + width - pad - 86 * dpr
    ctx.strokeStyle = s.color
    ctx.lineWidth = 2 * dpr
    ctx.beginPath()
    ctx.moveTo(tx, y)
    ctx.lineTo(tx + 12 * dpr, y)
    ctx.stroke()
    ctx.fillStyle = '#57636F'
    const label = s.name.length > 12 ? s.name.slice(0, 11) + '…' : s.name
    ctx.fillText(label, tx + 16 * dpr, y)
    y += rowH
  }
  if (props.series.length > max) {
    ctx.fillStyle = '#9AA4B0'
    ctx.fillText(`+${props.series.length - max}`, left + width - pad - 86 * dpr + 16 * dpr, y)
  }
  ctx.restore()
}

function buildOpts(w: number, h: number): uPlot.Options {
  const grid = props.showGrid
  const spread = props.displayMode === 'spread'
  const n = props.series.length

  const yAxis: uPlot.Axis = spread
    ? {
        // 排列模式：y 轴显示通道名（在各泳道中心），不显示数值刻度
        stroke: AXIS,
        grid: { show: false },
        ticks: { show: false },
        size: 64,
        font: '11px var(--ff-mono, monospace)',
        splits: () => Array.from({ length: n }, (_, k) => k),
        values: (_u, splits) => splits.map((c) => props.series[n - 1 - Math.round(c)]?.name ?? ''),
      }
    : {
        label: props.yLabel,
        stroke: AXIS,
        grid: { show: grid, stroke: GRID },
        ticks: { stroke: GRID },
        font: '11px var(--ff-mono, monospace)',
      }

  const cursor: uPlot.Cursor = { drag: { x: true, y: false, setScale: false }, focus: { prox: 16 } }
  if (props.syncKey) cursor.sync = { key: props.syncKey }

  const opts: uPlot.Options = {
    width: w,
    height: h,
    legend: { show: false },
    cursor,
    scales: {
      x: { time: false },
      y: spread
        ? { range: [-0.6, n - 0.4] }
        : props.yMax != null
          ? { range: [-props.yMax, props.yMax] }
          : {},
    },
    axes: [
      { label: props.xLabel, stroke: AXIS, grid: { show: grid, stroke: GRID }, ticks: { stroke: GRID }, font: '11px var(--ff-mono, monospace)' },
      yAxis,
    ],
    series: [
      {},
      ...props.series.map((s) => ({ label: s.name, stroke: s.color, width: 1.25, points: { show: false } })),
    ],
    hooks: {
      drawClear: [(u: uPlot) => drawUnder(u)],
      draw: [(u: uPlot) => drawLegend(u)],
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
          const idx = u.cursor.idx
          if (idx == null) {
            emit('cursor', null)
            return
          }
          // 读数永远报「原始 µV」（props.data），不受 spread 偏移影响
          const xv = props.data[0]?.[idx]
          if (xv == null) {
            emit('cursor', null)
            return
          }
          const items: CursorItem[] = props.series.map((s, si) => ({
            name: s.name,
            color: s.color,
            uv: Number(props.data[si + 1]?.[idx] ?? 0),
          }))
          emit('cursor', { x: Number(xv), items })
        },
      ],
    },
  }
  // pxRatio：强制 ≥2x 超采样抗锯齿（uPlot 运行时支持，类型未声明 → 断言赋值）；1x 屏按 2 倍像素渲染再缩放，线条更细腻
  ;(opts as unknown as { pxRatio: number }).pxRatio = PX_RATIO
  return opts
}

function rebuild() {
  const host = hostRef.value
  if (!host) return
  chart.value?.destroy()
  chart.value = null
  if (!props.series.length || !props.data[0]?.length) return
  const w = host.clientWidth || 800
  const h = host.clientHeight || 400
  chart.value = new uPlot(buildOpts(w, h), buildDisplayData() as unknown as uPlot.AlignedData, host)
}

onMounted(async () => {
  await nextTick()
  rebuild()
  ro = new ResizeObserver(() => {
    const host = hostRef.value
    if (host && chart.value) chart.value.setSize({ width: host.clientWidth, height: host.clientHeight })
  })
  if (hostRef.value) ro.observe(hostRef.value)
})

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  chart.value?.destroy()
  chart.value = null
})

// 数据/序列/Y档/显示模式/网格/联动键 = 结构性变化 → 重建（最稳）。
watch(
  () => [props.data, props.series, props.yMax, props.displayMode, props.showGrid, props.syncKey],
  () => rebuild(),
  { deep: false },
)
// 区间/图例/参考线 = 轻量重绘（不重建，保留缩放/游标）。
watch(
  () => [props.region, props.showLegend, props.refLines],
  () => chart.value?.redraw(),
  { deep: true },
)
</script>

<style scoped>
.tcc-host { position: relative; width: 100%; height: 100%; min-height: 0; }
.tcc-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--c-text-3); font-size: 13px; }
</style>
