<template>
  <div class="topo-strip">
    <div class="topo-cap">地形图<span class="topo-cap-sub">{{ subtitle }}</span>
      <div class="topo-cap-right">
        <span v-if="vmax > 0" style="display: inline-flex; align-items: center; gap: 5px; font-family: var(--ff-mono); font-size: 11px; color: var(--c-text-3);">
          <span>{{ loLabel ?? axisLabel(barLo) }}</span>
          <span :style="{ width: '88px', height: '9px', borderRadius: '2px', border: '1px solid var(--c-border)', background: barGradient }"></span>
          <span>{{ hiLabel ?? axisLabel(barHi) }}</span>
          <span style="margin-left: 2px;">{{ unit }}</span>
        </span>
        <button v-if="cells.length" type="button" class="topo-expand" title="放大查看全部地形图（双击地形图亦可）" @click="openExpanded">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></svg>
          <span>放大</span>
        </button>
      </div>
    </div>
    <div class="topo-cards" :class="{ 'is-grid': layout === 'grid' }" @dblclick="openExpanded">
      <div
        v-for="c in cells"
        :key="c.seg"
        class="topo-card"
        :class="{ 'is-sel': selectable, 'is-active': selectable && c.seg === activeSeg, 'is-marked': c.marked }"
        :style="{ borderTopColor: c.color }"
        @click="onCardClick(c.seg)"
        @dblclick="onCardDblClick(c.seg, $event)"
      >
        <div class="topo-hd"><span class="topo-dot" :style="{ background: c.color }"></span><span class="topo-hd-name">{{ c.label }}</span></div>
        <!-- 单层 canvas：色面 + 头罩 + 鼻耳 + 电极点同一坐标变换绘制（杜绝分层错位）；hover 真值走动态 title -->
        <canvas v-if="c.points && c.points.length" :ref="(el) => setCanvas(c.seg, el)" class="topo-cv"></canvas>
        <div v-else class="topo-empty">无电极坐标<br />(该结果未带 montage)</div>
        <div v-if="c.sub" class="topo-sub">{{ c.sub }}</div>
      </div>
    </div>

    <!-- 放大查看：把本条地形图整组铺成网格大图，标签=条件名，色阶/绘制全复用条带那套 -->
    <Modal v-if="expanded" @close="expanded = false">
      <div class="topo-modal" role="dialog" aria-label="地形图放大查看">
        <div class="topo-modal-hd">
          <div class="topo-modal-ttl">地形图</div>
          <div class="topo-modal-actions">
            <span v-if="vmax > 0" class="topo-modal-bar">
              <span>{{ loLabel ?? axisLabel(barLo) }}</span>
              <span class="topo-modal-grad" :style="{ background: barGradient }"></span>
              <span>{{ hiLabel ?? axisLabel(barHi) }}</span>
              <span class="topo-modal-unit">{{ unit }}</span>
            </span>
            <button type="button" class="topo-modal-dl" title="下载为 PNG 图片（每张带条件标签 + 底部色阶）" @click="exportPng">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M7 11l5 5 5-5M5 20h14" /></svg>
              <span>下载 PNG</span>
            </button>
            <button type="button" class="topo-modal-x" title="关闭（Esc）" aria-label="关闭" @click="expanded = false">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
            </button>
          </div>
        </div>
        <div class="topo-modal-grid" :style="modalGridStyle">
          <div v-for="c in cells" :key="c.seg" class="topo-modal-card" :style="{ borderTopColor: c.color }">
            <div class="topo-modal-cardhd"><span class="topo-dot" :style="{ background: c.color }"></span><span class="topo-modal-cardname">{{ c.label }}</span></div>
            <canvas v-if="c.points && c.points.length" :ref="(el) => setModalCanvas(c.seg, el)" class="topo-modal-cv"></canvas>
            <div v-else class="topo-modal-empty">无电极坐标<br />(该结果未带 montage)</div>
          </div>
        </div>
      </div>
    </Modal>
  </div>
</template>

<script setup lang="ts">
// 真实地形图条：电极 2D 坐标 → 薄板样条插值出色面（头罩圆内），中性电极标记叠在面上。
// 性能（Step 2 / 2b）：曲面是数值的线性函数 ⇒ 每个 montage 预算一次插值矩阵 M（见 topoKernel.ts），
// 之后每帧只做 surface = M·v（纯乘加、零 log）+ 查 LUT 配色 + putImageData（无 toDataURL）。
// 建矩阵那笔重活默认派给 Web Worker（topoKernel.worker），首屏/切组主线程不卡；worker 不可用时同步兜底。
// 绘制：色面 + 头罩圈 + 鼻耳 + 电极点全部画在**同一张 canvas、同一套坐标变换**里——
// 旧版「canvas 色面 + SVG 头罩」两层叠放会在真机上对不齐，单层从根上消除该问题。
import { computed, onMounted, onUnmounted, watch, nextTick, ref } from 'vue'
import Modal from '@/components/common/Modal.vue'
import { TOPO_RES as RES, buildTopoKernel } from './topoKernel'
import { buildHeatmapLut, HEATMAP_LUT_N, heatmapCssGradient, type HeatmapCmap } from './heatmapColor'

interface TopoPoint { name: string; x: number; y: number; value: number }
// sub：标签下一行小字（ICA 成分墙用：解释方差% / 自动标签）。marked：标记态（ICA 剔除）→ 红框。
interface TopoCell { seg: number; label: string; color: string; points: TopoPoint[] | null; sub?: string; marked?: boolean }
// vmax：对称 ±vmax 着色（相对/去均值的 PSD·TFR 用，白=0 居中）。
// domain：非对称 [lo,hi] 着色（绝对量、与主图 Y 轴同尺度的时域用）——值线性铺满 [lo,hi]、白落窗中点（EEGLAB 色限）。
// cmap：地形图色板，默认 elys（全站地形图统一用招牌色）；TFR 传入当前热图 cmap 以跟随热图选择。
const props = withDefaults(defineProps<{ cells: TopoCell[]; vmax: number; domain?: [number, number] | null; cmap?: HeatmapCmap | null; subtitle?: string; unit?: string; loLabel?: string; hiLabel?: string; layout?: 'strip' | 'grid'; selectable?: boolean; activeSeg?: number | null }>(), { subtitle: '区间均值 µV · 全部通道', unit: 'µV', domain: null, cmap: 'elys', layout: 'strip', selectable: false, activeSeg: null })
const emit = defineEmits<{ (e: 'cell-click', seg: number): void; (e: 'cell-dblclick', seg: number): void }>()
// 成分墙（ICA）：网格模式下点选某格上报 seg；strip 模式 / 非 selectable 不触发，三观察页零影响。
function onCardClick(seg: number) { if (props.selectable) emit('cell-click', seg) }
// 双击：selectable 下上报 seg（ICA 用作"标记/取消剔除"）并 stop——阻止冒泡到 .topo-cards 开放大弹窗；
// 非 selectable（三观察页）不拦截，双击照常冒泡开放大弹窗，零影响。
function onCardDblClick(seg: number, ev: Event) {
  if (props.selectable) { ev.stopPropagation(); emit('cell-dblclick', seg) }
}

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
// 色阶条渐变：用当前色板（默认 elys），值按 [lo,hi] 线性铺满整条色板、白/中点落窗中央。
const barGradient = computed(() => heatmapCssGradient(props.cmap ?? 'elys', 'to right'))

// 当前生效 LUT：用 props.cmap（默认 elys）的热图色板 LUT；缓存，cmap 不变不重烤。
// 注：热图 LUT 按 i→t∈[-1,1](发散)/k∈[0,1](顺序) 预烤，下标都走 (t+1)/2·(N-1)，发散映白心、顺序映低→高，两者皆对。
let cmapLut: Uint8Array | null = null
let cmapLutKey: HeatmapCmap | null = null
function activeLut(): { lut: Uint8Array; n: number } {
  const cm = props.cmap ?? 'elys'
  if (cmapLutKey !== cm) {
    cmapLut = buildHeatmapLut(cm)
    cmapLutKey = cm
  }
  return { lut: cmapLut as Uint8Array, n: HEATMAP_LUT_N }
}

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
// 条带（小图）与放大弹窗（大图）各持一套 canvas/命中表，共用同一套绘制逻辑（drawCell），按目标 store 落点。
type Hit = { name: string; value: number; x: number; y: number }
const canvasMap = new Map<number, HTMLCanvasElement>()
const hitMap = new Map<number, Hit[]>()
const modalCanvasMap = new Map<number, HTMLCanvasElement>()
const modalHitMap = new Map<number, Hit[]>()

// 放大查看：把本条整组地形图铺成网格大图（标签=条件名）
const expanded = ref(false)
function openExpanded() { if (props.cells.length) expanded.value = true }
// 弹窗网格列数按卡片数自适应（少则少列 → 弹窗 fit-content 自然收窄，不留大白边）；与导出图同一套平衡公式
const gridCols = computed(() => {
  const n = props.cells.length
  return n <= 3 ? Math.max(1, n) : Math.min(4, Math.ceil(Math.sqrt(n)))
})
const modalGridStyle = computed(() => ({ gridTemplateColumns: `repeat(${gridCols.value}, minmax(190px, 240px))` }))

function bindCanvas(seg: number, el: unknown, cmap: Map<number, HTMLCanvasElement>, hmap: Map<number, Hit[]>) {
  if (el instanceof HTMLCanvasElement) {
    cmap.set(seg, el)
    el.onmousemove = (ev) => onHover(seg, el, ev, hmap) // 动态 title：悬停最近电极 → 原生 tooltip 显名+值
    el.onmouseleave = () => { el.title = '' }
  } else {
    cmap.delete(seg)
    hmap.delete(seg)
  }
}
function setCanvas(seg: number, el: unknown) { bindCanvas(seg, el, canvasMap, hitMap) }
function setModalCanvas(seg: number, el: unknown) { bindCanvas(seg, el, modalCanvasMap, modalHitMap) }

function onHover(seg: number, el: HTMLCanvasElement, ev: MouseEvent, hmap: Map<number, Hit[]>) {
  const hits = hmap.get(seg)
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
  el.title = best ? `${best.name}: ${best.value.toFixed(2)} ${props.unit}` : ''
}

// 一格全绘：色面（M·v→LUT→putImageData）+ 头罩圈 + 鼻耳 + 电极点，同一坐标变换 mapX/mapY，物理对齐
function drawCell(canvas: HTMLCanvasElement, kernel: ReadyKernel, points: TopoPoint[], lo: number, hi: number, lut: Uint8Array, lutN: number, seg: number, store: Map<number, Hit[]>) {
  // 1) 色面算进离屏 RES×RES。值按 [lo,hi] 线性铺满整条色板（中点=lut 中段；发散色=白心，顺序色=中间调）。
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
    const li = (((t + 1) * 0.5 * (lutN - 1)) | 0) * 3
    const di = inside[p] * 4
    data[di] = lut[li]
    data[di + 1] = lut[li + 1]
    data[di + 2] = lut[li + 2]
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
  store.set(seg, hits)
}

// 把整组地形图绘到指定的一套 canvas（条带或弹窗），命中表落到对应 store。大图小图同逻辑、只是尺寸不同。
function renderInto(cmap: Map<number, HTMLCanvasElement>, hmap: Map<number, Hit[]>) {
  // 色阶域：给了非对称 domain 用 [lo,hi]，否则对称 [−vmax, vmax]；值线性铺满整条色板
  const lo = barLo.value
  const hi = barHi.value
  const { lut, n } = activeLut() // 当前色板 LUT（默认 elys；TFR 跟随其热图 cmap）
  for (const c of props.cells) {
    if (!c.points || c.points.length < 3) continue
    const canvas = cmap.get(c.seg)
    if (!canvas) continue
    const kernel = getKernel(sigOf(c.points), c.points)
    if (!kernel) continue // undefined=worker 计算中 / null=退化 montage → 本格留空（无 montage 提示走 v-else）
    drawCell(canvas, kernel, c.points, lo, hi, lut, n, c.seg, hmap)
  }
}
// 条带常绘；弹窗开着时一并刷新（cells/游标变化、worker 矩阵到位都会走这里）
function renderAll() {
  renderInto(canvasMap, hitMap)
  if (expanded.value) renderInto(modalCanvasMap, modalHitMap)
}

watch(() => [props.cells, props.vmax, props.domain, props.cmap], async () => { await nextTick(); renderAll() }, { deep: false })
// 弹窗开 → 等大图 canvas 挂载后绘制；关 → 清掉弹窗那套引用
watch(expanded, async (v) => {
  if (v) { await nextTick(); renderInto(modalCanvasMap, modalHitMap) }
  else { modalCanvasMap.clear(); modalHitMap.clear() }
})
// ── 导出 PNG：整组大图拼成多面板图——每格只留「条件名标签 + 地形图」，底部居中一条色阶图例；
//    不印标题 / 副标题等 UI 文字（那些是给屏幕看的、对静态图是噪声，窄图里还会叠字）──
const EXPORT_FONT = '-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
const EXPORT_MONO = '"JetBrains Mono", Consolas, Menlo, monospace'
function sanitizeName(s: string): string {
  return s.replace(/[\\/:*?"<>|]+/g, '').replace(/[·\s]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 48)
}
// 在导出画布上画一条居中色阶图例（lo [渐变] hi 单位），颜色逐列采当前 LUT，与地形图配色完全一致
function drawExportBar(ctx: CanvasRenderingContext2D, centerX: number, midY: number, barW: number, barH: number, d: number) {
  const { lut, n } = activeLut()
  const loT = props.loLabel ?? axisLabel(barLo.value)
  const hiT = props.hiLabel ?? axisLabel(barHi.value)
  const gap = 6 * d
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'left'
  ctx.font = `400 ${11 * d}px ${EXPORT_MONO}`
  const loW = ctx.measureText(loT).width
  const hiW = ctx.measureText(hiT).width
  const uW = ctx.measureText(props.unit).width
  // 整组 [lo 渐变 hi 单位] 居中：先量总宽，再从左往右铺
  let x = centerX - (loW + gap + barW + gap + hiW + gap + uW) / 2
  ctx.fillStyle = '#79859A'; ctx.fillText(loT, x, midY); x += loW + gap
  for (let px = 0; px < barW; px++) {
    const t = (px / Math.max(1, barW - 1)) * 2 - 1
    const li = (((t + 1) * 0.5 * (n - 1)) | 0) * 3
    ctx.fillStyle = `rgb(${lut[li]},${lut[li + 1]},${lut[li + 2]})`
    ctx.fillRect(x + px, midY - barH / 2, 1, barH)
  }
  ctx.strokeStyle = '#E5E9F2'; ctx.lineWidth = Math.max(1, d)
  ctx.strokeRect(x, midY - barH / 2, barW, barH)
  x += barW + gap
  ctx.fillStyle = '#79859A'; ctx.fillText(hiT, x, midY); x += hiW + gap
  ctx.fillText(props.unit, x, midY)
}
function exportPng() {
  const list = props.cells
  if (!list.length) return
  renderInto(modalCanvasMap, modalHitMap) // 先刷一遍，确保大图是最新（游标 / 数据可能刚变）
  const d = 2 // 2× 输出，导出图更锐
  const P = 18 * d, GAP = 14 * d
  const cellW = 226 * d, labelH = 28 * d, imgH = 212 * d, cellH = labelH + imgH
  const cols = list.length <= 3 ? list.length : Math.min(4, Math.ceil(Math.sqrt(list.length)))
  const rows = Math.ceil(list.length / cols)
  const W = P * 2 + cols * cellW + (cols - 1) * GAP
  const gridTop = P
  const gridBottom = gridTop + rows * cellH + (rows - 1) * GAP
  const hasBar = props.vmax > 0
  const footerGap = hasBar ? 14 * d : 0
  const footerH = hasBar ? 16 * d : 0
  const H = gridBottom + footerGap + footerH + P
  const cv = document.createElement('canvas')
  cv.width = W; cv.height = H
  const ctx = cv.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, H)

  // 每格：卡片描边 + 顶部条件色条 + 条件名（含色点）+ 居中地形图
  for (let i = 0; i < list.length; i++) {
    const c = list[i]
    const x = P + (i % cols) * (cellW + GAP)
    const y = gridTop + Math.floor(i / cols) * (cellH + GAP)
    ctx.strokeStyle = '#E5E9F2'; ctx.lineWidth = Math.max(1, d)
    ctx.strokeRect(x + 0.5 * d, y + 0.5 * d, cellW - d, cellH - d)
    ctx.fillStyle = c.color; ctx.fillRect(x, y, cellW, 3 * d)
    // 标签
    const lblY = y + 3 * d + (labelH - 3 * d) / 2
    ctx.font = `600 ${12 * d}px ${EXPORT_FONT}`
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    const lw = ctx.measureText(c.label).width
    const cxText = x + cellW / 2
    const dotR = 3.5 * d
    ctx.fillStyle = c.color
    ctx.beginPath(); ctx.arc(cxText - lw / 2 - dotR - 4 * d, lblY, dotR, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = '#51607A'; ctx.fillText(c.label, cxText, lblY)
    // 地形图（等比居中贴进图区，杜绝拉伸）
    const iy = y + labelH, iw = cellW, ih = imgH
    const canvas = modalCanvasMap.get(c.seg)
    if (canvas && canvas.width && canvas.height) {
      const s = Math.min(iw / canvas.width, ih / canvas.height)
      const dw = canvas.width * s, dh = canvas.height * s
      ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'
      ctx.drawImage(canvas, x + (iw - dw) / 2, iy + (ih - dh) / 2, dw, dh)
    } else {
      ctx.fillStyle = '#79859A'; ctx.font = `400 ${11 * d}px ${EXPORT_FONT}`
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText('无电极坐标', x + iw / 2, iy + ih / 2)
    }
  }

  // 底部唯一图例：居中色阶（标题 / 副标题等 UI 文字不印进图）
  if (hasBar) drawExportBar(ctx, W / 2, gridBottom + footerGap + footerH / 2, 170 * d, 11 * d, d)

  const name = '地形图' + (props.subtitle ? '_' + sanitizeName(props.subtitle) : '') + '.png'
  cv.toBlob((blob) => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = name
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, 'image/png')
}

onMounted(async () => { await nextTick(); renderAll() })
onUnmounted(() => { worker?.terminate(); worker = null })
</script>

<style scoped>
/* 自绘放大镜光标（描白边 + elys 招牌蓝＝色板冷端钴蓝 #2D5096，比 UI 亮蓝更深更沉），替掉系统默认那只糙放大镜；hotspot 落在镜片中心 (11,11) */
.topo-strip { flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; margin-top: 8px; --cursor-zoom: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='28'%20height='28'%20viewBox='0%200%2028%2028'%3E%3Cg%20fill='none'%20stroke-linecap='round'%3E%3Ccircle%20cx='11'%20cy='11'%20r='7.5'%20stroke='%23ffffff'%20stroke-width='4'/%3E%3Cline%20x1='16.5'%20y1='16.5'%20x2='23.5'%20y2='23.5'%20stroke='%23ffffff'%20stroke-width='4'/%3E%3Ccircle%20cx='11'%20cy='11'%20r='7.5'%20stroke='%232D5096'%20stroke-width='2.2'/%3E%3Cline%20x1='16.5'%20y1='16.5'%20x2='23.5'%20y2='23.5'%20stroke='%232D5096'%20stroke-width='2.2'/%3E%3C/g%3E%3C/svg%3E") 11 11, pointer; }
/* 固定宽度：游标 ms 位数变化（5 / 315 / 1000）不再改变本列宽度，右侧地形图卡不再左右抖动 */
.topo-cap { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; font-size: 11px; color: var(--c-text-2); }
.topo-cap-sub { font-size: 11px; color: var(--c-text-3); font-variant-numeric: tabular-nums; }
.topo-cap-right { margin-left: auto; display: inline-flex; align-items: center; gap: 10px; }
/* 「放大」入口：低噪声药丸按钮，给非技术受众一个显式可发现的开关（双击同样可开） */
.topo-expand { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; font-size: 11px; color: var(--c-text-2); background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 999px; cursor: pointer; line-height: 1.7; }
.topo-expand:hover { color: var(--c-text); background: var(--c-bg-soft); }
.topo-expand svg { flex-shrink: 0; }
.topo-cards { display: flex; gap: 8px; overflow-x: auto; flex: 1; cursor: var(--cursor-zoom); }
.topo-card { width: 140px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; border: 1px solid var(--c-border); border-top-width: 2px; border-radius: var(--r-sm); background: var(--c-surface); padding: 4px 4px 2px; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.topo-hd { font-size: 9px; font-weight: 600; color: var(--c-text-2); display: flex; align-items: center; gap: 4px; max-width: 100%; }
.topo-hd-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topo-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.topo-cv { width: 100%; height: 96px; display: block; }
.topo-empty { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 9px; color: var(--c-text-3); line-height: 1.4; padding: 12px 4px; }

/* 成分墙（ICA 等）：网格平铺 + 可点选 + 选中/标记态。默认 strip + 非 selectable 时这些规则不命中，三观察页零影响。 */
.topo-cards.is-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); overflow-x: visible; cursor: default; }
.is-grid .topo-card { width: auto; }
.topo-card.is-sel { cursor: pointer; transition: border-color .12s, box-shadow .12s, background .12s; }
.topo-card.is-sel:hover { border-color: var(--c-primary); }
.topo-card.is-active { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(46, 107, 255, .18); }
.topo-card.is-marked { background: rgba(239, 68, 68, .05); border-left-color: rgba(239, 68, 68, .4); border-right-color: rgba(239, 68, 68, .4); border-bottom-color: rgba(239, 68, 68, .4); }
.topo-sub { font-size: 9px; color: var(--c-text-3); font-variant-numeric: tabular-nums; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── 放大查看弹窗：外壳沿用全站 modal 规格（surface + r-md + shadow-lg）；宽度按卡片数自适应（fit-content），少量卡片时自然收窄、不留大白边 ── */
.topo-modal { width: fit-content; max-width: 92vw; max-height: 88vh; display: flex; flex-direction: column; border: 1px solid var(--c-border); border-radius: var(--r-md); background: var(--c-surface); box-shadow: var(--shadow-lg); overflow: hidden; }
.topo-modal-hd { flex-shrink: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px; padding: 13px 16px; border-bottom: 1px solid var(--c-border); }
.topo-modal-ttl { font-size: 14px; font-weight: 600; color: var(--c-text); }
.topo-modal-actions { margin-left: auto; display: inline-flex; align-items: center; gap: 14px; }
.topo-modal-bar { display: inline-flex; align-items: center; gap: 5px; font-family: var(--ff-mono); font-size: 11px; color: var(--c-text-3); }
.topo-modal-grad { width: 120px; height: 10px; border-radius: 2px; border: 1px solid var(--c-border); }
.topo-modal-unit { margin-left: 2px; }
.topo-modal-dl { display: inline-flex; align-items: center; gap: 5px; padding: 5px 11px; font-size: 12px; font-weight: 500; color: var(--c-primary, #2E6BFF); background: var(--c-primary-soft, #E8F0FF); border: 1px solid transparent; border-radius: 999px; cursor: pointer; line-height: 1.3; }
.topo-modal-dl:hover { filter: brightness(0.97); }
.topo-modal-dl svg { flex-shrink: 0; }
.topo-modal-x { display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; padding: 0; color: var(--c-text-3); background: transparent; border: none; border-radius: var(--r-sm); cursor: pointer; }
.topo-modal-x:hover { color: var(--c-text); background: var(--c-bg-soft); }
.topo-modal-grid { flex: 1; overflow-y: auto; display: grid; justify-content: center; gap: 14px; padding: 16px; background: var(--c-bg-soft); }
.topo-modal-card { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 10px 10px 12px; border: 1px solid var(--c-border); border-top-width: 3px; border-radius: var(--r-sm); background: var(--c-surface); box-shadow: var(--shadow-sm); }
.topo-modal-cardhd { width: 100%; display: flex; align-items: center; justify-content: center; gap: 5px; font-size: 12px; font-weight: 600; color: var(--c-text-2); }
.topo-modal-cardname { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topo-modal-cv { width: 100%; height: 230px; display: block; }
.topo-modal-empty { width: 100%; height: 230px; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 11px; color: var(--c-text-3); line-height: 1.5; }
</style>
