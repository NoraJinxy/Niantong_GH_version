<template>
  <WorkbenchShell active-key="view-erp" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">3</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node">
              <svg class="toggle-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9" /></svg>
              <input type="checkbox" checked />
              <span class="name" style="font-weight: 500">stroke-mi-rehab</span>
            </div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-01 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-01 · ses-02</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">sub-02 · ses-01</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-03 · ses-01</span></div>
            <div class="ck-node indent-1"><span style="font-size: 11px; color: var(--c-text-3); padding-left: 18px">… +20 个</span></div>
            <div class="ck-node">
              <svg class="toggle-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
              <input type="checkbox" />
              <span class="name" style="font-weight: 500">p300-bci-spelling</span>
            </div>
            <div class="ck-node">
              <svg class="toggle-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
              <input type="checkbox" />
              <span class="name" style="font-weight: 500">resting-alpha-long</span>
            </div>
          </div>
        </div>

        <div class="sel-section">
          <h4>条件 / 事件 <span class="count">2</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span class="cond-pill active s1"><span class="dot"></span>S1 (Left MI)</span>
            <span class="cond-pill active s2"><span class="dot"></span>S2 (Right MI)</span>
            <span class="cond-pill"><span class="dot"></span>R1</span>
            <span class="cond-pill"><span class="dot"></span>R2</span>
          </div>
        </div>

        <div class="sel-section">
          <h4>通道 <span class="count">5</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span v-for="ch in channels" :key="ch.id" class="ch-tag">{{ ch.label }}</span>
          </div>
          <button class="btn btn--sm" style="margin-top: 8px; width: 100%; justify-content: center; height: 26px; font-size: 11px">
            + 添加通道
          </button>
        </div>

        <div class="sel-section">
          <h4>试次 (Epochs)</h4>
          <div style="display: flex; gap: 6px; align-items: center; font-size: 11px; color: var(--c-text-2)">
            范围
            <input class="input input--sm" value="1-64" style="width: 60px; font-family: var(--ff-mono)" />
            / 共 <span style="font-family: var(--ff-mono); color: var(--c-primary); font-weight: 600">128</span>
          </div>
          <label class="checkbox-row" style="margin-top: 6px"><input type="checkbox" checked />仅显示有效试次</label>
          <label class="checkbox-row"><input type="checkbox" />显示拒绝试次（灰色）</label>
        </div>

        <div class="sel-section">
          <h4>布局</h4>
          <div class="layout-grid">
            <div class="layout-btn active">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="6" height="6" /><rect x="11" y="3" width="6" height="6" />
                <rect x="3" y="11" width="6" height="6" /><rect x="11" y="11" width="6" height="6" />
              </svg>
              <span class="lbl">网格</span>
            </div>
            <div class="layout-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="3" y1="12" x2="21" y2="6" /><line x1="3" y1="14" x2="21" y2="10" />
                <line x1="3" y1="16" x2="21" y2="14" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
              <span class="lbl">蝶形</span>
            </div>
            <div class="layout-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /></svg>
              <span class="lbl">头分布</span>
            </div>
            <div class="layout-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
              <span class="lbl">堆叠</span>
            </div>
          </div>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="erp">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">3 数据集 · 5 通道 · 2 条件 · 128 试次</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <button class="btn btn--sm">‹</button>
          <span style="font-family: var(--ff-mono); font-size: 12px; min-width: 110px; text-align: center; color: var(--c-text)">−200 ms / 800 ms</span>
          <button class="btn btn--sm">›</button>
          <div class="divider-h"></div>
          <span class="tool-lbl">时窗</span>
          <select><option>±100 ms</option><option selected>−200 ~ 800 ms</option><option>0 ~ 1000 ms</option></select>
          <span class="tool-lbl">Y 轴</span>
          <select><option>自动</option><option selected>±20 μV</option><option>±50 μV</option><option>±100 μV</option></select>
          <div class="divider-h"></div>
          <label class="checkbox-row" style="font-size: 11px"><input type="checkbox" checked />显示单试次</label>
          <label class="checkbox-row" style="font-size: 11px; margin-left: 6px"><input type="checkbox" checked />平均</label>
          <label class="checkbox-row" style="font-size: 11px; margin-left: 6px"><input type="checkbox" />置信区间</label>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">+ 添加面板</button>
          <button class="btn btn--sm">导出</button>
        </div>

        <div class="region-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" /></svg>
          <span class="label">已选区间：300 – 500 ms</span>
          <span class="hint">右侧面板显示该区间统计</span>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">清除</button>
        </div>

        <div class="panel-grid erp-panels">
          <div v-for="ch in channels" :key="ch.id" class="obs-panel">
            <div class="panel-head">
              <span class="ch-tag-solid" :style="{ background: ch.color }">{{ ch.label }}</span>
              <span class="title">{{ ch.subtitle }}<span v-if="ch.star" style="color: var(--c-success)"> · ★ 最大</span></span>
              <span class="stats">peak {{ ch.amp }} μV @ {{ ch.peak }} ms</span>
            </div>
            <div class="panel-body">
              <svg viewBox="0 0 400 200" preserveAspectRatio="none">
                <rect width="400" height="200" fill="#fff" />
                <line x1="0" y1="100" x2="400" y2="100" stroke="#E5E9F2" stroke-dasharray="3 3" />
                <line x1="80" y1="0" x2="80" y2="200" stroke="#EF4444" stroke-width="1" stroke-dasharray="3 3" />
                <text x="84" y="14" fill="#EF4444" font-size="9" font-family="monospace">0</text>
                <rect x="200" y="0" width="80" height="200" fill="rgba(46,107,255,.08)" stroke="rgba(46,107,255,.3)" stroke-width="1" stroke-dasharray="2 2" />
                <g stroke="#2E6BFF" stroke-width="0.4" fill="none" opacity="0.18">
                  <path v-for="(p, i) in ch.trials" :key="i" :d="p" />
                </g>
                <path :d="ch.avgS1" stroke="#2E6BFF" stroke-width="2" fill="none" />
                <path :d="ch.avgS2" stroke="#10B981" stroke-width="2" fill="none" />
                <text x="6" y="14" fill="#5B6B85" font-size="9">μV</text>
                <text x="396" y="196" fill="#5B6B85" font-size="9" text-anchor="end">ms</text>
              </svg>
            </div>
          </div>

          <div class="obs-panel">
            <div class="panel-head">
              <span class="ch-tag-solid" style="background: #5B6B85">Σ</span>
              <span class="title">蝶形图（5 通道叠加）</span>
              <span class="stats">GFP peak @ 388 ms</span>
            </div>
            <div class="panel-body">
              <svg viewBox="0 0 400 200" preserveAspectRatio="none">
                <rect width="400" height="200" fill="#fff" />
                <line x1="0" y1="100" x2="400" y2="100" stroke="#E5E9F2" stroke-dasharray="3 3" />
                <line x1="80" y1="0" x2="80" y2="200" stroke="#EF4444" stroke-width="1" stroke-dasharray="3 3" />
                <rect x="200" y="0" width="80" height="200" fill="rgba(46,107,255,.08)" stroke="rgba(46,107,255,.3)" stroke-width="1" stroke-dasharray="2 2" />
                <path v-for="(ch, i) in channels" :key="i" :d="ch.avgS1" :stroke="ch.color" stroke-width="1.2" fill="none" opacity="0.7" />
                <path :d="gfpPath" stroke="#1B2940" stroke-width="2.5" fill="none" />
              </svg>
            </div>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>区间统计 · 300 – 500 ms</h4>
          <div class="region-bar" style="border-radius: var(--r); border: 1px solid rgba(46, 107, 255, .3)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" /></svg>
            <span class="label">300 – 500 ms</span>
            <span style="margin-left: auto; color: var(--c-text-3); font-size: 10px">P300 窗口</span>
          </div>
        </div>

        <div class="st-section">
          <h4>每通道 · 条件 S1</h4>
          <div v-for="ch in channels" :key="ch.id" class="st-card">
            <div class="ttl">
              <span class="pin" :style="{ background: ch.color }"></span>{{ ch.label }}
              <span v-if="ch.star" style="margin-left: auto; font-size: 9px; color: var(--c-success)">★ 最大</span>
            </div>
            <div class="st-grid">
              <div class="st-cell"><span class="k">最大值</span><span class="v" :style="ch.star ? { color: 'var(--c-success)' } : null">+{{ ch.amp }} μV</span></div>
              <div class="st-cell"><span class="k">峰值潜伏期</span><span class="v" style="color: var(--c-primary)">{{ ch.peak }} ms</span></div>
              <div class="st-cell"><span class="k">均值</span><span class="v">+{{ (ch.amp * 0.42).toFixed(2) }} μV</span></div>
              <div class="st-cell"><span class="k">面积</span><span class="v">{{ Math.round(ch.amp * 92) }} μV·ms</span></div>
            </div>
          </div>
        </div>

        <div class="st-section">
          <h4>条件对比 · S1 vs S2</h4>
          <table class="small-tbl">
            <thead><tr><th>通道</th><th>S1 peak</th><th>S2 peak</th><th>Δ</th></tr></thead>
            <tbody>
              <tr v-for="ch in channels" :key="ch.id">
                <td>{{ ch.label }}</td>
                <td>+{{ ch.amp }}</td>
                <td>+{{ (ch.amp * 0.7).toFixed(1) }}</td>
                <td style="color: var(--c-success); font-weight: 700">+{{ (ch.amp * 0.3).toFixed(1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <button class="btn">导出统计 CSV</button>
          <RouterLink class="btn" to="/figures">发送到作图模块</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计模块</RouterLink>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'

function genErpPath(seed: number, peakMs: number, peakAmp: number, condShift = 0) {
  let path = ''
  for (let j = 0; j <= 200; j++) {
    const ms = -200 + j * 5
    let v = 0
    if (ms < 0) {
      v = (pseudoRand(seed + j) - 0.5) * 1.5 + Math.sin(ms / 40 + seed) * 0.5
    } else {
      const peak = peakMs + condShift
      v = Math.exp(-Math.pow((ms - peak) / 80, 2)) * (peakAmp + (pseudoRand(seed + j * 2) - 0.5) * 0.5)
      v -= Math.exp(-Math.pow((ms - 110) / 30, 2)) * 2.5
      v += (pseudoRand(seed + j * 3) - 0.5) * 0.8
    }
    const x = j * 2
    const y = 100 - v * 4
    path += (j === 0 ? 'M' : 'L') + x + ',' + y.toFixed(1) + ' '
  }
  return path
}

function genTrialPath(seed: number, peakMs: number, peakAmp: number) {
  let path = ''
  for (let j = 0; j <= 200; j++) {
    const ms = -200 + j * 5
    let v = (pseudoRand(seed + j) - 0.5) * 4
    if (ms > 0) {
      v += Math.exp(-Math.pow((ms - peakMs) / 80, 2)) * peakAmp + (pseudoRand(seed + j * 2) - 0.5) * 3
    }
    const x = j * 2
    const y = 100 - v * 4
    path += (j === 0 ? 'M' : 'L') + x + ',' + y.toFixed(1) + ' '
  }
  return path
}

function pseudoRand(seed: number) {
  const x = Math.sin(seed * 13.4567) * 43758.5453
  return x - Math.floor(x)
}

const channelDefs = [
  { id: 'fz', label: 'Fz', color: '#2E6BFF', peak: 348, amp: 8.2, subtitle: '前额中线 · sub-01 ~ sub-03' },
  { id: 'fcz', label: 'FCz', color: '#0891B2', peak: 372, amp: 9.7, subtitle: '额中央 · sub-01 ~ sub-03' },
  { id: 'cz', label: 'Cz', color: '#10B981', peak: 396, amp: 12.4, subtitle: '中央 · sub-01 ~ sub-03', star: true },
  { id: 'cpz', label: 'CPz', color: '#F59E0B', peak: 408, amp: 10.8, subtitle: '中央顶 · sub-01 ~ sub-03' },
  { id: 'pz', label: 'Pz', color: '#8B5CF6', peak: 432, amp: 8.1, subtitle: '顶中线 · sub-01 ~ sub-03' },
]

const channels = channelDefs.map((ch) => ({
  ...ch,
  trials: Array.from({ length: 8 }, (_, i) => genTrialPath(i + ch.peak / 100, ch.peak, ch.amp)),
  avgS1: genErpPath(ch.peak / 100, ch.peak, ch.amp),
  avgS2: genErpPath(ch.peak / 100 + 1, ch.peak, ch.amp * 0.7, 20),
}))

const gfpPath = (() => {
  let path = ''
  for (let j = 0; j <= 200; j++) {
    const ms = -200 + j * 5
    let max = 0
    channelDefs.forEach((ch) => {
      if (ms > 0) {
        const v = Math.exp(-Math.pow((ms - ch.peak) / 80, 2)) * ch.amp
        max = Math.max(max, v)
      }
    })
    const x = j * 2
    const y = 100 - max * 4 - 5
    path += (j === 0 ? 'M' : 'L') + x + ',' + y.toFixed(1) + ' '
  }
  return path
})()
</script>

<style scoped>
:deep(.page) { padding: 0; }
.erp-panels {
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: 1fr 1fr;
}
@media (max-width: 1300px) {
  .erp-panels { grid-template-columns: repeat(2, 1fr); grid-template-rows: repeat(3, 1fr); }
}
</style>
