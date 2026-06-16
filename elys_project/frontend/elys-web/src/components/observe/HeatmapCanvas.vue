<template>
  <div ref="hostRef" class="hmc-host" :class="{ 'hmc-locked': locked }">
    <canvas ref="canvasRef" class="hmc-cv"></canvas>
    <div v-if="loading" class="hmc-loading">加载中…</div>
  </div>
</template>

<script setup lang="ts">
// 时频热图宿主：原生 Canvas 画「频率 × 时间 → 功率(颜色)」面 + 冒泡游标/框选/缩放。
// 与时域/PSD 的 TimeCourseCanvas 对称：本组件只画图 + 发事件，不持业务状态。
// 决策见对话设计：TFR 第三维(功率)走颜色 → 不能像 1D 那样叠加，每通道一张面（父层分面）。
// 渲染：原始矩阵(nT×nF)烤进离屏 ImageData，再 drawImage 按视窗子矩形拉伸+双线性插值到绘图区（MNE 风平滑面）。
// 性能：底图(面+轴+频段线+刺激线)缓存在 baseCv，鼠标移动只 blit 底图 + 叠十字线，不重算面。
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { buildHeatmapLut, HEATMAP_LUT_N, type HeatmapCmap } from './heatmapColor'

interface Roi {
  t0: number
  t1: number
  f0: number
  f1: number
}

const props = withDefaults(
  defineProps<{
    /** 功率矩阵 power[iF][iT]，iF 低频→高频（freqs 升序），已按展示单位缩放。 */
    power: number[][]
    /** 频率轴（升序，Hz），与 power 行对齐。 */
    freqs: number[]
    /** 时间轴（升序，s），与 power 列对齐。 */
    times: number[]
    /** 色阶上界：rdbu 用对称 ±zmax、viridis 用 0..zmax。父层跨格取共享值保证可比。 */
    zmax: number
    cmap?: HeatmapCmap
    unit?: string
    showGrid?: boolean
    /** 刺激线：t=0 处画红色竖线（事件相关时频用）。 */
    tZero?: boolean
    denseAxes?: boolean
    hideXLabels?: boolean
    hideYLabels?: boolean
    loading?: boolean
    /** ROI 选区（时窗×频窗）：高亮 + 与右栏区间统计绑定。 */
    region?: Roi | null
    /** 锁定态：隐藏跟随鼠标的实时十字，只留锁定标记。 */
    locked?: boolean
    lockedT?: number | null
    lockedF?: number | null
    /** 受控时窗缩放（父层广播给所有格保持同窗）：null=数据全幅。 */
    viewTMin?: number | null
    viewTMax?: number | null
    /** 受控频窗（工具条输入）：null=数据全幅。 */
    viewFMin?: number | null
    viewFMax?: number | null
  }>(),
  {
    cmap: 'rdbu',
    unit: 'dB',
    showGrid: true,
    tZero: true,
    denseAxes: false,
    hideXLabels: false,
    hideYLabels: false,
    loading: false,
    region: null,
    locked: false,
    lockedT: null,
    lockedF: null,
    viewTMin: null,
    viewTMax: null,
    viewFMin: null,
    viewFMax: null,
  },
)

const emit = defineEmits<{
  (e: 'cursor', payload: { t: number; f: number; value: number } | null): void
  (e: 'select', region: Roi | null): void
  (e: 'lock', payload: { t: number; f: number; value: number }): void
  (e: 'unlock'): void
  /** 滚轮缩放时间轴：新可见范围（s），null=退回全幅。父层广播给所有格。 */
  (e: 'zoom', view: { min: number; max: number } | null): void
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

const AXIS = '#51607A'
const TICK = '#AEB7C6' // 刻度线 + 边框（克制，对标 matplotlib spine/tick）
const GRID_SOFT = 'rgba(120, 140, 170, 0.14)' // 可选淡网格（开「网格线」才画，默认关）
const LOCK_LINE = '#D9822B'
const STIM_LINE = '#D43F34' // 刺激线 t=0：红
const REGION_FILL = 'rgba(63, 94, 143, 0.10)'
const REGION_LINE = 'rgba(63, 94, 143, 0.55)'
const PX_RATIO = Math.min(window.devicePixelRatio || 1, 2)

let lut = buildHeatmapLut(props.cmap)
// 离屏：原始矩阵着色面（nT×nF，1px/格），按需 drawImage 拉伸
let matrixCv: HTMLCanvasElement | null = null
// 底图缓存（面+轴+频段线+刺激线），鼠标移动只 blit 它
let baseCv: HTMLCanvasElement | null = null
let ro: ResizeObserver | null = null

// 鼠标态
let hoverPx: { x: number; y: number } | null = null
let dragStart: { x: number; y: number } | null = null
let dragRect: { x: number; y: number; w: number; h: number } | null = null
// 游标 emit 合帧 + 跨采样去重
let cursorRaf = 0
let lastEmitKey: string | null | undefined = undefined

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v
}

// ---- 绘图区几何（设备像素）----
interface Geom {
  W: number
  H: number
  left: number
  top: number
  pw: number
  ph: number
  t0: number
  t1: number
  f0: number
  f1: number
}
function dataExtent(arr: number[]): [number, number] {
  if (!arr.length) return [0, 1]
  const lo = arr[0]
  const hi = arr[arr.length - 1]
  return hi > lo ? [lo, hi] : [lo, lo + 1]
}
function effRange(view0: number | null, view1: number | null, ext: [number, number]): [number, number] {
  let lo = view0 != null ? Math.max(ext[0], view0) : ext[0]
  let hi = view1 != null ? Math.min(ext[1], view1) : ext[1]
  if (!(hi > lo)) {
    lo = ext[0]
    hi = ext[1]
  }
  return [lo, hi]
}
function computeGeom(): Geom | null {
  const cv = canvasRef.value
  if (!cv) return null
  const W = cv.width
  const H = cv.height
  if (W <= 0 || H <= 0) return null
  const dpr = PX_RATIO
  const dense = props.denseAxes
  const left = (props.hideYLabels ? (dense ? 18 : 24) : dense ? 38 : 50) * dpr
  const bottom = (props.hideXLabels ? (dense ? 16 : 20) : dense ? 26 : 34) * dpr
  const top = 8 * dpr
  const right = 12 * dpr
  const pw = Math.max(1, W - left - right)
  const ph = Math.max(1, H - top - bottom)
  const [t0, t1] = effRange(props.viewTMin, props.viewTMax, dataExtent(props.times))
  const [f0, f1] = effRange(props.viewFMin, props.viewFMax, dataExtent(props.freqs))
  return { W, H, left, top, pw, ph, t0, t1, f0, f1 }
}
// 值 ↔ 像素
function tToX(g: Geom, t: number): number {
  return g.left + ((t - g.t0) / (g.t1 - g.t0 || 1)) * g.pw
}
function fToY(g: Geom, f: number): number {
  return g.top + (1 - (f - g.f0) / (g.f1 - g.f0 || 1)) * g.ph // 频率向上
}
function xToT(g: Geom, x: number): number {
  return g.t0 + ((x - g.left) / (g.pw || 1)) * (g.t1 - g.t0)
}
function yToF(g: Geom, y: number): number {
  return g.f0 + (1 - (y - g.top) / (g.ph || 1)) * (g.f1 - g.f0)
}
function nearestIdx(arr: number[], v: number): number {
  if (!arr.length) return -1
  let best = 0
  let bestD = Infinity
  for (let i = 0; i < arr.length; i++) {
    const d = Math.abs(arr[i] - v)
    if (d < bestD) {
      bestD = d
      best = i
    }
  }
  return best
}

// ---- 离屏矩阵面：把 power 烤成 nT×nF 的彩色 ImageData（行翻转：图首行=最高频）----
function buildMatrix() {
  const nF = props.power.length
  const nT = nF ? props.power[0].length : 0
  if (!nF || !nT) {
    matrixCv = null
    return
  }
  if (!matrixCv) matrixCv = document.createElement('canvas')
  matrixCv.width = nT
  matrixCv.height = nF
  const mctx = matrixCv.getContext('2d')
  if (!mctx) return
  const img = mctx.createImageData(nT, nF)
  const d = img.data
  const s = props.zmax > 0 ? props.zmax : 1
  const seq = props.cmap === 'viridis'
  for (let iF = 0; iF < nF; iF++) {
    const row = props.power[iF] || []
    const imgRow = nF - 1 - iF // 翻转：低频 iF=0 → 画到底部
    const base = imgRow * nT
    for (let iT = 0; iT < nT; iT++) {
      const v = row[iT]
      let li: number
      if (!Number.isFinite(v)) {
        li = seq ? 0 : (HEATMAP_LUT_N - 1) >> 1 // NaN → viridis 最低 / rdbu 白心
      } else if (seq) {
        let k = v / s
        k = k < 0 ? 0 : k > 1 ? 1 : k
        li = (k * (HEATMAP_LUT_N - 1)) | 0
      } else {
        let t = v / s
        t = t < -1 ? -1 : t > 1 ? 1 : t
        li = (((t + 1) * 0.5) * (HEATMAP_LUT_N - 1)) | 0
      }
      const di = (base + iT) * 4
      const ci = li * 3
      d[di] = lut[ci]
      d[di + 1] = lut[ci + 1]
      d[di + 2] = lut[ci + 2]
      d[di + 3] = 255
    }
  }
  mctx.putImageData(img, 0, 0)
}

// ---- 底图：面 + 轴 + 网格 + 频段线 + 刺激线 ----
function rebuildBase() {
  const cv = canvasRef.value
  const host = hostRef.value
  if (!cv || !host) return
  const wantW = Math.max(1, Math.round((host.clientWidth || 320) * PX_RATIO))
  const wantH = Math.max(1, Math.round((host.clientHeight || 200) * PX_RATIO))
  if (cv.width !== wantW) cv.width = wantW
  if (cv.height !== wantH) cv.height = wantH
  if (!baseCv) baseCv = document.createElement('canvas')
  baseCv.width = cv.width
  baseCv.height = cv.height

  const g = computeGeom()
  const ctx = baseCv.getContext('2d')
  if (!g || !ctx) return
  ctx.clearRect(0, 0, g.W, g.H)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(g.left, g.top, g.pw, g.ph)

  // 面：从矩阵里裁出当前视窗子矩形，拉伸到绘图区（双线性插值）
  buildMatrix()
  if (matrixCv) {
    const [te0, te1] = dataExtent(props.times)
    const [fe0, fe1] = dataExtent(props.freqs)
    const nT = matrixCv.width
    const nF = matrixCv.height
    // 源矩形：列按时间窗、行按频率窗（图首行=最高频，故 sy 用 fe1 端）
    const sx = ((g.t0 - te0) / (te1 - te0 || 1)) * nT
    const sw = ((g.t1 - g.t0) / (te1 - te0 || 1)) * nT
    const sy = ((fe1 - g.f1) / (fe1 - fe0 || 1)) * nF
    const sh = ((g.f1 - g.f0) / (fe1 - fe0 || 1)) * nF
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.save()
    ctx.beginPath()
    ctx.rect(g.left, g.top, g.pw, g.ph)
    ctx.clip()
    ctx.drawImage(matrixCv, sx, sy, Math.max(0.001, sw), Math.max(0.001, sh), g.left, g.top, g.pw, g.ph)
    ctx.restore()
  }

  drawTimeAxis(ctx, g)
  drawFreqAxis(ctx, g)
  if (props.tZero) drawStim(ctx, g)

  // 绘图区外框（细，对标 matplotlib box spine）
  ctx.strokeStyle = TICK
  ctx.lineWidth = PX_RATIO
  ctx.strokeRect(g.left + 0.5, g.top + 0.5, g.pw - 1, g.ph - 1)
}

function niceTicks(lo: number, hi: number, target: number): number[] {
  const span = hi - lo
  if (!(span > 0)) return [lo]
  const raw = span / target
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const norm = raw / mag
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag
  const out: number[] = []
  const start = Math.ceil(lo / step) * step
  for (let v = start; v <= hi + step * 1e-6; v += step) out.push(Math.round(v / step) * step)
  return out
}
function fmtTime(v: number): string {
  return Math.abs(v) >= 10 ? String(Math.round(v)) : String(Math.round(v * 100) / 100)
}
function fmtFreq(v: number): string {
  return Math.abs(v) >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10)
}

function drawTimeAxis(ctx: CanvasRenderingContext2D, g: Geom) {
  const dpr = PX_RATIO
  const fontPx = (props.denseAxes ? 10 : 12) * dpr
  const tick = 4 * dpr
  ctx.font = `${fontPx}px monospace`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  ctx.lineWidth = dpr
  for (const t of niceTicks(g.t0, g.t1, props.denseAxes ? 4 : 6)) {
    const x = tToX(g, t)
    if (x < g.left - 0.5 || x > g.left + g.pw + 0.5) continue
    if (props.showGrid) {
      ctx.strokeStyle = GRID_SOFT
      ctx.beginPath()
      ctx.moveTo(x, g.top)
      ctx.lineTo(x, g.top + g.ph)
      ctx.stroke()
    }
    // 朝外短刻度线（对标 matplotlib 'out'，不贯穿数据）
    ctx.strokeStyle = TICK
    ctx.beginPath()
    ctx.moveTo(x, g.top + g.ph)
    ctx.lineTo(x, g.top + g.ph + tick)
    ctx.stroke()
    if (!props.hideXLabels) {
      ctx.fillStyle = AXIS
      ctx.fillText(fmtTime(t), x, g.top + g.ph + tick + 3 * dpr)
    }
  }
}

// 频率轴：均匀 niceTicks 刻度 + 朝外短刻度线（对标 matplotlib/MNE，默认不画贯穿网格）。
function drawFreqAxis(ctx: CanvasRenderingContext2D, g: Geom) {
  const dpr = PX_RATIO
  const fontPx = (props.denseAxes ? 10 : 12) * dpr
  const tick = 4 * dpr
  ctx.font = `${fontPx}px monospace`
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  ctx.lineWidth = dpr
  for (const f of niceTicks(g.f0, g.f1, props.denseAxes ? 4 : 6)) {
    const y = fToY(g, f)
    if (y < g.top - 0.5 || y > g.top + g.ph + 0.5) continue
    if (props.showGrid) {
      ctx.strokeStyle = GRID_SOFT
      ctx.beginPath()
      ctx.moveTo(g.left, y)
      ctx.lineTo(g.left + g.pw, y)
      ctx.stroke()
    }
    ctx.strokeStyle = TICK
    ctx.beginPath()
    ctx.moveTo(g.left - tick, y)
    ctx.lineTo(g.left, y)
    ctx.stroke()
    if (!props.hideYLabels) {
      ctx.fillStyle = AXIS
      ctx.fillText(fmtFreq(f), g.left - tick - 3 * dpr, y)
    }
  }
}

function drawStim(ctx: CanvasRenderingContext2D, g: Geom) {
  if (0 <= g.t0 || 0 >= g.t1) return
  const dpr = PX_RATIO
  const x = tToX(g, 0)
  ctx.strokeStyle = STIM_LINE
  ctx.lineWidth = 1.5 * dpr
  ctx.setLineDash([4 * dpr, 3 * dpr])
  ctx.beginPath()
  ctx.moveTo(x, g.top)
  ctx.lineTo(x, g.top + g.ph)
  ctx.stroke()
  ctx.setLineDash([])
}

// ---- 合成：blit 底图 + 叠 ROI / 锁定 / 实时十字 ----
function paint() {
  const cv = canvasRef.value
  if (!cv || !baseCv) return
  const ctx = cv.getContext('2d')
  const g = computeGeom()
  if (!ctx || !g) return
  ctx.clearRect(0, 0, cv.width, cv.height)
  ctx.drawImage(baseCv, 0, 0)

  // ROI 选区（已确认）
  if (props.region) drawRoi(ctx, g, props.region)
  // 正在拖拽的框
  if (dragRect) {
    ctx.save()
    ctx.fillStyle = REGION_FILL
    ctx.strokeStyle = REGION_LINE
    ctx.lineWidth = PX_RATIO
    ctx.setLineDash([4 * PX_RATIO, 3 * PX_RATIO])
    ctx.fillRect(dragRect.x, dragRect.y, dragRect.w, dragRect.h)
    ctx.strokeRect(dragRect.x, dragRect.y, dragRect.w, dragRect.h)
    ctx.setLineDash([])
    ctx.restore()
  }
  // 锁定十字（常驻）
  if (props.lockedT != null && props.lockedF != null) {
    drawCross(ctx, g, tToX(g, props.lockedT), fToY(g, props.lockedF), LOCK_LINE, 1.5)
  }
  // 实时十字（非锁定、非拖拽时跟随鼠标）
  if (hoverPx && !props.locked && !dragRect) {
    drawCross(ctx, g, hoverPx.x, hoverPx.y, 'rgba(40,50,72,0.55)', 1)
  }
}
function drawRoi(ctx: CanvasRenderingContext2D, g: Geom, r: Roi) {
  const xa = clamp(tToX(g, Math.min(r.t0, r.t1)), g.left, g.left + g.pw)
  const xb = clamp(tToX(g, Math.max(r.t0, r.t1)), g.left, g.left + g.pw)
  const ya = clamp(fToY(g, Math.max(r.f0, r.f1)), g.top, g.top + g.ph)
  const yb = clamp(fToY(g, Math.min(r.f0, r.f1)), g.top, g.top + g.ph)
  if (xb <= xa || yb <= ya) return
  ctx.save()
  ctx.fillStyle = REGION_FILL
  ctx.fillRect(xa, ya, xb - xa, yb - ya)
  ctx.strokeStyle = REGION_LINE
  ctx.lineWidth = PX_RATIO
  ctx.setLineDash([4 * PX_RATIO, 3 * PX_RATIO])
  ctx.strokeRect(xa, ya, xb - xa, yb - ya)
  ctx.setLineDash([])
  ctx.restore()
}
function drawCross(ctx: CanvasRenderingContext2D, g: Geom, x: number, y: number, color: string, w: number) {
  if (x < g.left || x > g.left + g.pw || y < g.top || y > g.top + g.ph) return
  ctx.save()
  ctx.strokeStyle = color
  ctx.lineWidth = w * PX_RATIO
  ctx.beginPath()
  ctx.moveTo(x, g.top)
  ctx.lineTo(x, g.top + g.ph)
  ctx.moveTo(g.left, y)
  ctx.lineTo(g.left + g.pw, y)
  ctx.stroke()
  ctx.restore()
}

// ---- 鼠标坐标（CSS px → 设备 px）----
function evtToDevice(e: MouseEvent): { x: number; y: number } | null {
  const cv = canvasRef.value
  if (!cv) return null
  const rect = cv.getBoundingClientRect()
  const sx = cv.width / (rect.width || 1)
  const sy = cv.height / (rect.height || 1)
  return { x: (e.clientX - rect.left) * sx, y: (e.clientY - rect.top) * sy }
}
function readoutAt(g: Geom, px: { x: number; y: number }): { t: number; f: number; value: number } | null {
  if (px.x < g.left || px.x > g.left + g.pw || px.y < g.top || px.y > g.top + g.ph) return null
  const t = xToT(g, px.x)
  const f = yToF(g, px.y)
  const iT = nearestIdx(props.times, t)
  const iF = nearestIdx(props.freqs, f)
  if (iT < 0 || iF < 0) return null
  const value = Number(props.power[iF]?.[iT] ?? NaN)
  return { t: props.times[iT], f: props.freqs[iF], value }
}

function onMouseMove(e: MouseEvent) {
  const g = computeGeom()
  const px = evtToDevice(e)
  if (!g || !px) return
  if (dragStart) {
    // 拖框（限制在绘图区内）
    const x0 = clamp(dragStart.x, g.left, g.left + g.pw)
    const y0 = clamp(dragStart.y, g.top, g.top + g.ph)
    const x1 = clamp(px.x, g.left, g.left + g.pw)
    const y1 = clamp(px.y, g.top, g.top + g.ph)
    dragRect = { x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) }
    paint()
    return
  }
  hoverPx = px
  paint()
  if (props.locked) return
  // emit 合帧 + 跨采样去重
  if (!cursorRaf) cursorRaf = requestAnimationFrame(() => flushCursor(g, px))
}
function flushCursor(g: Geom, px: { x: number; y: number }) {
  cursorRaf = 0
  const r = readoutAt(g, px)
  const key = r ? `${r.t}|${r.f}` : null
  if (key === lastEmitKey) return
  lastEmitKey = key
  emit('cursor', r)
}
function onMouseLeave() {
  hoverPx = null
  lastEmitKey = undefined
  paint()
  if (!props.locked) emit('cursor', null)
}
function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  const g = computeGeom()
  const px = evtToDevice(e)
  if (!g || !px) return
  if (px.x < g.left || px.x > g.left + g.pw || px.y < g.top || px.y > g.top + g.ph) return
  dragStart = px
  dragRect = null
}
function onMouseUp(e: MouseEvent) {
  if (!dragStart) return
  const g = computeGeom()
  const px = evtToDevice(e)
  const start = dragStart
  dragStart = null
  if (!g || !px) {
    dragRect = null
    paint()
    return
  }
  const moved = Math.hypot(px.x - start.x, px.y - start.y)
  dragRect = null
  if (moved < 4 * PX_RATIO) {
    paint()
    return
  }
  const t0 = xToT(g, clamp(start.x, g.left, g.left + g.pw))
  const t1 = xToT(g, clamp(px.x, g.left, g.left + g.pw))
  const f0 = yToF(g, clamp(start.y, g.top, g.top + g.ph))
  const f1 = yToF(g, clamp(px.y, g.top, g.top + g.ph))
  emit('select', { t0: Math.min(t0, t1), t1: Math.max(t0, t1), f0: Math.min(f0, f1), f1: Math.max(f0, f1) })
  paint()
}
function onDblClick(e: MouseEvent) {
  if (props.locked) return
  const g = computeGeom()
  const px = evtToDevice(e)
  if (!g || !px) return
  const r = readoutAt(g, px)
  if (r) emit('lock', r)
}
function onContextMenu(e: MouseEvent) {
  e.preventDefault()
  emit('unlock')
}
// 滚轮缩放时间轴（保持游标下的时刻不动），与时域/PSD 一致
function onWheel(e: WheelEvent) {
  const g = computeGeom()
  if (!g) return
  e.preventDefault()
  const ext = dataExtent(props.times)
  const min = g.t0
  const max = g.t1
  if (!(max > min)) return
  const px = evtToDevice(e)
  let cx = px ? xToT(g, clamp(px.x, g.left, g.left + g.pw)) : (min + max) / 2
  cx = clamp(cx, min, max)
  const factor = e.deltaY < 0 ? 0.82 : 1 / 0.82
  let nmin = cx - (cx - min) * factor
  let nmax = cx + (max - cx) * factor
  nmin = Math.max(ext[0], nmin)
  nmax = Math.min(ext[1], nmax)
  const minSpan = (ext[1] - ext[0]) / 500
  if (nmax - nmin < minSpan) {
    const c = (nmin + nmax) / 2
    nmin = c - minSpan / 2
    nmax = c + minSpan / 2
  }
  if (nmin <= ext[0] && nmax >= ext[1]) {
    emit('zoom', null)
    return
  }
  emit('zoom', { min: nmin, max: nmax })
}

function full() {
  rebuildBase()
  paint()
}

onMounted(async () => {
  await nextTick()
  full()
  ro = new ResizeObserver(() => full())
  const cv = canvasRef.value
  if (cv) {
    ro.observe(hostRef.value as Element)
    cv.addEventListener('mousemove', onMouseMove)
    cv.addEventListener('mouseleave', onMouseLeave)
    cv.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mouseup', onMouseUp)
    cv.addEventListener('dblclick', onDblClick)
    cv.addEventListener('contextmenu', onContextMenu)
    cv.addEventListener('wheel', onWheel, { passive: false })
  }
})
onUnmounted(() => {
  if (cursorRaf) cancelAnimationFrame(cursorRaf)
  ro?.disconnect()
  ro = null
  const cv = canvasRef.value
  if (cv) {
    cv.removeEventListener('mousemove', onMouseMove)
    cv.removeEventListener('mouseleave', onMouseLeave)
    cv.removeEventListener('mousedown', onMouseDown)
    window.removeEventListener('mouseup', onMouseUp)
    cv.removeEventListener('dblclick', onDblClick)
    cv.removeEventListener('contextmenu', onContextMenu)
    cv.removeEventListener('wheel', onWheel)
  }
})

// 配色变 → 重烤 LUT + 重建底图
watch(
  () => props.cmap,
  () => {
    lut = buildHeatmapLut(props.cmap)
    full()
  },
)
// 数据 / 色阶 / 视窗 / 轴显示 / 频段 / 刺激 = 重建底图
watch(
  () => [
    props.power,
    props.freqs,
    props.times,
    props.zmax,
    props.viewTMin,
    props.viewTMax,
    props.viewFMin,
    props.viewFMax,
    props.showGrid,
    props.tZero,
    props.denseAxes,
    props.hideXLabels,
    props.hideYLabels,
  ],
  () => full(),
  { deep: false },
)
// 选区 / 锁定标记 = 仅重绘叠加层（不重建底图）
watch(() => [props.region, props.lockedT, props.lockedF, props.locked], () => paint(), { deep: true })
</script>

<style scoped>
.hmc-host {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}
.hmc-cv {
  width: 100%;
  height: 100%;
  display: block;
  cursor: crosshair;
}
.hmc-locked .hmc-cv {
  cursor: default;
}
.hmc-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c-text-3);
  font-size: 13px;
}
</style>
