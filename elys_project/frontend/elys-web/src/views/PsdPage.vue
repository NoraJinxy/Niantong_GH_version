<template>
  <WorkbenchShell active-key="view-psd" active-top-key="observe">
    <div v-if="!isLive" class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">3</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name" style="font-weight: 500">sub-01_psd_resting</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">eyes-open</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">eyes-closed</span></div>
            <div class="ck-node"><input type="checkbox" checked /><span class="name" style="font-weight: 500">sub-03_psd_resting</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">resting</span></div>
            <div class="ck-node"><input type="checkbox" /><span class="name" style="font-weight: 500">sub-05_psd_task</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>条件 <span class="count">3</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span class="cond-pill active s1"><span class="dot"></span>eyes-open</span>
            <span class="cond-pill active s2"><span class="dot"></span>eyes-closed</span>
            <span class="cond-pill"><span class="dot"></span>resting</span>
          </div>
        </div>

        <div class="sel-section">
          <h4>通道 <span class="count">5</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span v-for="ch in channels" :key="ch.id" class="ch-tag">{{ ch.label }}</span>
          </div>
        </div>

        <div class="sel-section">
          <h4>频段 <span class="count">5</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span v-for="band in bands" :key="band.name" class="band-pill" :class="{ active: band.active }">
              <span class="bdot" :style="{ background: band.color }"></span>{{ band.name }}
            </span>
          </div>
        </div>

        <div class="sel-section">
          <h4>显示选项</h4>
          <label class="checkbox-row"><input type="checkbox" checked />频段背景着色</label>
          <label class="checkbox-row"><input type="checkbox" checked />峰值标记 / IAF</label>
          <label class="checkbox-row"><input type="checkbox" checked />SEM 包络</label>
          <label class="checkbox-row"><input type="checkbox" />对数 Y 轴</label>
          <label class="checkbox-row"><input type="checkbox" checked />地形图侧栏</label>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="psd">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">3 数据集 · 5 通道 · 5 频段</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <button class="btn btn--sm">‹</button>
          <span style="font-family: var(--ff-mono); font-size: 12px; min-width: 100px; text-align: center; color: var(--c-text)">0 – 45 Hz</span>
          <button class="btn btn--sm">›</button>
          <div class="divider-h"></div>
          <span class="tool-lbl">频窗</span>
          <select><option selected>0 – 45 Hz</option><option>0 – 30 Hz</option><option>0 – 100 Hz</option></select>
          <span class="tool-lbl">Y 轴</span>
          <select><option>自动</option><option selected>线性</option><option>对数 (dB)</option></select>
          <div class="divider-h"></div>
          <label class="checkbox-row" style="font-size: 11px"><input type="checkbox" checked />频段背景</label>
          <label class="checkbox-row" style="font-size: 11px"><input type="checkbox" checked />峰值标记</label>
          <label class="checkbox-row" style="font-size: 11px"><input type="checkbox" checked />SEM 包络</label>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">+ 添加面板</button>
          <button class="btn btn--sm">导出</button>
        </div>

        <div class="region-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" /></svg>
          <span class="label">已选频段：α (8 – 13 Hz)</span>
          <span class="hint">右侧面板显示该频段统计</span>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">清除</button>
        </div>

        <div class="panel-grid psd-panels">
          <div v-for="ch in channels" :key="ch.id" class="obs-panel">
            <div class="panel-head">
              <span class="ch-tag-solid" :style="{ background: ch.color }">{{ ch.label }}</span>
              <span class="title">{{ ch.subtitle }}<span v-if="ch.star" style="color: var(--c-success)"> · ★ 最大 α</span></span>
              <span class="stats">α peak {{ ch.amp }} μV² @{{ ch.peak }}Hz</span>
            </div>
            <div class="panel-body">
              <svg viewBox="0 0 400 200" preserveAspectRatio="none">
                <rect width="400" height="200" fill="#fff" />
                <rect x="0" y="0" width="32" height="200" fill="#3B82F6" fill-opacity=".12" />
                <rect x="32" y="0" width="32" height="200" fill="#10B981" fill-opacity=".12" />
                <rect x="64" y="0" width="40" height="200" fill="#F59E0B" fill-opacity=".12" />
                <rect x="104" y="0" width="136" height="200" fill="#F97316" fill-opacity=".12" />
                <rect x="240" y="0" width="160" height="200" fill="#EF4444" fill-opacity=".12" />
                <rect x="64" y="0" width="40" height="200" fill="rgba(46,107,255,.12)" />
                <line x1="0" y1="100" x2="400" y2="100" stroke="#E5E9F2" stroke-width="0.5" stroke-dasharray="3 3" />
                <line x1="0" y1="50" x2="400" y2="50" stroke="#E5E9F2" stroke-width="0.5" stroke-dasharray="3 3" />
                <line x1="0" y1="150" x2="400" y2="150" stroke="#E5E9F2" stroke-width="0.5" stroke-dasharray="3 3" />
                <g font-size="8" font-family="monospace" fill="var(--c-text-3)">
                  <text x="16" y="196" text-anchor="middle">δ</text>
                  <text x="48" y="196" text-anchor="middle">θ</text>
                  <text x="84" y="196" text-anchor="middle">α</text>
                  <text x="172" y="196" text-anchor="middle">β</text>
                  <text x="320" y="196" text-anchor="middle">γ</text>
                </g>
                <path :d="ch.semPath" fill="#2E6BFF" fill-opacity="0.08" stroke="none" />
                <path :d="ch.curveS1" stroke="#2E6BFF" stroke-width="1.8" fill="none" />
                <path :d="ch.curveS2" stroke="#10B981" stroke-width="1.8" fill="none" />
                <path :d="ch.curveS3" stroke="#F59E0B" stroke-width="1.8" fill="none" stroke-dasharray="4 3" />
                <text x="4" y="14" fill="#5B6B85" font-size="8" font-family="monospace">μV²/Hz</text>
                <text x="396" y="196" fill="#5B6B85" font-size="8" text-anchor="end" font-family="monospace">Hz</text>
              </svg>
            </div>
          </div>

          <div class="obs-panel">
            <div class="panel-head">
              <span class="ch-tag-solid" style="background: #5B6B85">Σ</span>
              <span class="title">通道叠加</span>
              <span class="stats">α band 平均</span>
            </div>
            <div class="panel-body">
              <svg viewBox="0 0 400 200" preserveAspectRatio="none">
                <rect width="400" height="200" fill="#fff" />
                <rect x="64" y="0" width="40" height="200" fill="rgba(46,107,255,.12)" />
                <line x1="0" y1="100" x2="400" y2="100" stroke="#E5E9F2" stroke-width="0.5" stroke-dasharray="3 3" />
                <path v-for="ch in channels" :key="ch.id" :d="ch.curveS2" :stroke="ch.color" stroke-width="1.2" fill="none" opacity="0.7" />
              </svg>
            </div>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>频段统计 · Alpha (8–13 Hz)</h4>
          <div v-for="ch in channels" :key="ch.id" class="st-card">
            <div class="ttl">
              <span class="pin" :style="{ background: ch.color }"></span>{{ ch.label }}
              <span v-if="ch.star" style="margin-left: auto; font-size: 9px; color: var(--c-success)">★ 最大</span>
            </div>
            <div class="st-grid">
              <div class="st-cell"><span class="k">均值</span><span class="v">{{ (ch.amp * 0.93).toFixed(1) }} μV²</span></div>
              <div class="st-cell"><span class="k">峰值</span><span class="v" :style="{ color: ch.star ? 'var(--c-success)' : 'var(--c-primary)' }">{{ ch.amp }} @{{ ch.peak }}Hz</span></div>
              <div class="st-cell"><span class="k">绝对功率</span><span class="v">{{ (ch.amp * 0.18).toFixed(2) }} μV²</span></div>
              <div class="st-cell"><span class="k">相对功率</span><span class="v">{{ (ch.amp * 2.4).toFixed(1) }} %</span></div>
            </div>
          </div>
        </div>

        <div class="st-section">
          <h4>条件对比 · α 频段</h4>
          <table class="small-tbl">
            <thead><tr><th>通道</th><th>open</th><th>closed</th><th>Δ</th></tr></thead>
            <tbody>
              <tr v-for="ch in channels" :key="ch.id">
                <td>{{ ch.label }}</td>
                <td>{{ (ch.amp * 0.7).toFixed(1) }}</td>
                <td>{{ ch.amp }}</td>
                <td style="color: var(--c-success); font-weight: 700">+{{ (ch.amp * 0.3).toFixed(1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="st-section">
          <h4>IAF 检测</h4>
          <div class="iaf-alert">
            <strong>IAF = 10.2 Hz</strong>
            <div class="iaf-sub">检测置信度高 · sub-01 eyes-closed</div>
          </div>
        </div>

        <div class="st-section">
          <h4>频段地形图 · α</h4>
          <div class="topomap" style="height: 120px"></div>
          <div style="text-align: center; font-size: 11px; color: var(--c-text-2); margin-top: 4px">
            8–13 Hz 平均功率
          </div>
          <select class="select input--sm" style="margin-top: 8px; width: 100%; font-family: var(--ff-mono)">
            <option>δ 地形图</option>
            <option>θ 地形图</option>
            <option selected>α 地形图（当前）</option>
            <option>β 地形图</option>
            <option>γ 地形图</option>
          </select>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <button class="btn">导出统计 CSV</button>
          <RouterLink class="btn" to="/figures">发送到作图模块</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计模块</RouterLink>
        </div>
      </aside>
    </div>

    <div v-else class="obs-layout obs-layout--live">
      <main class="obs-main">
        <ObserveTabs active="psd">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">{{ liveMeta }}</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">通道</span>
          <select :value="selectedChannel" @change="selectChannel(($event.target as HTMLSelectElement).value)">
            <option v-for="ch in channelOptions" :key="ch" :value="ch">{{ ch }}</option>
          </select>
          <div style="flex: 1"></div>
          <button class="btn btn--sm btn--primary" @click="refresh">▶ 刷新</button>
        </div>

        <div class="psd-live-card">
          <div class="psd-live-card__head">
            <h2>功率谱 · {{ selectedChannel }} · {{ live?.condition || '—' }}</h2>
            <p>Welch · {{ fmtHz(live?.fmin) }}–{{ fmtHz(live?.fmax) }} Hz · {{ live?.n_channels_total ?? '—' }} 通道</p>
          </div>
          <div class="psd-live-plot">
            <div v-if="liveLoading" class="psd-state">正在加载功率谱…</div>
            <div v-else-if="liveError" class="psd-state psd-state--err">{{ liveError }}</div>
            <svg viewBox="0 0 760 320" preserveAspectRatio="xMidYMid meet" class="psd-svg">
              <rect width="760" height="320" fill="#fff" />
              <g transform="translate(56, 16)">
                <line v-for="g in yGrid" :key="`y${g.y}`" x1="0" :y1="g.y" x2="660" :y2="g.y" stroke="#E5E9F2" stroke-width="0.5" stroke-dasharray="3 3" />
                <text v-for="g in yGrid" :key="`yl${g.y}`" x="-8" :y="g.y + 3" font-size="10" text-anchor="end" fill="#577190" font-family="monospace">{{ g.label }}</text>
                <line x1="0" y1="0" x2="0" y2="260" stroke="#bbccdd" />
                <line x1="0" y1="260" x2="660" y2="260" stroke="#bbccdd" />
                <text v-for="t in xTicks" :key="`x${t.x}`" :x="t.x" y="278" font-size="10" text-anchor="middle" fill="#577190" font-family="monospace">{{ t.label }}</text>
                <polyline v-if="linePath" :points="linePath" fill="none" stroke="#2563EB" stroke-width="1.8" />
                <text x="-44" y="130" font-size="11" fill="#5B6B85" transform="rotate(-90 -44 130)">功率 (dB)</text>
                <text x="330" y="300" font-size="11" fill="#5B6B85">频率 (Hz)</text>
              </g>
            </svg>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>频带平均功率 (dB)</h4>
          <div class="stat-grid">
            <div v-for="b in live?.bands || []" :key="b.name" class="stat-card">
              <div class="stat-label">{{ b.name }} ({{ b.fmin }}–{{ b.fmax }} Hz)</div>
              <div class="stat-value">{{ b.value.toFixed(1) }}<span class="unit"> dB</span></div>
            </div>
          </div>
        </div>
        <div class="st-section">
          <h4>导出</h4>
          <RouterLink class="btn" to="/figures">发送到作图模块</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计模块</RouterLink>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'
import { pipelineApi } from '@/api/pipelines'
import type { StudyOutputPsd } from '@/types'

// ── 双模式：路由带 study_output_id+studyId → 拉真实功率谱；否则保留静态设计稿 ──
const route = useRoute()
const studyId = computed(() => String(route.query.studyId || route.query.study_id || ''))
const outputId = computed(() => String(route.query.study_output_id || ''))
const isLive = computed(() => Boolean(studyId.value && outputId.value))

const live = ref<StudyOutputPsd | null>(null)
const liveLoading = ref(false)
const liveError = ref('')
const selectedChannel = ref('')

async function loadPsd(channel?: string) {
  if (!isLive.value) return
  liveLoading.value = true
  liveError.value = ''
  try {
    const res = await pipelineApi.getStudyOutputPsd(studyId.value, outputId.value, channel ? { channel } : {})
    live.value = res.data
    selectedChannel.value = res.data.channel
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail
    liveError.value = detail?.message || (error as Error)?.message || '功率谱加载失败'
  } finally {
    liveLoading.value = false
  }
}

onMounted(() => {
  if (isLive.value) loadPsd()
})

function selectChannel(ch: string) {
  if (!ch) return
  selectedChannel.value = ch
  if (isLive.value) loadPsd(ch)
}

function refresh() {
  if (isLive.value) loadPsd(selectedChannel.value)
}

const channelOptions = computed(() => (live.value ? live.value.ch_names_all : []))

const liveMeta = computed(() => {
  if (!live.value) return ''
  return `${selectedChannel.value} · ${live.value.condition || '—'} · ${Math.round(live.value.sfreq)} Hz`
})

function fmtHz(value: number | null | undefined) {
  if (value == null) return '—'
  return Math.abs(value) >= 10 ? String(Math.round(value)) : String(Math.round(value * 10) / 10)
}

// ── 折线 / 坐标：把 freqs/power 映射到 660×260 绘图区 ──
const PLOT_W = 660
const PLOT_H = 260

const prange = computed(() => {
  const p = live.value?.power || []
  if (!p.length) return { pmin: -1, pmax: 1 }
  const pmin = live.value?.pmin ?? Math.min(...p)
  const pmax = live.value?.pmax ?? Math.max(...p)
  if (pmax <= pmin) return { pmin: pmin - 1, pmax: pmax + 1 }
  return { pmin, pmax }
})

const linePath = computed(() => {
  const freqs = live.value?.freqs || []
  const power = live.value?.power || []
  const n = Math.min(freqs.length, power.length)
  if (n < 2) return ''
  const fmin = freqs[0]
  const fspan = freqs[n - 1] - fmin || 1
  const { pmin, pmax } = prange.value
  const pspan = pmax - pmin || 1
  const pts: string[] = []
  for (let i = 0; i < n; i++) {
    const x = ((freqs[i] - fmin) / fspan) * PLOT_W
    const y = PLOT_H - ((power[i] - pmin) / pspan) * PLOT_H
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`)
  }
  return pts.join(' ')
})

const yGrid = computed(() => {
  const { pmin, pmax } = prange.value
  return [0, 0.5, 1].map((f) => ({
    y: PLOT_H - f * PLOT_H,
    label: String(Math.round(pmin + f * (pmax - pmin))),
  }))
})

const xTicks = computed(() => {
  const freqs = live.value?.freqs || []
  if (!freqs.length) return [] as Array<{ x: number; label: string }>
  const fmin = freqs[0]
  const fmax = freqs[freqs.length - 1]
  return [0, 0.5, 1].map((f) => ({ x: f * PLOT_W, label: fmtHz(fmin + f * (fmax - fmin)) }))
})

function pseudoRand(seed: number) {
  const x = Math.sin(seed * 13.4567) * 43758.5453
  return x - Math.floor(x)
}

function genPsdPath(seed: number, alphaPeak: number, alphaAmp: number, deltaScale: number) {
  let path = ''
  const n = 200
  for (let i = 0; i <= n; i++) {
    const hz = (i / n) * 45
    let v = 0
    v += (8 + deltaScale * 3) / (1 + Math.pow(hz / 2, 1.8))
    v += alphaAmp * Math.exp(-Math.pow((hz - alphaPeak) / 2.5, 2))
    v += alphaAmp * 0.15 * Math.exp(-Math.pow((hz - alphaPeak * 2) / 3, 2))
    v += 2 / (1 + Math.pow(hz / 15, 2))
    v += (pseudoRand(seed + i) - 0.5) * 0.3 * (1 / (1 + hz / 10))
    v = Math.max(v, 0.1)
    const x = (i / n) * 400
    const y = 200 - (v / 25) * 190
    path += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' '
  }
  return path
}

function genPsdSem(seed: number, alphaPeak: number, alphaAmp: number, deltaScale: number) {
  let top = '', bot = ''
  const n = 200
  for (let i = 0; i <= n; i++) {
    const hz = (i / n) * 45
    let v = 0
    v += (8 + deltaScale * 3) / (1 + Math.pow(hz / 2, 1.8))
    v += alphaAmp * Math.exp(-Math.pow((hz - alphaPeak) / 2.5, 2))
    v += alphaAmp * 0.15 * Math.exp(-Math.pow((hz - alphaPeak * 2) / 3, 2))
    v += 2 / (1 + Math.pow(hz / 15, 2))
    const sem = 0.8 + 0.5 * alphaAmp * Math.exp(-Math.pow((hz - alphaPeak) / 3, 2)) * 0.3
    const x = (i / n) * 400
    const yTop = 200 - ((v + sem) / 25) * 190
    const yBot = 200 - ((v - sem) / 25) * 190
    top += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + yTop.toFixed(1) + ' '
    bot = 'L' + x.toFixed(1) + ',' + yBot.toFixed(1) + ' ' + bot
  }
  return top + bot + 'Z'
}

const channelDefs = [
  { id: 'fz', label: 'Fz', color: '#2E6BFF', peak: 10.0, amp: 10.5, delta: 0.8, subtitle: '前额中线 · PSD' },
  { id: 'cz', label: 'Cz', color: '#10B981', peak: 10.2, amp: 15.7, delta: 1.0, subtitle: '中央 · PSD', star: true },
  { id: 'pz', label: 'Pz', color: '#8B5CF6', peak: 9.8, amp: 13.2, delta: 0.9, subtitle: '顶中线 · PSD' },
  { id: 'oz', label: 'Oz', color: '#EF4444', peak: 10.5, amp: 18.3, delta: 0.7, subtitle: '枕区 · PSD' },
  { id: 'cpz', label: 'CPz', color: '#F59E0B', peak: 10.0, amp: 12.1, delta: 0.85, subtitle: '中央顶 · PSD' },
]

const channels = channelDefs.map((ch) => ({
  ...ch,
  curveS1: genPsdPath(ch.peak * 7, ch.peak, ch.amp * 0.65, ch.delta),
  curveS2: genPsdPath(ch.peak * 7 + 1, ch.peak, ch.amp, ch.delta),
  curveS3: genPsdPath(ch.peak * 7 + 2, ch.peak * 1.02, ch.amp * 0.75, ch.delta * 1.1),
  semPath: genPsdSem(ch.peak * 7, ch.peak, ch.amp * 0.65, ch.delta),
}))

const bands = [
  { name: 'δ', color: '#3B82F6', active: false },
  { name: 'θ', color: '#10B981', active: false },
  { name: 'α', color: '#F59E0B', active: true },
  { name: 'β', color: '#F97316', active: false },
  { name: 'γ', color: '#EF4444', active: false },
]
</script>

<style scoped>
:deep(.page) { padding: 0; }
.psd-panels {
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: 1fr 1fr;
}
@media (max-width: 1300px) {
  .psd-panels { grid-template-columns: repeat(2, 1fr); grid-template-rows: repeat(3, 1fr); }
}
.band-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  font-size: 11px;
  border-radius: var(--r-pill);
  border: 1px solid var(--c-border);
  background: var(--c-surface);
  color: var(--c-text-2);
  cursor: pointer;
}
.band-pill.active {
  background: rgba(245, 158, 11, .15);
  border-color: var(--c-warning);
  color: var(--c-warning);
  font-weight: 600;
}
.band-pill .bdot { width: 8px; height: 8px; border-radius: 50%; }

.topomap {
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 35%, rgba(245, 158, 11, .6), transparent 40%),
    radial-gradient(circle at 50% 65%, rgba(46, 107, 255, .4), transparent 35%),
    radial-gradient(circle at 50% 50%, #FEF3D7 0%, #F7F9FC 70%);
  border: 1.5px solid var(--c-border-strong);
  margin: 0 auto;
  width: 120px;
  height: 120px;
}
.iaf-alert {
  background: rgba(16, 185, 129, .08);
  border: 1px solid rgba(16, 185, 129, .3);
  border-radius: var(--r);
  padding: 8px 10px;
}
.iaf-alert strong { color: var(--c-success); }
.iaf-sub { font-size: 11px; color: var(--c-text-2); margin-top: 2px; }

/* ── live 模式（接真实 PSD 结果）── */
.psd-live-card {
  margin: 12px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  overflow: hidden;
}
.psd-live-card__head {
  padding: 12px 16px;
  background: var(--c-bg-soft);
  border-bottom: 1px solid var(--c-border);
}
.psd-live-card__head h2 { margin: 0; font-size: 14px; }
.psd-live-card__head p { margin: 4px 0 0; color: var(--c-text-2); font-size: 12px; }
.psd-live-plot { padding: 12px; position: relative; }
.psd-svg { width: 100%; max-width: 100%; height: auto; }
.psd-state {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 14px;
  font-size: 12px;
  border-radius: var(--r-pill);
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  color: var(--c-text-2);
}
.psd-state--err { color: var(--c-danger, #d43f34); border-color: var(--c-danger, #d43f34); }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.stat-card {
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
  padding: 8px 10px;
  text-align: center;
}
.stat-label { font-size: 10px; color: var(--c-text-3); }
.stat-value { font-family: var(--ff-mono); font-size: 15px; font-weight: 600; margin-top: 2px; color: var(--c-text); }
.stat-value .unit { font-size: 10px; color: var(--c-text-3); margin-left: 2px; }
</style>
