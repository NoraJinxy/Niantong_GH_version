<template>
  <WorkbenchShell active-key="view-tfr" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">3</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name">stroke-mi-rehab</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-01 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">sub-02 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-03 · ses-01</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>通道</h4>
          <div style="display: flex; gap: 4px; flex-wrap: wrap">
            <span
              v-for="ch in ['Fz', 'Cz', 'Pz', 'Oz']"
              :key="ch"
              class="ch-tag"
              :class="{ 'is-on': ch === selectedChannel }"
              @click="selectedChannel = ch"
            >
              {{ ch }}
            </span>
          </div>
        </div>

        <div class="sel-section">
          <h4>条件</h4>
          <div style="display: flex; gap: 4px; flex-wrap: wrap">
            <span class="cond-pill active s1"><span class="dot"></span>Left MI</span>
            <span class="cond-pill"><span class="dot"></span>Right MI</span>
            <span class="cond-pill"><span class="dot"></span>Rest</span>
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
          <label class="checkbox-row"><input type="radio" name="norm" checked />dB（相对基线）</label>
          <label class="checkbox-row"><input type="radio" name="norm" />Z-score</label>
          <label class="checkbox-row"><input type="radio" name="norm" />% 变化</label>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="tfr">
          <template #meta>
            <span class="text-mono" style="font-size: 11px; color: var(--c-text-3)">
              {{ selectedChannel }} · Left MI · 1000 Hz
            </span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">色阶 (dB)</span>
          <input v-model="zmin" class="input input--sm" style="width: 56px; font-family: var(--ff-mono); text-align: center" />
          <span style="color: var(--c-text-3)">→</span>
          <input v-model="zmax" class="input input--sm" style="width: 56px; font-family: var(--ff-mono); text-align: center" />
          <div class="divider-h"></div>
          <span class="tool-lbl">方法</span>
          <select><option>Morlet Wavelet</option><option>STFT</option><option>Hilbert</option></select>
          <div class="divider-h"></div>
          <span class="tool-lbl">通道</span>
          <select v-model="selectedChannel">
            <option>Cz</option><option>Fz</option><option>Pz</option><option>Oz</option>
          </select>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">↻ 重置</button>
          <button class="btn btn--sm btn--primary">▶ 刷新</button>
        </div>

        <div class="tfr-card">
          <div class="tfr-card__head">
            <div>
              <h2>时频分析 · {{ selectedChannel }} · ERSP</h2>
              <p>Morlet Wavelet · 1–50 Hz · 基线 [−0.5, 0] s · dB re. baseline</p>
            </div>
            <div class="row gap-2">
              <span class="badge">高密度时频</span>
              <span class="badge">悬停 / 缩放</span>
            </div>
          </div>

          <div class="tfr-plot">
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
                <line x1="200" y1="0" x2="200" y2="300" stroke="#d43f34" stroke-width="2" stroke-dasharray="3 3" />
                <text x="204" y="14" fill="#d43f34" font-size="10" font-family="monospace">stimulus 0 s</text>
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
                <text x="-8" y="0" font-size="10" text-anchor="end" fill="#577190" font-family="monospace">50</text>
                <text x="-8" y="150" font-size="10" text-anchor="end" fill="#577190" font-family="monospace">25</text>
                <text x="-8" y="300" font-size="10" text-anchor="end" fill="#577190" font-family="monospace">1</text>
                <text x="-32" y="160" font-size="11" fill="#5B6B85" transform="rotate(-90 -32 160)">频率 Hz</text>
                <text x="0" y="320" font-size="10" fill="#577190" font-family="monospace">−0.5</text>
                <text x="300" y="320" font-size="10" fill="#577190" font-family="monospace" text-anchor="middle">0.5</text>
                <text x="600" y="320" font-size="10" fill="#577190" font-family="monospace" text-anchor="end">1.5</text>
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
                <text x="20" y="6" font-size="10" fill="#5B6B85" font-family="monospace">+3 dB</text>
                <text x="20" y="158" font-size="10" fill="#5B6B85" font-family="monospace">0</text>
                <text x="20" y="304" font-size="10" fill="#5B6B85" font-family="monospace">−3 dB</text>
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
              <div class="stat-value">{{ bandStats.alpha.toFixed(2) }}<span class="unit"> dB</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">β (12–30 Hz)</div>
              <div class="stat-value">{{ bandStats.beta.toFixed(2) }}<span class="unit"> dB</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">θ (4–8 Hz)</div>
              <div class="stat-value">{{ bandStats.theta.toFixed(2) }}<span class="unit"> dB</span></div>
            </div>
            <div class="stat-card">
              <div class="stat-label">γ (30–50 Hz)</div>
              <div class="stat-value">{{ bandStats.gamma.toFixed(2) }}<span class="unit"> dB</span></div>
            </div>
          </div>

          <div class="stat-card" style="text-align: left; padding: 10px 14px; margin-top: 8px">
            <div class="stat-label">峰值 ERD</div>
            <div class="stat-value" style="font-size: 14px; margin-top: 2px">
              {{ bandStats.peak.toFixed(2) }}<span class="unit"> dB @ {{ bandStats.peakT }} ms</span>
            </div>
          </div>

          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px">
            <span v-for="b in ['δ 1–4', 'θ 4–8', 'α 8–12', 'β 12–30', 'γ 30–50']" :key="b" class="band-tag-on">{{ b }}</span>
          </div>
          <div style="font-size: 10px; color: var(--c-text-3); margin-top: 6px; text-align: center">
            基线 [−0.5, 0] s mean
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
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'

const selectedChannel = ref('Cz')
const cmap = ref<'rdbu' | 'viridis' | 'hot'>('rdbu')
const zmin = ref('-3')
const zmax = ref('+3')

const CHANNEL_PROFILES: Record<string, { alpha: number; beta: number; theta: number; gamma: number }> = {
  Fz: { alpha: 0.2, beta: 0.5, theta: 0.85, gamma: 0.3 },
  Cz: { alpha: 0.5, beta: 0.9, theta: 0.3, gamma: 0.5 },
  Pz: { alpha: 0.6, beta: 0.7, theta: 0.5, gamma: 0.4 },
  Oz: { alpha: 1.3, beta: 0.2, theta: 0.2, gamma: 0.25 },
}

function pseudoRand(seed: number) {
  const x = Math.sin(seed * 13.4567) * 43758.5453
  return x - Math.floor(x)
}

function ersfColor(db: number, mode: 'rdbu' | 'viridis' | 'hot') {
  const t = Math.max(-3, Math.min(3, db)) / 3
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

const N_T = 60
const N_F = 40

const ersp = computed(() => {
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

const heatmap = computed(() => {
  const cellW = 600 / N_T
  const cellH = 300 / N_F
  return ersp.value.map((row, iF) => ({
    iF,
    cells: row.map((v, iT) => ({
      iT,
      x: iT * cellW,
      y: 300 - (iF + 1) * cellH,
      w: cellW + 0.5,
      h: cellH + 0.5,
      fill: ersfColor(v, cmap.value),
    })),
  }))
})

const bandLines = computed(() => {
  const freqToY = (f: number) => 300 - ((f - 1) / 49) * 300
  return [
    { name: 'δ', y: freqToY(4) },
    { name: 'θ', y: freqToY(8) },
    { name: 'α', y: freqToY(13) },
    { name: 'β', y: freqToY(30) },
  ]
})

const bandStats = computed(() => {
  const z = ersp.value
  function mean(lo: number, hi: number) {
    let sum = 0, count = 0
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
  let peak = Infinity, peakT = 0
  for (let iF = 0; iF < N_F; iF++) {
    for (let iT = 0; iT < N_T; iT++) {
      const ts = -0.5 + (iT / (N_T - 1)) * 2
      if (ts < 0.1 || ts > 0.8) continue
      if (z[iF][iT] < peak) { peak = z[iF][iT]; peakT = ts }
    }
  }
  return {
    alpha: mean(8, 12),
    beta: mean(12, 30),
    theta: mean(4, 8),
    gamma: mean(30, 50),
    peak,
    peakT: Math.round(peakT * 1000),
  }
})
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
.tfr-plot { flex: 1; padding: 12px; overflow: auto; }
.tfr-svg { width: 100%; max-width: 100%; height: auto; }

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
