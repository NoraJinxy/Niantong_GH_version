<template>
  <div class="topo-strip">
    <div class="topo-cap">地形图<span class="topo-cap-sub">{{ subtitle }}</span>
      <span v-if="vmax > 0" style="display: inline-flex; align-items: center; gap: 5px; margin-left: auto; font-family: var(--ff-mono); font-size: 11px; color: var(--c-text-3);">
        <span>{{ loLabel ?? axisLabel(barLo) }}</span>
        <span style="width: 88px; height: 9px; border-radius: 2px; border: 1px solid var(--c-border); background: linear-gradient(to right, rgb(38,92,186), rgb(245,247,250), rgb(206,52,48));"></span>
        <span>{{ hiLabel ?? axisLabel(barHi) }}</span>
        <span style="margin-left: 2px;">{{ unit }}</span>
      </span>
    </div>
    <div class="topo-cards">
      <div v-for="c in cells" :key="c.seg" class="topo-card" :style="{ borderTopColor: c.color }">
        <div class="topo-hd"><span class="topo-dot" :style="{ background: c.color }"></span><span class="topo-hd-name">{{ c.label }}</span></div>
        <!-- 单层 canvas：色面 + 头罩 + 鼻耳 + 电极点同一坐标变换绘制（杜绝分层错位）；hover 真值走动态 title -->
        <canvas v-if="c.points && c.points.length" :ref="(el) => setCanvas(c.seg, el)" class="topo-cv"></canvas>
        <div v-else class="topo-empty">无电极坐标<br />(该结果未带 montage)</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 真实地形图条：电极 2D 坐标 → 薄板样条插值出色面（头罩圆内），中性电极标记叠在面上。
// 性能（Step 2 / 2b）：曲面是数值的线性函数 ⇒ 每个 montage 预算一次插值矩阵 M（见 topoKernel.ts），
// 之后每帧只做 surface = M·v（纯乘加、零 log）+ 查 LUT 配色 + putImageData（无 toDataURL）。
// 建矩阵那笔重活默认派给 Web Worker（topoKernel.worker），首屏/切组主线程不卡；worker 不可用时同步兜底。
// 绘制：色面 + 头罩圈 + 鼻耳 + 电极点全部画在**同一张 canvas、同一套坐标变换**里——
// 旧版「canvas 色面 + SVG 头罩」两层叠放会在真机上对不齐，单层从根上消除该问题。
import { computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { TOPO_RES as RES, buildTopoKernel } from './topoKernel'

interface TopoPoint { name: string; x: number; y: number; value: number }
interface TopoCell { seg: number; label: string; color: string; points: TopoPoint[] | null }
// vmax：对称 ±vmax 着色（相对/去均值的 PSD·TFR 用，白=0 居中）。
// domain：非对称 [lo,hi] 着色（绝对量、与主图 Y 轴同尺度的时域用）——白仍钉在 0，正侧按 hi、负侧按 |lo| 各自归一，
//         色阶条与标签随之非对称。两者二选一：给了 domain 就用它，否则回退 ±vmax。
const props = withDefaults(defineProps<{ cells: TopoCell[]; vmax: number; domain?: [number, number] | null; subtitle?: string; unit?: string; loLabel?: string; hiLabel?: string }>(), { subtitle: '区间均值 µV · 全部通道', unit: 'µV', domain: null })

// 色标数字格式:大值取整、小值留 1 位
function fmtScale(v: number): string {
  return v >= 10 ? String(Math.round(v)) : String(Math.round(v * 10) / 10)
}
// 带符号轴标签（0 不带号；±vmax 对称时退化为旧的「−x / +x」）
function axisLabel(v: number): string {
  if (Math.abs(v) < 1e-9) return '0'
  return (v > 0 ? '+' : '−') + fmtScale(Math.abs(v))
}
// 色阶条两端值：给了 domain 用 [lo,hi]，否则对称 ±vmax
const barLo = computed(() => (props.domain ? props.domain[0] : -props.vmax))
const barHi = computed(() => (props.domain ? props.domain[1] : props.vmax))
// 色阶条渐变固定 蓝→白→红、白居中：值按 [lo,hi] 线性铺满整条色板（蓝=lo·白=窗中点·红=hi），
// 非对称窗（如 0–12）也走满蓝→红，不再因「白钉死 0µV」退化成半截白→红（对标 EEGLAB 色限）。

// ── 配色 LUT：发散色（负→蓝、零→近白、正→红），按归一化 t∈[-1,1] 预烤；vmax 只用于把数值映成 t，不进 LUT ──
const LUT_N = 512
const LUT = new Uint8Array(LUT_N * 3)
;(function buildLUT() {
  const white = [245, 247, 250]
  for (let i = 0; i < LUT_N; i++) {
    const t = (i / (LUT_N - 1)) * 2 - 1 // -1..1
    const target = t < 0 ? [38, 92, 186] : [206, 52, 48] // 红蓝发散（RdBu 风）
    const k = Math.pow(Math.abs(t), 0.8) // 轻微 gamma(<1)：中等幅值也更显色
    LUT[i * 3] = Math.round(white[0] + (target[0] - white[0]) * k)
    LUT[i * 3 + 1] = Math.round(white[1] + (target[1] - white[1]) * k)
    LUT[i * 3 + 2] = Math.round(white[2] + (target[2] - white[2]) * k)
  }
})()

// ── kernel 调度：每个 montage 的插值矩阵，按签名缓存；重活派给 worker，主线程不阻塞 ──
interface ReadyKernel { names: string[]; inside: Int32Array; M: Float32Array; N: number }
type WorkerOut = { sig: string; failed: true } | { sig: string; names: string[]; N: number; inside: ArrayBuffer; M: ArrayBuffer }
const kernelCache = new Map<string, ReadyKernel | null>() // null = 退化 montage（电极共线等）
const pendingSigs = new Set<string>()
let worker: Worker | null = null
let workerBroken = false

function sigOf(points: TopoPoint[]): string {
  let s = ''
  for (const p of points) s += p.name + ':' + p.x.toFixed(4) + ',' + p.y.toFixed(4) + '|'
  return s
}

function ensureWorker(): Worker | null {
  if (worker || workerBroken) return worker
  try {
    const w = new Worker(new URL('./topoKernel.worker.ts', import.meta.url), { type: 'module' })
    w.onmessage = (e: MessageEvent<WorkerOut>) => {
      const d = e.data
      pendingSigs.delete(d.sig)
      if ('failed' in d) { kernelCache.set(d.sig, null); return }
      kernelCache.set(d.sig, { names: d.names, inside: new Int32Array(d.inside), M: new Float32Array(d.M), N: d.N })
      renderAll() // 矩阵到位 → 立刻补画色面
    }
    w.onerror = () => { workerBroken = true } // 运行期出错：后续走主线程兜底
    worker = w
  } catch {
    workerBroken = true
    worker = null
  }
  return worker
}

// worker 不可用时同步兜底（会有一次卡顿，但保证出图）
function buildSync(sig: string, points: TopoPoint[]): ReadyKernel | null {
  const k = buildTopoKernel(points.map((p) => ({ x: p.x, y: p.y })))
  const ready = k ? { names: points.map((p) => p.name), inside: k.inside, M: k.M, N: k.N } : null
  kernelCache.set(sig, ready)
  return ready
}

// ready → 直接用；没算过 → 派给 worker（返回 undefined：本帧只画标记，矩阵到了再补色面）
function getKernel(sig: string, points: TopoPoint[]): ReadyKernel | null | undefined {
  if (kernelCache.has(sig)) return kernelCache.get(sig)
  const w = ensureWorker()
  if (!w) return buildSync(sig, points)
  if (!pendingSigs.has(sig)) {
    pendingSigs.add(sig)
    w.postMessage({ sig, names: points.map((p) => p.name), points: points.map((p) => ({ x: p.x, y: p.y })) })
  }
  return undefined
}

// 取本格各通道数值，对齐到 kernel 的电极顺序
function valueVector(points: TopoPoint[], names: string[]): Float32Array {
  const map = new Map<string, number>()
  for (const p of points) map.set(p.name, p.value)
  const v = new Float32Array(names.length)
  for (let i = 0; i < names.length; i++) v[i] = map.get(names[i]) ?? 0
  return v
}

// 复用一块离屏 RES×RES 画布 + ImageData：圈外像素 alpha 恒 0（从不写入），圈内每帧覆盖
let off: { canvas: HTMLCanvasElement; ctx: CanvasRenderingContext2D; img: ImageData } | null = null
function ensureOffscreen() {
  if (off) return off
  const canvas = document.createElement('canvas')
  canvas.width = RES
  canvas.height = RES
  const ctx = canvas.getContext('2d')!
  off = { canvas, ctx, img: ctx.createImageData(RES, RES) }
  return off
}

// 本格可见 canvas + 电极命中表（CSS 像素，供 hover 读数）
const canvasMap = new Map<number, HTMLCanvasElement>()
const hitMap = new Map<number, { name: string; value: number; x: number; y: number }[]>()
function setCanvas(seg: number, el: unknown) {
  if (el instanceof HTMLCanvasElement) {
    canvasMap.set(seg, el)
    el.onmousemove = (ev) => onHover(seg, el, ev) // 动态 title：悬停最近电极 → 原生 tooltip 显名+值
    el.onmouseleave = () => { el.title = '' }
  } else {
    canvasMap.delete(seg)
    hitMap.delete(seg)
  }
}
function onHover(seg: number, el: HTMLCanvasElement, ev: MouseEvent) {
  const hits = hitMap.get(seg)
  if (!hits) return
  const rect = el.getBoundingClientRect()
  const mx = ev.clientX - rect.left
  const my = ev.clientY - rect.top
  let best: { name: string; value: number } | null = null
  let bestD = 12 // 命中半径（CSS px）
  for (const h of hits) {
    const d = Math.hypot(h.x - mx, h.y - my)
    if (d < bestD) { bestD = d; best = h }
  }
  el.title = best ? `${best.name}: ${best.value.toFixed(2)} µV` : ''
}

// 一格全绘：色面（M·v→LUT→putImageData）+ 头罩圈 + 鼻耳 + 电极点，同一坐标变换 mapX/mapY，物理对齐
function drawCell(canvas: HTMLCanvasElement, kernel: ReadyKernel, points: TopoPoint[], lo: number, hi: number, seg: number) {
  // 1) 色面算进离屏 RES×RES。值按 [lo,hi] 线性铺满 蓝(lo)→白(中点)→红(hi)：非对称窗也走满蓝红、不退化半截。
  const o = ensureOffscreen()
  const data = o.img.data
  const { inside, M, N } = kernel
  const v = valueVector(points, kernel.names)
  const span = hi - lo
  const inv = span > 0 ? 2 / span : 0 // t = (s-lo)*inv - 1 ∈ [-1,1]，白落在窗中点
  for (let p = 0; p < inside.length; p++) {
    let s = 0
    const base = p * N
    for (let j = 0; j < N; j++) s += M[base + j] * v[j]
    let t = Number.isFinite(s) && span > 0 ? (s - lo) * inv - 1 : 0 // span≤0(全平/无量程)→白
    if (t < -1) t = -1
    else if (t > 1) t = 1
    const li = (((t + 1) * 0.5 * (LUT_N - 1)) | 0) * 3
    const di = inside[p] * 4
    data[di] = LUT[li]
    data[di + 1] = LUT[li + 1]
    data[di + 2] = LUT[li + 2]
    data[di + 3] = 255
  }
  o.ctx.putImageData(o.img, 0, 0)

  // 2) 后备分辨率：必须让 backing 宽高比 == 显示框宽高比，否则浏览器非等比拉伸 → 正圆被拉成椭圆。
  //    注意 canvas.width 默认 300、height 默认 150（绝不为 0）；旧的「===0 才设」等于从不设，正是椭圆元凶。
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const wantW = Math.max(1, Math.round((canvas.clientWidth || 132) * dpr))
  const wantH = Math.max(1, Math.round((canvas.clientHeight || 96) * dpr))
  if (canvas.width !== wantW) canvas.width = wantW
  if (canvas.height !== wantH) canvas.height = wantH
  const W = canvas.width
  const H = canvas.height
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, W, H)
  ctx.imageSmoothingEnabled = true

  // 3) 统一坐标变换（viewBox -1.28 -1.34 2.56 2.62，等比居中）：所有几何都过 mapX/mapY ⇒ 天然对齐
  const vbMinX = -1.28, vbMinY = -1.34, vbW = 2.56, vbH = 2.62
  const scale = Math.min(W / vbW, H / vbH)
  const ox = (W - vbW * scale) / 2
  const oy = (H - vbH * scale) / 2
  const mapX = (vx: number) => ox + (vx - vbMinX) * scale
  const mapY = (vy: number) => oy + (vy - vbMinY) * scale
  const cx = mapX(0)
  const cy = mapY(0)

  // 4) 色面贴 [-1,1]²，裁到头罩圆
  ctx.save()
  ctx.beginPath()
  ctx.arc(cx, cy, scale, 0, Math.PI * 2)
  ctx.clip()
  ctx.drawImage(o.canvas, mapX(-1), mapY(-1), 2 * scale, 2 * scale)
  ctx.restore()

  // 5) 头罩圈 + 鼻子 + 双耳（与色面同变换、同圆心同半径）
  ctx.strokeStyle = '#C4CCD8'
  ctx.lineWidth = 0.02 * scale
  ctx.beginPath(); ctx.arc(cx, cy, scale, 0, Math.PI * 2); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(mapX(-0.13), mapY(-0.99)); ctx.quadraticCurveTo(mapX(0), mapY(-1.24), mapX(0.13), mapY(-0.99)); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(mapX(-1), mapY(-0.2)); ctx.quadraticCurveTo(mapX(-1.13), mapY(0), mapX(-1), mapY(0.2)); ctx.stroke()
  ctx.beginPath(); ctx.moveTo(mapX(1), mapY(-0.2)); ctx.quadraticCurveTo(mapX(1.13), mapY(0), mapX(1), mapY(0.2)); ctx.stroke()

  // 6) 电极点（白底深描边，不按值填色）+ 记命中表（CSS px）
  const rx = (canvas.clientWidth || W) / W
  const ry = (canvas.clientHeight || H) / H
  const hits: { name: string; value: number; x: number; y: number }[] = []
  ctx.lineWidth = 0.012 * scale
  for (const p of points) {
    const ex = mapX(p.x)
    const ey = mapY(-p.y) // 与旧 SVG cy=-p.y 一致；该处色面正是该电极的值
    ctx.beginPath()
    ctx.arc(ex, ey, 0.026 * scale, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
    ctx.fill()
    ctx.strokeStyle = 'rgba(38, 50, 72, 0.6)'
    ctx.stroke()
    hits.push({ name: p.name, value: p.value, x: ex * rx, y: ey * ry })
  }
  hitMap.set(seg, hits)
}

function renderAll() {
  // 色阶域：给了非对称 domain 用 [lo,hi]，否则对称 [−vmax, vmax]；值线性铺满 蓝→白→红
  const lo = barLo.value
  const hi = barHi.value
  for (const c of props.cells) {
    if (!c.points || c.points.length < 3) continue
    const canvas = canvasMap.get(c.seg)
    if (!canvas) continue
    const kernel = getKernel(sigOf(c.points), c.points)
    if (!kernel) continue // undefined=worker 计算中 / null=退化 montage → 本格留空（无 montage 提示走 v-else）
    drawCell(canvas, kernel, c.points, lo, hi, c.seg)
  }
}

watch(() => [props.cells, props.vmax, props.domain], async () => { await nextTick(); renderAll() }, { deep: false })
onMounted(async () => { await nextTick(); renderAll() })
onUnmounted(() => { worker?.terminate(); worker = null })
</script>

<style scoped>
.topo-strip { flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
/* 固定宽度：游标 ms 位数变化（5 / 315 / 1000）不再改变本列宽度，右侧地形图卡不再左右抖动 */
.topo-cap { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; font-size: 11px; color: var(--c-text-2); }
.topo-cap-sub { font-size: 11px; color: var(--c-text-3); font-variant-numeric: tabular-nums; }
.topo-cards { display: flex; gap: 8px; overflow-x: auto; flex: 1; }
.topo-card { width: 140px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; border: 1px solid var(--c-border); border-top-width: 2px; border-radius: var(--r-sm); background: var(--c-surface); padding: 4px 4px 2px; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.topo-hd { font-size: 9px; font-weight: 600; color: var(--c-text-2); display: flex; align-items: center; gap: 4px; max-width: 100%; }
.topo-hd-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topo-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.topo-cv { width: 100%; height: 96px; display: block; }
.topo-empty { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 9px; color: var(--c-text-3); line-height: 1.4; padding: 12px 4px; }
</style>
