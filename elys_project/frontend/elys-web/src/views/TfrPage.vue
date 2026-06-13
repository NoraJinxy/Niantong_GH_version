<template>
  <WorkbenchShell active-key="view-tfr" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div v-if="!isLive" class="sel-section">
          <h4>数据集 <span class="count">3</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name">stroke-mi-rehab</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-01 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">sub-02 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-03 · ses-01</span></div>
          </div>
        </div>
        <div v-else class="sel-section">
          <h4>结果</h4>
          <div class="result-meta">
            <div class="result-meta__row"><span class="k">条件</span><span class="v">{{ live?.condition || '—' }}</span></div>
            <div class="result-meta__row"><span class="k">试次</span><span class="v">{{ live?.nave ?? '—' }}</span></div>
            <div class="result-meta__row"><span class="k">通道</span><span class="v">{{ live?.n_channels_total ?? '—' }}</span></div>
            <div class="result-meta__row"><span class="k">方法</span><span class="v">{{ live?.method || 'morlet' }}</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>通道</h4>
          <div style="display: flex; gap: 4px; flex-wrap: wrap">
            <span
              v-for="ch in channelChips"
              :key="ch"
              class="ch-tag"
              :class="{ 'is-on': ch === selectedChannel }"
              @click="selectChannel(ch)"
            >
              {{ ch }}
            </span>
            <span v-if="isLive && channelOptions.length > channelChips.length" class="ch-more">
              +{{ channelOptions.length - channelChips.length }}
            </span>
          </div>
        </div>

        <div class="sel-section">
          <h4>色标</h4>
          <select v-model="cmap" class="select input--sm" style="width: 100%; font-family: var(--ff-mono)">
            <option value="rdbu">RdBu（ERSP 经典）</option>
            <option value="viridis">Viridis</option>
            <option value="hot">Hot</option>
          </select>
        </div>

        <div class="sel-section">
          <h4>归一化</h4>
          <div v-if="isLive" class="norm-fixed text-mono">{{ baselineDesc(live?.baseline_mode) }}</div>
          <template v-else>
            <label class="checkbox-row"><input type="radio" name="norm" checked />dB（相对基线）</label>
            <label class="checkbox-row"><input type="radio" name="norm" />Z-score</label>
            <label class="checkbox-row"><input type="radio" name="norm" />% 变化</label>
          </template>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="tfr">
          <template #meta>
            <span class="text-mono" style="font-size: 11px; color: var(--c-text-3)">
              {{ metaLine }}
            </span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">色阶 ({{ unitLabel }})</span>
          <input v-model="zmin" class="input input--sm" style="width: 56px; font-family: var(--ff-mono); text-align: center" />
          <span style="color: var(--c-text-3)">→</span>
          <input v-model="zmax" class="input input--sm" style="width: 56px; font-family: var(--ff-mono); text-align: center" />
          <div class="divider-h"></div>
          <span class="tool-lbl">方法</span>
          <select :disabled="isLive"><option>Morlet Wavelet</option><option>STFT</option><option>Hilbert</option></select>
          <div class="divider-h"></div>
          <span class="tool-lbl">通道</span>
          <select :value="selectedChannel" @change="selectChannel(($event.target as HTMLSelectElement).value)">
            <option v-for="ch in channelOptions" :key="ch" :value="ch">{{ ch }}</option>
          </select>
          <div style="flex: 1"></div>
          <button class="btn btn--sm" @click="resetScale">↻ 重置</button>
          <button class="btn btn--sm btn--primary" @click="refresh">▶ 刷新</button>
        </div>

        <div class="tfr-card">
          <div class="tfr-card__head">
            <div>
              <h2>{{ cardTitle }}</h2>
              <p>{{ cardSubtitle }}</p>
            </div>
            <div class="row gap-2">
              <span class="badge">高密度时频</span>
              <span class="badge">悬停 / 缩放</span>
            </div>
          </div>

          <div class="tfr-plot">
            <div v-if="liveLoading" class="tfr-state">正在加载时频数据…</div>
            <div v-else-if="liveError" class="tfr-state tfr-state--err">{{ liveError }}</div>
            <svg viewBox="0 0 760 360" preserveAspectRatio="xMidYMid meet" class="tfr-svg">
              <rect width="760" height="360" fill="#fff" />
              <g transform="translate(60, 20)">
                <g v-for="row in heatmap" :key="row.iF">
                  <rect
                    v-for="cell in row.cells"
                    :key="cell.iT"
                    :x="cell.x"
                    :y="cell.y"
                    :width="cell.w"
                    :height="cell.h"
                    :fill="cell.fill"
                  />
                </g>
                <template v-if="zeroX !== null">
                  <line :x1="zeroX" y1="0" :x2="zeroX" y2="300" stroke="#d43f34" stroke-width="2" stroke-dasharray="3 3" />
                  <text :x="zeroX + 4" y="14" fill="#d43f34" font-size="10" font-family="monospace">stimulus 0 s</text>
                </template>
                <line
                  v-for="band in bandLines"
                  :key="band.name"
                  x1="0"
                  :y1="band.y"
                  x2="600"
                  :y2="band.y"
                  stroke="#7c8ea0"
                  stroke-width="0.6"
                  stroke-dasharray="3 3"
                  opacity="0.5"
                />
                <text
                  v-for="band in bandLines"
                  :key="`l-${band.name}`"
                  x="608"
                  :y="band.y + 4"
                  font-size="10"
                  fill="#577190"
                  font-family="monospace"
                >
                  {{ band.name }}
                </text>
                <line x1="0" y1="0" x2="0" y2="300" stroke="#bbccdd" />
                <line x1="0" y1="300" x2="600" y2="300" stroke="#bbccdd" />
                <text
                  v-for="tick in freqAxis"
                  :key="`f-${tick.y}`"
                  x="-8"
                  :y="tick.y"
                  font-size="10"
                  text-anchor="end"
                  fill="#577190"
                  font-family="monospace"
                >
                  {{ tick.label }}
                </text>
                <text x="-32" y="160" font-size="11" fill="#5B6B85" transform="rotate(-90 -32 160)">频率 Hz</text>
                <text
                  v-for="tick in timeAxis"
                  :key="`t-${tick.x}`"
                  :x="tick.x"
                  y="320"
                  font-size="10"
                  fill="#577190"
                  font-family="monospace"
                  :text-anchor="tick.anchor"
                >
                  {{ tick.label }}
                </text>
                <text x="290" y="340" font-size="11" fill="#5B6B85">时间 (s)</text>
              </g>

              <g transform="translate(680, 20)">
                <defs>
                  <linearGradient id="cmapGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stop-color="#fff5d6" />
                    <stop offset="0.5" stop-color="#fac874" />
                    <stop offset="1" stop-color="#7c1d6f" />
                  </linearGradient>
                </defs>
                <rect width="14" height="300" fill="url(#cmapGrad)" stroke="#bbccdd" />
                <text x="20" y="6" font-size="10" fill="#5B6B85" font-family="monospace">{{ colorbar.top }}</text>
                <text x="20" y="158" font-size="10" fill="#5B6B85" font-family="monospace">{{ colorbar.mid }}</text>
                <text x="20" y="304" font-size="10" fill="#5B6B85" font-family="monospace">{{ colorbar.bottom }}</text>
              </g>
            </svg>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>频带功率变化</h4>
          <div class="stat-grid">
            <div class="stat-card">
              <div class="stat-label">α (8–12 Hz)</div>
              <div class="stat-value">{{ bandStats.alpha.toFixed(2) }}<span class="unit"> {{ unitLabel }}</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">β (12–30 Hz)</div>
              <div class="stat-value">{{ bandStats.beta.toFixed(2) }}<span class="unit"> {{ unitLabel }}</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">θ (4–8 Hz)</div>
              <div class="stat-value">{{ bandStats.theta.toFixed(2) }}<span class="unit"> {{ unitLabel }}</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">γ (30–50 Hz)</div>
              <div class="stat-value">{{ bandStats.gamma.toFixed(2) }}<span class="unit"> {{ unitLabel }}</span></div>
            </div>
          </div>

          <div class="stat-card" style="text-align: left; padding: 10px 14px; margin-top: 8px">
            <div class="stat-label">峰值 ERD</div>
            <div class="stat-value" style="font-size: 14px; margin-top: 2px">
              {{ bandStats.peak.toFixed(2) }}<span class="unit"> {{ unitLabel }} @ {{ bandStats.peakT }} ms</span>
            </div>
          </div>

          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px">
            <span v-for="b in ['δ 1–4', 'θ 4–8', 'α 8–12', 'β 12–30', 'γ 30–50']" :key="b" class="band-tag-on">{{ b }}</span>
          </div>
          <div style="font-size: 10px; color: var(--c-text-3); margin-top: 6px; text-align: center">
            {{ isLive ? '刺激后窗口均值 (t ≥ 0)' : '基线 [−0.5, 0] s mean' }}
          </div>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <RouterLink class="btn" to="/figures">发送到作图模块</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计模块</RouterLink>
          <button class="btn">导出 (.npy)</button>
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
import type { StudyOutputTfr } from '@/types'

// ── 双模式：路由带 study_output_id+studyId → 拉真实时频结果；否则保留静态设计稿 ──
const route = useRoute()
const studyId = computed(() => String(route.query.studyId || route.query.study_id || ''))
const outputId = computed(() => String(route.query.study_output_id || ''))
const isLive = computed(() => Boolean(studyId.value && outputId.value))

const live = ref<StudyOutputTfr | null>(null)
const liveLoading = ref(false)
const liveError = ref('')

const selectedChannel = ref('Cz')
const cmap = ref<'rdbu' | 'viridis' | 'hot'>('rdbu')
const zmin = ref('-3')
const zmax = ref('+3')

async function loadTfr(channel?: string) {
  if (!isLive.value) return
  liveLoading.value = true
  liveError.value = ''
  try {
    const res = await pipelineApi.getStudyOutputTfr(
      studyId.value,
      outputId.value,
      channel ? { channel } : {},
    )
    live.value = res.data
    selectedChannel.value = res.data.channel
    const z = Number(res.data.zmax) || 1
    zmax.value = `+${roundZ(z)}`
    zmin.value = `-${roundZ(z)}`
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: { message?: string } } } })?.response?.data?.detail
    liveError.value = detail?.message || (error as Error)?.message || '时频数据加载失败'
  } finally {
    liveLoading.value = false
  }
}

onMounted(() => {
  if (isLive.value) loadTfr()
})

function selectChannel(ch: string) {
  if (!ch) return
  selectedChannel.value = ch
  if (isLive.value) loadTfr(ch)
}

function refresh() {
  if (isLive.value) loadTfr(selectedChannel.value)
}

function resetScale() {
  const z = isLive.value && live.value ? Number(live.value.zmax) || 1 : 3
  zmax.value = `+${roundZ(z)}`
  zmin.value = `-${roundZ(z)}`
}

// ── 通道选项 ──
const DEMO_CHANNELS = ['Fz', 'Cz', 'Pz', 'Oz']
const channelOptions = computed(() => (isLive.value && live.value ? live.value.ch_names_all : DEMO_CHANNELS))
const channelChips = computed(() => channelOptions.value.slice(0, 32))

// ── 色彩映射：把展示值(已含单位)映射到颜色，scale = 当前色阶上界 ──
function pseudoRand(seed: number) {
  const x = Math.sin(seed * 13.4567) * 43758.5453
  return x - Math.floor(x)
}

function ersfColor(value: number, mode: 'rdbu' | 'viridis' | 'hot', scale: number) {
  const s = scale || 1
  const t = Math.max(-s, Math.min(s, value)) / s
  if (mode === 'rdbu') {
    if (t < 0) {
      const k = -t
      return `rgb(${Math.round(46 + (255 - 46) * (1 - k))}, ${Math.round(107 + (255 - 107) * (1 - k))}, ${Math.round(255)})`
    }
    return `rgb(${Math.round(255)}, ${Math.round(255 - 255 * t * 0.7)}, ${Math.round(255 - 255 * t * 0.9)})`
  }
  if (mode === 'viridis') {
    const k = (t + 1) / 2
    return `rgb(${Math.round(68 + 188 * k)}, ${Math.round(1 + 230 * k)}, ${Math.round(84 + 138 * (1 - k))})`
  }
  const k = (t + 1) / 2
  return `rgb(${Math.round(255 * k)}, ${Math.round(80 * k)}, ${Math.round(40 * (1 - k))})`
}

// ── 演示用伪时频矩阵(无真实结果时) ──
const N_T = 60
const N_F = 40
const CHANNEL_PROFILES: Record<string, { alpha: number; beta: number; theta: number; gamma: number }> = {
  Fz: { alpha: 0.2, beta: 0.5, theta: 0.85, gamma: 0.3 },
  Cz: { alpha: 0.5, beta: 0.9, theta: 0.3, gamma: 0.5 },
  Pz: { alpha: 0.6, beta: 0.7, theta: 0.5, gamma: 0.4 },
  Oz: { alpha: 1.3, beta: 0.2, theta: 0.2, gamma: 0.25 },
}

const erspDemo = computed(() => {
  const prof = CHANNEL_PROFILES[selectedChannel.value] || CHANNEL_PROFILES.Cz
  const result: number[][] = []
  for (let iF = 0; iF < N_F; iF++) {
    const freq = 1 + (iF / (N_F - 1)) * 49
    const row: number[] = []
    for (let iT = 0; iT < N_T; iT++) {
      const ts = -0.5 + (iT / (N_T - 1)) * 2
      let v = 0
      if (freq >= 7 && freq <= 13) {
        v -= prof.alpha * 2.5 * Math.exp(-Math.pow((ts - 0.45) / 0.28, 2)) * Math.exp(-Math.pow((freq - 10) / 2.5, 2))
      }
      if (freq >= 13 && freq <= 30) {
        v += prof.beta * 2.5 * Math.exp(-Math.pow((ts - 0.28) / 0.2, 2)) * Math.exp(-Math.pow((freq - 20) / 6, 2))
      }
      if (freq >= 4 && freq <= 8) {
        v += prof.theta * 2 * Math.exp(-Math.pow((ts - 0.22) / 0.18, 2))
      }
      if (freq >= 30 && freq <= 48) {
        v += prof.gamma * 1.8 * Math.exp(-Math.pow((ts - 0.16) / 0.09, 2))
      }
      if (ts < 0) v = (pseudoRand(iF * 31 + iT * 7) - 0.5) * 0.6
      v += (pseudoRand(iF * 17 + iT * 13) - 0.5) * 0.4
      row.push(v)
    }
    result.push(row)
  }
  return result
})

// ersp[iF][iT]，iF 从低频到高频；live.power 同向（freqs 升序）
const ersp = computed<number[][]>(() => {
  if (isLive.value) return live.value ? live.value.power : []
  return erspDemo.value
})

const colorScale = computed(() => Math.abs(Number(zmax.value)) || 3)

const heatmap = computed(() => {
  const matrix = ersp.value
  const rows = matrix.length
  if (!rows) return [] as Array<{ iF: number; cells: Array<{ iT: number; x: number; y: number; w: number; h: number; fill: string }> }>
  const cols = matrix[0]?.length || 1
  const cellW = 600 / cols
  const cellH = 300 / rows
  const scale = colorScale.value
  return matrix.map((row, iF) => ({
    iF,
    cells: row.map((v, iT) => ({
      iT,
      x: iT * cellW,
      y: 300 - (iF + 1) * cellH,
      w: cellW + 0.5,
      h: cellH + 0.5,
      fill: ersfColor(v, cmap.value, scale),
    })),
  }))
})

// ── 频率范围 / 时间范围（live 用真实，demo 用 1–50 Hz / −0.5–1.5 s） ──
const freqRange = computed(() => {
  if (isLive.value && live.value) return { fmin: live.value.fmin ?? 1, fmax: live.value.fmax ?? 50 }
  return { fmin: 1, fmax: 50 }
})
const timeRange = computed(() => {
  if (isLive.value && live.value) return { tmin: live.value.tmin ?? -0.5, tmax: live.value.tmax ?? 1.5 }
  return { tmin: -0.5, tmax: 1.5 }
})

const zeroX = computed<number | null>(() => {
  const { tmin, tmax } = timeRange.value
  if (tmax <= tmin || 0 < tmin || 0 > tmax) return null
  return ((0 - tmin) / (tmax - tmin)) * 600
})

const bandLines = computed(() => {
  const { fmin, fmax } = freqRange.value
  const span = fmax - fmin || 1
  const freqToY = (f: number) => 300 - ((f - fmin) / span) * 300
  return [
    { name: 'δ', f: 4 },
    { name: 'θ', f: 8 },
    { name: 'α', f: 13 },
    { name: 'β', f: 30 },
  ]
    .filter((b) => b.f > fmin && b.f < fmax)
    .map((b) => ({ name: b.name, y: freqToY(b.f) }))
})

const freqAxis = computed(() => {
  const { fmin, fmax } = freqRange.value
  return [
    { y: 0, label: fmtFreq(fmax) },
    { y: 150, label: fmtFreq((fmin + fmax) / 2) },
    { y: 300, label: fmtFreq(fmin) },
  ]
})

const timeAxis = computed(() => {
  const { tmin, tmax } = timeRange.value
  return [
    { x: 0, anchor: 'start', label: fmtTime(tmin) },
    { x: 300, anchor: 'middle', label: fmtTime((tmin + tmax) / 2) },
    { x: 600, anchor: 'end', label: fmtTime(tmax) },
  ]
})

const colorbar = computed(() => {
  const z = roundZ(colorScale.value)
  const u = unitLabel.value
  return { top: `+${z} ${u}`, mid: '0', bottom: `−${z} ${u}` }
})

const unitLabel = computed(() => (isLive.value && live.value ? live.value.unit : 'dB'))

const bandStatsDemo = computed(() => {
  const z = erspDemo.value
  function mean(lo: number, hi: number) {
    let sum = 0,
      count = 0
    for (let iF = 0; iF < N_F; iF++) {
      const freq = 1 + (iF / (N_F - 1)) * 49
      if (freq < lo || freq > hi) continue
      for (let iT = 0; iT < N_T; iT++) {
        const ts = -0.5 + (iT / (N_T - 1)) * 2
        if (ts < 0.1 || ts > 0.8) continue
        sum += z[iF][iT]
        count++
      }
    }
    return count ? sum / count : 0
  }
  let peak = Infinity,
    peakT = 0
  for (let iF = 0; iF < N_F; iF++) {
    for (let iT = 0; iT < N_T; iT++) {
      const ts = -0.5 + (iT / (N_T - 1)) * 2
      if (ts < 0.1 || ts > 0.8) continue
      if (z[iF][iT] < peak) {
        peak = z[iF][iT]
        peakT = ts
      }
    }
  }
  return {
    alpha: mean(8, 12),
    beta: mean(12, 30),
    theta: mean(4, 8),
    gamma: mean(30, 50),
    peak: Number.isFinite(peak) ? peak : 0,
    peakT: Math.round(peakT * 1000),
  }
})

const bandStats = computed(() => {
  if (!(isLive.value && live.value)) return bandStatsDemo.value
  const data = live.value
  const band = (name: string) => data.bands.find((b) => b.name === name)?.value ?? 0
  let peak = Infinity
  let peakT = 0
  let found = false
  for (let iF = 0; iF < data.power.length; iF++) {
    const row = data.power[iF]
    for (let iT = 0; iT < row.length; iT++) {
      const t = data.times[iT]
      if (t == null || t < 0) continue
      if (row[iT] < peak) {
        peak = row[iT]
        peakT = t
        found = true
      }
    }
  }
  return {
    alpha: band('alpha'),
    beta: band('beta'),
    theta: band('theta'),
    gamma: band('gamma'),
    peak: found ? peak : 0,
    peakT: Math.round(peakT * 1000),
  }
})

// ── 标题 / 元信息 ──
const metaLine = computed(() => {
  if (isLive.value && live.value) {
    return `${selectedChannel.value} · ${live.value.condition || '—'} · ${Math.round(live.value.sfreq)} Hz`
  }
  return `${selectedChannel.value} · Left MI · 1000 Hz`
})

const cardTitle = computed(() => {
  const cond = isLive.value && live.value ? live.value.condition || 'ERSP' : 'ERSP'
  return `时频分析 · ${selectedChannel.value} · ${cond}`
})

const cardSubtitle = computed(() => {
  if (isLive.value && live.value) {
    const l = live.value
    return `${l.method || 'morlet'} · ${fmtFreq(l.fmin)}–${fmtFreq(l.fmax)} Hz · ${l.nave} trials · ${baselineDesc(l.baseline_mode)}`
  }
  return 'Morlet Wavelet · 1–50 Hz · 基线 [−0.5, 0] s · dB re. baseline'
})

function baselineDesc(mode?: string | null) {
  const map: Record<string, string> = {
    logratio: 'dB re. baseline',
    percent: '% change re. baseline',
    zscore: 'z-score re. baseline',
    ratio: 'ratio re. baseline',
    mean: 'mean-subtract baseline',
    none: '无基线校正',
  }
  return map[String(mode || '')] || 'dB re. baseline'
}

function fmtFreq(value: number | null) {
  if (value == null) return '—'
  return Math.abs(value) >= 10 ? String(Math.round(value)) : String(Math.round(value * 10) / 10)
}

function fmtTime(value: number | null) {
  if (value == null) return '—'
  return String(Math.round(value * 100) / 100)
}

function roundZ(value: number) {
  return Math.round(value * 100) / 100
}
</script>

<style scoped>
:deep(.page) { padding: 0; }
.tfr-card {
  margin: 12px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  height: calc(100% - 24px);
  display: flex;
  flex-direction: column;
}
.tfr-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--c-bg-soft);
  border-bottom: 1px solid var(--c-border);
}
.tfr-card__head h2 { margin: 0; font-size: 14px; }
.tfr-card__head p { margin: 4px 0 0; color: var(--c-text-2); font-size: 12px; }
.tfr-plot { flex: 1; padding: 12px; overflow: auto; position: relative; }
.tfr-svg { width: 100%; max-width: 100%; height: auto; }
.tfr-state {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  padding: 6px 14px;
  font-size: 12px;
  border-radius: var(--r-pill);
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  color: var(--c-text-2);
}
.tfr-state--err { color: var(--c-danger, #d43f34); border-color: var(--c-danger, #d43f34); }

.result-meta { display: flex; flex-direction: column; gap: 4px; }
.result-meta__row { display: flex; justify-content: space-between; font-size: 12px; }
.result-meta__row .k { color: var(--c-text-3); }
.result-meta__row .v { font-family: var(--ff-mono); color: var(--c-text); }
.norm-fixed { font-size: 11px; color: var(--c-text-2); }
.ch-more { font-size: 10px; color: var(--c-text-3); align-self: center; }

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.stat-card {
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
  padding: 8px 10px;
  text-align: center;
}
.stat-label {
  font-size: 10px;
  color: var(--c-text-3);
  letter-spacing: .04em;
}
.stat-value {
  font-family: var(--ff-mono);
  font-size: 16px;
  font-weight: 600;
  margin-top: 2px;
  color: var(--c-text);
}
.stat-value .unit { font-size: 10px; color: var(--c-text-3); margin-left: 2px; }
.band-tag-on {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 10px;
  border-radius: var(--r-pill);
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-family: var(--ff-mono);
}
.ch-tag {
  cursor: pointer;
}
.ch-tag.is-on {
  background: var(--c-primary);
  color: #fff;
  border-color: var(--c-primary);
}
</style>
