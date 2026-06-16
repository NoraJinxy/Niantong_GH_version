<template>
  <div class="topo-strip">
    <div class="topo-cap">地形图<span class="topo-cap-sub">{{ subtitle }}</span></div>
    <div class="topo-cards">
      <div v-for="c in cells" :key="c.seg" class="topo-card" :style="{ borderTopColor: c.color }">
        <div class="topo-hd"><span class="topo-dot" :style="{ background: c.color }"></span><span class="topo-hd-name">{{ c.label }}</span></div>
        <!-- 色面（薄板样条插值）走 canvas（putImageData，无 PNG 编码）；头罩 + 电极标记叠一层透明 SVG（保留 hover 真值） -->
        <div v-if="c.points && c.points.length" class="topo-plot">
          <canvas :ref="(el) => setCanvas(c.seg, el)" class="topo-cv"></canvas>
          <svg viewBox="-1.28 -1.34 2.56 2.62" class="topo-ov">
            <circle cx="0" cy="0" r="1" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
            <path d="M -0.13 -0.99 Q 0 -1.24 0.13 -0.99" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
            <path d="M -1 -0.2 Q -1.13 0 -1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
            <path d="M 1 -0.2 Q 1.13 0 1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
            <!-- 中性电极标记：白底 + 深描边，红/蓝/近白底色上都看得见；真值走 hover title（对标 EEGLAB/MNE 不按值填点） -->
            <circle
              v-for="p in c.points"
              :key="p.name"
              :cx="p.x"
              :cy="-p.y"
              r="0.026"
              fill="rgba(255, 255, 255, 0.9)"
              stroke="rgba(38, 50, 72, 0.6)"
              stroke-width="0.012"
            >
              <title>{{ p.name }}: {{ p.value.toFixed(2) }} µV</title>
            </circle>
          </svg>
        </div>
        <div v-else class="topo-empty">无电极坐标<br />(该结果未带 montage)</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 真实地形图条：电极 2D 坐标 → 薄板样条插值出色面（头罩圆内），中性电极标记叠在面上。
// 性能（Step 2 / 2b）：曲面是数值的线性函数 ⇒ 每个 montage 预算一次插值矩阵 M（见 topoKernel.ts），
// 之后每帧只做 surface = M·v（纯乘加、零 log）+ 查 LUT 配色 + putImageData（无 toDataURL）。
// 建矩阵那笔重活默认派给 Web Worker（topoKernel.worker），首次进页/切通道组主线程不卡；worker 不可用时同步兜底。
import { onMounted, onUnmounted, watch, nextTick } from 'vue'
import { TOPO_RES as RES, buildTopoKernel } from './topoKernel'

interface TopoPoint { name: string; x: number; y: number; value: number }
interface TopoCell { seg: number; label: string; color: string; points: TopoPoint[] | null }
const props = withDefaults(defineProps<{ cells: TopoCell[]; vmax: number; subtitle?: string }>(), { subtitle: '区间均值 µV · 全部通道' })

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

// 本格可见 canvas（按 seg 收集）
const canvasMap = new Map<number, HTMLCanvasElement>()
function setCanvas(seg: number, el: unknown) {
  if (el instanceof HTMLCanvasElement) canvasMap.set(seg, el)
  else canvasMap.delete(seg)
}

// 每帧：surface = M·v → 查 LUT 写 ImageData → putImageData 到离屏 → drawImage 贴到本格 canvas 的 [-1,1]² 区域
function drawSurface(canvas: HTMLCanvasElement, kernel: ReadyKernel, v: Float32Array, vmax: number) {
  const o = ensureOffscreen()
  const data = o.img.data
  const { inside, M, N } = kernel
  const P = inside.length
  const invVmax = vmax > 0 ? 1 / vmax : 1
  for (let p = 0; p < P; p++) {
    let s = 0
    const base = p * N
    for (let j = 0; j < N; j++) s += M[base + j] * v[j]
    let t = s * invVmax
    if (t < -1) t = -1
    else if (t > 1) t = 1
    else if (!Number.isFinite(t)) t = 0
    const li = (((t + 1) * 0.5 * (LUT_N - 1)) | 0) * 3
    const di = inside[p] * 4
    data[di] = LUT[li]
    data[di + 1] = LUT[li + 1]
    data[di + 2] = LUT[li + 2]
    data[di + 3] = 255
  }
  o.ctx.putImageData(o.img, 0, 0)
  // 本格 canvas 后备分辨率：按显示尺寸 × dpr，只在首次（width=0）设一次（卡片尺寸固定）
  if (canvas.width === 0 || canvas.height === 0) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.max(1, Math.round((canvas.clientWidth || 132) * dpr))
    canvas.height = Math.max(1, Math.round((canvas.clientHeight || 96) * dpr))
  }
  const W = canvas.width
  const H = canvas.height
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, W, H)
  ctx.imageSmoothingEnabled = true
  // 关键：必须和上层 SVG overlay 用**同一个** viewBox→viewport 映射，否则两层错位、色面捅出头罩。
  // SVG 默认 preserveAspectRatio="xMidYMid meet"（等比缩放 + 居中），这里如法炮制：
  // 等比 scale ⇒ 色面 [-1,1]² 落成正方形 ⇒ 内切圆仍是正圆，与头罩 <circle r=1> 完全重合。
  const vbMinX = -1.28, vbMinY = -1.34, vbW = 2.56, vbH = 2.62
  const scale = Math.min(W / vbW, H / vbH)
  const ox = (W - vbW * scale) / 2
  const oy = (H - vbH * scale) / 2
  const cx = ox + (0 - vbMinX) * scale
  const cy = oy + (0 - vbMinY) * scale
  ctx.save()
  ctx.beginPath()
  ctx.arc(cx, cy, scale, 0, Math.PI * 2) // 头罩圆（r=1 → 半径=scale）裁剪兜底，杜绝任何越界像素
  ctx.clip()
  ctx.drawImage(o.canvas, ox + (-1 - vbMinX) * scale, oy + (-1 - vbMinY) * scale, 2 * scale, 2 * scale)
  ctx.restore()
}

function renderAll() {
  const vmax = props.vmax
  for (const c of props.cells) {
    if (!c.points || c.points.length < 3) continue
    const canvas = canvasMap.get(c.seg)
    if (!canvas) continue
    const kernel = getKernel(sigOf(c.points), c.points)
    if (!kernel) continue // undefined=worker 计算中 / null=退化 montage → 只留头罩+标记
    drawSurface(canvas, kernel, valueVector(c.points, kernel.names), vmax)
  }
}

watch(() => [props.cells, props.vmax], async () => { await nextTick(); renderAll() }, { deep: false })
onMounted(async () => { await nextTick(); renderAll() })
onUnmounted(() => { worker?.terminate(); worker = null })
</script>

<style scoped>
.topo-strip { flex-shrink: 0; display: flex; align-items: stretch; gap: 8px; margin-top: 8px; }
/* 固定宽度：游标 ms 位数变化（5 / 315 / 1000）不再改变本列宽度，右侧地形图卡不再左右抖动 */
.topo-cap { display: flex; flex-direction: column; justify-content: center; width: 92px; flex-shrink: 0; font-size: 10px; color: var(--c-text-3); padding-right: 4px; border-right: 1px solid var(--c-border); }
.topo-cap-sub { font-size: 8px; margin-top: 2px; font-variant-numeric: tabular-nums; }
.topo-cards { display: flex; gap: 8px; overflow-x: auto; flex: 1; }
.topo-card { width: 140px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; border: 1px solid var(--c-border); border-top-width: 2px; border-radius: var(--r-sm); background: var(--c-surface); padding: 4px 4px 2px; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.topo-hd { font-size: 9px; font-weight: 600; color: var(--c-text-2); display: flex; align-items: center; gap: 4px; max-width: 100%; }
.topo-hd-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topo-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
/* 色面 canvas 在下、头罩/电极 SVG 在上，同尺寸叠放 */
.topo-plot { position: relative; width: 100%; height: 96px; }
.topo-cv { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.topo-ov { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.topo-empty { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 9px; color: var(--c-text-3); line-height: 1.4; padding: 12px 4px; }
</style>
