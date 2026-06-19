<template>
  <div class="stats-page">
    <header class="sp-head">
      <div class="sp-id">
        <span class="sp-badge">STAT</span>
        <div>
          <div class="sp-title">{{ contrastLabel }}<span class="sp-region">统计比较</span></div>
          <div class="sp-sub" v-if="data">
            <span class="sp-tag">{{ baseLabel }}</span>
            <span class="sp-tag">{{ designLabel }}</span>
            <span class="sp-tag">{{ methodLabel }}</span>
            <span class="sp-tag" v-if="data.method === 'pointwise'">{{ correctionLabel }}</span>
            <span class="sp-tag">α = {{ data.alpha }}</span>
            <span class="sp-tag">n: {{ data.n_a }} vs {{ data.n_b }}</span>
          </div>
        </div>
      </div>
      <button class="sp-btn" @click="load()" :disabled="loading">刷新</button>
    </header>

    <div class="sp-main" v-if="data">
      <!-- 左：通道 -->
      <aside class="sp-left">
        <div class="sp-left-h">通道<span class="sp-cnt">{{ data.ch_names.length }}</span></div>
        <div class="sp-chan-list">
          <button
            v-for="ch in data.ch_names"
            :key="ch"
            class="sp-chan"
            :class="{ 'is-sel': ch === selectedChannel, 'is-roi': roiSet.has(ch) }"
            @click="selectChannel(ch)"
          >
            <span class="sp-chan-name">{{ ch }}</span>
            <span v-if="roiSet.has(ch)" class="sp-chan-roi" title="cluster ROI 通道">◆</span>
          </button>
        </div>
      </aside>

      <!-- 中：主图 -->
      <section class="sp-canvas">
        <div class="sp-canvas-head">
          <span class="sp-canvas-title">通道 {{ selectedChannel }}</span>
          <span class="sp-legend" v-if="is1D">
            <i class="lg lg-a"></i>{{ labelA }}<i class="lg lg-b"></i>{{ labelB }}<i class="lg lg-sig"></i>显著
          </span>
          <span class="sp-legend" v-else>t 值（<i class="lg lg-neg"></i>负 <i class="lg lg-pos"></i>正），显著 = 不透明</span>
        </div>

        <!-- 1D：ERP / PSD -->
        <template v-if="is1D">
          <svg class="sp-svg" :viewBox="`0 0 ${VW} ${PLOT_H}`" preserveAspectRatio="none">
            <rect v-for="(s, i) in sigSegments" :key="'s' + i" :x="s.x" y="0" :width="s.w" :height="PLOT_H" class="sp-sig-band" />
            <rect
              v-for="(c, i) in clusterBands"
              :key="'c' + i"
              :x="c.x"
              y="0"
              :width="c.w"
              :height="PLOT_H"
              class="sp-clu-band"
              :class="{ 'is-sig': c.sig }"
            />
            <line v-if="zeroInRange" :x1="0" :y1="zeroY" :x2="VW" :y2="zeroY" class="sp-zero" />
            <polyline :points="ptsA" class="sp-line sp-line-a" />
            <polyline :points="ptsB" class="sp-line sp-line-b" />
            <text v-for="(c, i) in clusterBands" :key="'ct' + i" :x="c.cx" y="16" class="sp-clu-label" v-show="c.sig">
              p={{ c.p }}
            </text>
          </svg>
          <div class="sp-axis-row">
            <span>{{ axisMin }}</span><span class="sp-axis-name">{{ axisUnit }}</span><span>{{ axisMax }}</span>
          </div>
        </template>

        <!-- 2D：TFR -->
        <template v-else>
          <div class="sp-heat-wrap"><canvas ref="heatCanvas" class="sp-heat"></canvas></div>
          <div class="sp-axis-row">
            <span>{{ heatTimeLabel }}</span><span class="sp-axis-name">时间 × 频率（{{ heatFreqLabel }}）</span>
          </div>
        </template>
      </section>

      <!-- 右：摘要 + cluster 表 -->
      <aside class="sp-right">
        <div class="sp-card">
          <div class="sp-card-h">对比摘要</div>
          <div class="sp-stat"><span>对比</span><b>{{ contrastLabel }}</b></div>
          <div class="sp-stat"><span>设计</span><b>{{ designLabel }}</b></div>
          <div class="sp-stat"><span>方法</span><b>{{ methodLabel }}</b></div>
          <div class="sp-stat" v-if="data.method === 'pointwise'"><span>校正</span><b>{{ correctionLabel }}</b></div>
          <div class="sp-stat"><span>显著点</span><b>{{ data.n_significant }} / {{ data.n_total }}</b></div>
          <div class="sp-stat"><span>max |t|</span><b>{{ data.tmax_abs }}</b></div>
        </div>

        <div class="sp-card" v-if="data.method === 'cluster'">
          <div class="sp-card-h">显著簇（ROI：{{ roiText }}）</div>
          <div v-if="!data.clusters.length" class="sp-empty">未检出任何簇</div>
          <table v-else class="sp-clu-table">
            <thead><tr><th>窗口</th><th>p</th></tr></thead>
            <tbody>
              <tr v-for="(c, i) in data.clusters" :key="i" :class="{ 'is-sig': c.significant }">
                <td>{{ clusterWindowText(c) }}</td>
                <td>{{ c.p }}<span v-if="c.significant" class="sp-star">*</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="sp-note">{{ statNote }}</div>
      </aside>
    </div>

    <div v-else-if="loading" class="sp-state">加载统计图…</div>
    <div v-else class="sp-state sp-err">{{ error || '无数据' }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { pipelineApi } from '@/api/pipelines'
import { useQueryString } from '@/composables/observe/observeUtils'
import type { StudyOutputStat, StudyOutputStatCluster } from '@/types'

const VW = 1000
const PLOT_H = 320

const qstr = useQueryString()
const studyId = qstr('studyId') || qstr('study_id')
const outputId = (qstr('study_output_id') || qstr('dd')).split(',')[0]?.trim() || ''

const data = ref<StudyOutputStat | null>(null)
const loading = ref(false)
const error = ref('')
const selectedChannel = ref('')
const heatCanvas = ref<HTMLCanvasElement | null>(null)

const is1D = computed(() => (data.value?.base_type || '') !== 'tfr')

async function load(channel?: string) {
  if (!studyId || !outputId) {
    error.value = '缺少参数：需要 studyId 与 study_output_id。'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await pipelineApi.getStudyOutputStat(studyId, outputId, { channel })
    data.value = res.data
    selectedChannel.value = res.data.channel
    if (!is1D.value) {
      await nextTick()
      drawHeat()
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: { message?: string } } }; message?: string }
    error.value = err?.response?.data?.detail?.message || err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function selectChannel(ch: string) {
  if (ch !== selectedChannel.value) load(ch)
}

// ---------- 文案 ----------
const contrastLabel = computed(() => data.value?.contrast_label || '统计比较')
const labelAB = computed(() => contrastLabel.value.split('−').map((s) => s.trim()))
const labelA = computed(() => labelAB.value[0] || '组 A')
const labelB = computed(() => labelAB.value[1] || '组 B')
const baseLabel = computed(
  () => ({ evoked: 'ERP（时域）', psd: 'PSD（频域）', tfr: 'TFR（时频）' } as Record<string, string>)[data.value?.base_type || ''] || data.value?.base_type || '',
)
const designLabel = computed(() => (data.value?.design === 'paired' ? '配对' : '独立'))
const methodLabel = computed(() => (data.value?.method === 'cluster' ? 'Cluster permutation' : '逐点 t 检验'))
const correctionLabel = computed(() => (data.value?.correction === 'fdr' ? 'FDR 校正' : '未校正'))
const roiSet = computed(() => new Set(data.value?.roi_channels || []))
const roiText = computed(() => {
  const roi = data.value?.roi_channels || []
  if (!roi.length || roi.length === (data.value?.ch_names.length || 0)) return '全通道'
  return roi.join('、')
})
const statNote = computed(() =>
  data.value?.method === 'cluster'
    ? 'ROI 置换聚类检验：在选定通道平均后沿连续轴成簇，置换零分布控制多重比较；簇 p < α 标显著。'
    : `逐点 t 检验：每个点独立比较，${correctionLabel.value}后 p < α 标显著（着色带）。`,
)

// ---------- 1D 几何 ----------
const axisValues = computed(() => (is1D.value ? data.value?.axis?.values || [] : []))
const meanA = computed(() => data.value?.mean_a || [])
const meanB = computed(() => data.value?.mean_b || [])
const sigArr = computed(() => data.value?.sig || [])
const axisUnit = computed(() => (data.value?.base_type === 'evoked' ? 's' : 'Hz'))
const axisMin = computed(() => (axisValues.value.length ? axisValues.value[0] : 0))
const axisMax = computed(() => (axisValues.value.length ? axisValues.value[axisValues.value.length - 1] : 0))

const yDomain = computed(() => {
  const all = [...meanA.value, ...meanB.value].filter((v) => Number.isFinite(v))
  if (!all.length) return [0, 1]
  let lo = Math.min(...all)
  let hi = Math.max(...all)
  if (lo === hi) { lo -= 1; hi += 1 }
  const pad = (hi - lo) * 0.08
  return [lo - pad, hi + pad]
})
function xOf(i: number): number {
  const n = axisValues.value.length
  return n > 1 ? (i / (n - 1)) * VW : 0
}
function xVal(v: number): number {
  const lo = axisMin.value
  const hi = axisMax.value
  return hi > lo ? ((v - lo) / (hi - lo)) * VW : 0
}
function yOf(v: number): number {
  const [lo, hi] = yDomain.value
  return hi > lo ? PLOT_H - ((v - lo) / (hi - lo)) * PLOT_H : PLOT_H / 2
}
function polyline(arr: number[]): string {
  return arr.map((v, i) => `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`).join(' ')
}
const ptsA = computed(() => polyline(meanA.value))
const ptsB = computed(() => polyline(meanB.value))
const zeroInRange = computed(() => yDomain.value[0] < 0 && yDomain.value[1] > 0)
const zeroY = computed(() => yOf(0))

// 显著点的连续段 → 着色带
const sigSegments = computed(() => {
  const sig = sigArr.value
  const segs: { x: number; w: number }[] = []
  let start = -1
  for (let i = 0; i <= sig.length; i++) {
    if (i < sig.length && sig[i]) {
      if (start < 0) start = i
    } else if (start >= 0) {
      const x0 = xOf(start)
      const x1 = xOf(i - 1)
      segs.push({ x: x0, w: Math.max(1.5, x1 - x0) })
      start = -1
    }
  }
  return segs
})

// cluster 窗口 → 着色带（沿轴映射）
const clusterBands = computed(() => {
  const base = data.value?.base_type
  const out: { x: number; w: number; cx: number; sig: boolean; p: number }[] = []
  for (const c of data.value?.clusters || []) {
    let lo: number | undefined
    let hi: number | undefined
    if (base === 'evoked') { lo = c.tmin; hi = c.tmax }
    else if (base === 'psd') { lo = c.fmin; hi = c.fmax }
    if (lo === undefined || hi === undefined) continue
    const x0 = xVal(lo)
    const x1 = xVal(hi)
    out.push({ x: x0, w: Math.max(2, x1 - x0), cx: (x0 + x1) / 2, sig: !!c.significant, p: c.p })
  }
  return out
})

// ---------- 2D 热图 ----------
const heatFreqLabel = computed(() => {
  const f = data.value?.axis?.freqs || []
  return f.length ? `${f[0]}–${f[f.length - 1]} Hz` : ''
})
const heatTimeLabel = computed(() => {
  const t = data.value?.axis?.times || []
  return t.length ? `${t[0]} – ${t[t.length - 1]} s` : ''
})

function diverge(t: number, tmax: number): string {
  const x = Math.max(-1, Math.min(1, tmax > 0 ? t / tmax : 0))
  let r: number, g: number, b: number
  if (x >= 0) { r = 255 - 55 * x; g = 255 - 215 * x; b = 255 - 225 * x }
  else { const a = -x; r = 255 - 215 * a; g = 255 - 165 * a; b = 255 - 75 * a }
  return `${Math.round(r)},${Math.round(g)},${Math.round(b)}`
}

function drawHeat() {
  const c = heatCanvas.value
  const d = data.value
  if (!c || !d || !d.t_grid || !d.t_grid.length) return
  const grid = d.t_grid
  const sg = d.sig_grid || []
  const nf = grid.length
  const nt = grid[0]?.length || 0
  if (!nf || !nt) return
  const cw = c.clientWidth || 600
  const ch = c.clientHeight || 320
  const dpr = window.devicePixelRatio || 1
  c.width = Math.round(cw * dpr)
  c.height = Math.round(ch * dpr)
  const ctx = c.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  const tmax = d.tmax_abs || 1
  const cellW = cw / nt
  const cellH = ch / nf
  for (let fi = 0; fi < nf; fi++) {
    const rowY = (nf - 1 - fi) * cellH // 高频在上
    for (let ti = 0; ti < nt; ti++) {
      const sig = sg[fi]?.[ti]
      ctx.fillStyle = `rgba(${diverge(grid[fi][ti], tmax)},${sig ? 1 : 0.32})`
      ctx.fillRect(ti * cellW, rowY, cellW + 0.6, cellH + 0.6)
    }
  }
}

function clusterWindowText(c: StudyOutputStatCluster): string {
  const base = data.value?.base_type
  if (base === 'evoked') return `${c.tmin} – ${c.tmax} s`
  if (base === 'psd') return `${c.fmin} – ${c.fmax} Hz`
  if (base === 'tfr') return `${c.fmin}–${c.fmax} Hz × ${c.tmin}–${c.tmax} s`
  return `${c.n_points} 点`
}

function onResize() {
  if (!is1D.value) drawHeat()
}
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.stats-page { display: flex; flex-direction: column; height: 100vh; background: #f6f7f9; color: #1f2937; font-size: 13px; }
.sp-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.sp-id { display: flex; align-items: center; gap: 10px; }
.sp-badge { background: #b42318; color: #fff; font-weight: 700; font-size: 11px; padding: 3px 7px; border-radius: 5px; letter-spacing: 0.5px; }
.sp-title { font-size: 15px; font-weight: 600; }
.sp-region { color: #9ca3af; font-weight: 400; font-size: 12px; margin-left: 8px; }
.sp-sub { margin-top: 3px; display: flex; flex-wrap: wrap; gap: 6px; }
.sp-tag { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 1px 6px; font-size: 11px; color: #4b5563; }
.sp-btn { border: 1px solid #d1d5db; background: #fff; border-radius: 6px; padding: 5px 12px; cursor: pointer; color: #374151; }
.sp-btn:hover { background: #f9fafb; }
.sp-btn:disabled { opacity: 0.5; cursor: default; }

.sp-main { flex: 1; display: flex; min-height: 0; }
.sp-left { width: 150px; border-right: 1px solid #e5e7eb; background: #fff; display: flex; flex-direction: column; min-height: 0; }
.sp-left-h { padding: 8px 12px; font-weight: 600; border-bottom: 1px solid #f0f1f3; display: flex; justify-content: space-between; }
.sp-cnt { color: #9ca3af; font-weight: 400; }
.sp-chan-list { overflow-y: auto; flex: 1; padding: 4px; }
.sp-chan { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 4px; border: none; background: transparent; padding: 5px 8px; border-radius: 5px; cursor: pointer; color: #374151; font-size: 12px; }
.sp-chan:hover { background: #f3f4f6; }
.sp-chan.is-sel { background: #fce9e7; color: #b42318; font-weight: 600; }
.sp-chan-roi { color: #b42318; font-size: 9px; }

.sp-canvas { flex: 1; display: flex; flex-direction: column; min-width: 0; padding: 12px 16px; }
.sp-canvas-head { display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }
.sp-canvas-title { font-weight: 600; }
.sp-legend { color: #6b7280; font-size: 12px; display: flex; align-items: center; gap: 4px; }
.lg { display: inline-block; width: 14px; height: 3px; border-radius: 2px; margin: 0 2px 0 8px; }
.lg-a { background: #2f5f8f; } .lg-b { background: #b07f33; }
.lg-sig { background: rgba(180, 35, 24, 0.25); height: 10px; }
.lg-pos { background: #c83820; height: 10px; width: 10px; } .lg-neg { background: #285ab4; height: 10px; width: 10px; }
.sp-svg { width: 100%; flex: 1; min-height: 0; background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; }
.sp-sig-band { fill: rgba(180, 35, 24, 0.1); }
.sp-clu-band { fill: rgba(180, 35, 24, 0.04); stroke: rgba(180, 35, 24, 0.35); stroke-dasharray: 3 3; stroke-width: 1; }
.sp-clu-band.is-sig { fill: rgba(180, 35, 24, 0.13); stroke: rgba(180, 35, 24, 0.7); stroke-dasharray: none; }
.sp-clu-label { fill: #b42318; font-size: 11px; font-weight: 600; }
.sp-zero { stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 4 3; }
.sp-line { fill: none; stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.sp-line-a { stroke: #2f5f8f; } .sp-line-b { stroke: #b07f33; }
.sp-heat-wrap { flex: 1; min-height: 0; background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.sp-heat { width: 100%; height: 100%; display: block; }
.sp-axis-row { display: flex; justify-content: space-between; color: #9ca3af; font-size: 11px; margin-top: 4px; }
.sp-axis-name { color: #6b7280; }

.sp-right { width: 230px; border-left: 1px solid #e5e7eb; background: #fff; padding: 12px; overflow-y: auto; }
.sp-card { border: 1px solid #eceef1; border-radius: 8px; padding: 10px; margin-bottom: 12px; }
.sp-card-h { font-weight: 600; margin-bottom: 8px; font-size: 12px; }
.sp-stat { display: flex; justify-content: space-between; padding: 3px 0; color: #6b7280; }
.sp-stat b { color: #1f2937; font-weight: 600; }
.sp-clu-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sp-clu-table th { text-align: left; color: #9ca3af; font-weight: 500; border-bottom: 1px solid #f0f1f3; padding: 3px 2px; }
.sp-clu-table td { padding: 4px 2px; border-bottom: 1px solid #f6f7f8; color: #6b7280; }
.sp-clu-table tr.is-sig td { color: #1f2937; font-weight: 600; }
.sp-star { color: #b42318; margin-left: 2px; }
.sp-empty { color: #9ca3af; font-size: 12px; }
.sp-note { color: #9ca3af; font-size: 11px; line-height: 1.5; margin-top: 4px; }
.sp-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #9ca3af; }
.sp-err { color: #b42318; }
</style>
