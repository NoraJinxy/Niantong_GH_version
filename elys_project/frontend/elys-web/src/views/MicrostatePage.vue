<template>
  <WorkbenchShell active-key="view-microstate" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">3</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name" style="font-weight: 500">resting-microstate-multi</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">Healthy Controls · n=58</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">Schizophrenia · n=42</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">Panic Disorder · n=22</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>当前被试</h4>
          <select class="select input--sm" style="width: 100%; font-family: var(--ff-mono)">
            <option>HC-sub-001（代表样本）</option>
            <option>HC-sub-002</option>
            <option>SCZ-sub-005</option>
            <option>组平均 · 全 HC</option>
            <option>组平均 · 全 SCZ</option>
          </select>
        </div>

        <div class="sel-section">
          <h4>聚类数 K <span class="count">4</span></h4>
          <div class="k-grid">
            <div v-for="k in clusterCounts" :key="k.value" class="k-card" :class="{ 'is-on': k.value === 4 }">
              <div class="num">{{ k.value }}</div>
              <div class="gev">{{ k.gev }}%</div>
            </div>
          </div>
          <div style="font-size: 10px; color: var(--c-text-3); margin-top: 6px">GEV = 全局解释方差</div>
        </div>

        <div class="sel-section">
          <h4>聚类算法</h4>
          <label class="checkbox-row"><input type="radio" name="algo" checked />修订 K-means (modKM)</label>
          <label class="checkbox-row"><input type="radio" name="algo" />AAHC 凝聚层次</label>
          <label class="checkbox-row"><input type="radio" name="algo" />T-AAHC 加权</label>
          <div style="font-size: 11px; color: var(--c-text-2); margin-top: 8px; margin-bottom: 4px">极性是否合并</div>
          <label class="checkbox-row"><input type="checkbox" checked />极性无关（推荐）</label>
        </div>

        <div class="sel-section">
          <h4>滤波带</h4>
          <div style="display: flex; gap: 6px; align-items: center">
            <input class="input input--sm" value="2" style="width: 50px; font-family: var(--ff-mono); text-align: center" />
            <span style="color: var(--c-text-3)">→</span>
            <input class="input input--sm" value="20" style="width: 50px; font-family: var(--ff-mono); text-align: center" />
            <span style="color: var(--c-text-3); font-size: 11px">Hz</span>
          </div>
          <div style="font-size: 10px; color: var(--c-text-3); margin-top: 6px">微状态分析常用 2–20 Hz</div>
        </div>

        <div class="sel-section">
          <h4>显示选项</h4>
          <label class="checkbox-row"><input type="checkbox" checked />原始 EEG（背景）</label>
          <label class="checkbox-row"><input type="checkbox" checked />GFP 包络</label>
          <label class="checkbox-row"><input type="checkbox" checked />状态色带</label>
          <label class="checkbox-row"><input type="checkbox" checked />显示状态字母</label>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="micro">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">resting-microstate-multi · K=4 · GEV 78.3% · modKM</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">视窗</span>
          <input class="input input--sm" value="0" style="width: 60px; font-family: var(--ff-mono); text-align: center" />
          <span style="color: var(--c-text-3)">→</span>
          <input class="input input--sm" value="2.5" style="width: 60px; font-family: var(--ff-mono); text-align: center" />
          <span style="color: var(--c-text-3); font-size: 11px">s</span>
          <div class="divider-h"></div>
          <span class="tool-lbl">参数</span>
          <select>
            <option>Duration (ms)</option>
            <option>Occurrence (/s)</option>
            <option selected>Coverage (%)</option>
            <option>Mean GFP</option>
          </select>
          <div class="divider-h"></div>
          <label class="checkbox-row" style="font-size: 11px"><input type="checkbox" checked />组平均拓扑</label>
          <label class="checkbox-row" style="font-size: 11px; margin-left: 6px"><input type="checkbox" checked />显著性 *</label>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">重新聚类</button>
          <button class="btn btn--sm">导出</button>
        </div>

        <div class="ms-stage">
          <div class="viz-card">
            <div class="cap">A <em>4 个微状态拓扑（K-means · GEV = 78.3%）</em></div>
            <div class="ms-topo-row">
              <div v-for="ms in states" :key="ms.id" class="ms-topo">
                <div class="ms-topo__map" :style="ms.topo"></div>
                <div class="ms-topo__label" :style="{ background: ms.color }">{{ ms.id }}</div>
                <div class="ms-topo__sub">{{ ms.feature }}</div>
              </div>
            </div>
          </div>

          <div class="viz-card">
            <div class="cap">B <em>状态序列 · 2.5 s 片段</em></div>
            <div class="ms-sequence">
              <div v-for="(seg, i) in sequence" :key="i" :style="{ flex: seg.dur, background: stateColor(seg.id) }">
                {{ seg.id }}
              </div>
            </div>
            <svg viewBox="0 0 600 100" preserveAspectRatio="none" class="ms-eeg">
              <line x1="0" y1="50" x2="600" y2="50" stroke="var(--c-border)" stroke-dasharray="2 4" />
              <path
                d="M0 50 Q40 30 80 50 T160 50 T240 30 T320 50 T400 60 T480 30 T560 50 T600 40"
                stroke="var(--c-primary)" stroke-width="1.2" fill="none"
              />
              <path
                d="M0 60 Q60 50 120 65 T240 60 T360 50 T480 60 T600 55"
                stroke="var(--c-text-3)" stroke-width="0.8" fill="none" opacity="0.6"
              />
            </svg>
            <div class="ms-axis"><span>0 s</span><span>1.0</span><span>2.0</span><span>2.5 s</span></div>
          </div>

          <div class="viz-card">
            <div class="cap">C <em>GFP 峰值标注 · 28 个峰</em></div>
            <svg viewBox="0 0 600 100" preserveAspectRatio="none" class="ms-eeg">
              <line x1="0" y1="80" x2="600" y2="80" stroke="var(--c-border)" />
              <path
                d="M0 80 L40 50 L70 75 L110 30 L150 70 L195 35 L230 65 L275 25 L320 70 L370 40 L420 75 L470 35 L520 65 L575 30 L600 60"
                stroke="var(--c-primary)" stroke-width="1.5" fill="none"
              />
              <g>
                <circle v-for="(peak, i) in gfpPeaks" :key="i" :cx="peak.x" :cy="peak.y" r="4" :fill="stateColor(peak.id)" stroke="#fff" stroke-width="1" />
              </g>
            </svg>
            <div class="ms-axis"><span>GFP</span><span style="flex: 1"></span><span>峰间距 ≥ 30 ms</span></div>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>微状态参数</h4>
          <table class="params-tbl">
            <thead>
              <tr><th></th><th>Duration</th><th>Occurrence</th><th>Coverage</th></tr>
            </thead>
            <tbody>
              <tr v-for="ms in states" :key="ms.id">
                <td><span class="ms-pin" :style="{ background: ms.color }">{{ ms.id }}</span></td>
                <td class="v">{{ ms.duration }} ms</td>
                <td class="v">{{ ms.occurrence }}/s</td>
                <td class="v">{{ ms.coverage }}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="st-section">
          <h4>转移概率矩阵 (Tij)</h4>
          <div class="tmatrix">
            <div class="head"></div>
            <div class="head">A</div>
            <div class="head">B</div>
            <div class="head">C</div>
            <div class="head">D</div>
            <template v-for="(row, i) in transitions" :key="i">
              <div class="head"><span class="ms-tag" :style="{ background: states[i].color }"></span>{{ states[i].id }}</div>
              <div v-for="(val, j) in row" :key="j" :class="{ strong: val > 0.3 }">{{ val.toFixed(2) }}</div>
            </template>
          </div>
          <div style="font-size: 10px; color: var(--c-text-3); margin-top: 6px">行 → 列 · 条件概率</div>
        </div>

        <div class="st-section">
          <h4>状态特征</h4>
          <div v-for="ms in states" :key="ms.id" class="edu-card" :style="{ borderLeftColor: ms.color }">
            <div class="ttl"><span class="ms-pin" :style="{ background: ms.color }">{{ ms.id }}</span>{{ ms.featureFull }}</div>
            <div class="body">{{ ms.description }}</div>
          </div>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <RouterLink class="btn" to="/figures">发送到作图</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计</RouterLink>
          <button class="btn">导出 microstate_stats.tsv</button>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'

const clusterCounts = [
  { value: 3, gev: 68 },
  { value: 4, gev: 78 },
  { value: 5, gev: 82 },
  { value: 6, gev: 85 },
]

const states = [
  {
    id: 'A', color: '#FBC02D',
    topo: 'background: radial-gradient(circle at 30% 30%, rgba(46, 107, 255, .7), transparent 40%), radial-gradient(circle at 70% 70%, rgba(239, 68, 68, .55), transparent 40%), #FFF8E5;',
    feature: '右前 / 左后',
    featureFull: '右前 → 左后 偶极',
    description: '言语 / 听觉相关网络 · 听觉 PFC',
    duration: 78, occurrence: 3.6, coverage: 28.4,
  },
  {
    id: 'B', color: '#4CAF50',
    topo: 'background: radial-gradient(circle at 70% 30%, rgba(46, 107, 255, .7), transparent 40%), radial-gradient(circle at 30% 70%, rgba(239, 68, 68, .55), transparent 40%), #E9F7EE;',
    feature: '左前 / 右后',
    featureFull: '左前 → 右后 偶极',
    description: '视觉网络 · 枕部活动',
    duration: 82, occurrence: 3.2, coverage: 25.1,
  },
  {
    id: 'C', color: '#00BCD4',
    topo: 'background: radial-gradient(circle at 50% 25%, rgba(46, 107, 255, .8), transparent 40%), radial-gradient(circle at 50% 75%, rgba(245, 158, 11, .5), transparent 35%), #E0F7FA;',
    feature: '前后纵向',
    featureFull: '前后纵向偶极',
    description: '默认模式网络（DMN）',
    duration: 86, occurrence: 3.4, coverage: 27.8,
  },
  {
    id: 'D', color: '#F4511E',
    topo: 'background: radial-gradient(circle at 50% 50%, rgba(245, 158, 11, .85), transparent 40%), radial-gradient(circle at 50% 50%, rgba(239, 68, 68, .35), transparent 60%), #FBE9E7;',
    feature: '中线主导',
    featureFull: '中线 / 注意系统',
    description: '注意控制 · 中央激活',
    duration: 74, occurrence: 2.8, coverage: 18.7,
  },
]

function stateColor(id: string) {
  const ms = states.find((s) => s.id === id)
  return ms ? ms.color : 'var(--c-text-3)'
}

const sequence = [
  { id: 'A', dur: 2 }, { id: 'C', dur: 3 }, { id: 'B', dur: 2 },
  { id: 'A', dur: 2 }, { id: 'D', dur: 1 }, { id: 'C', dur: 3 },
  { id: 'B', dur: 2 }, { id: 'C', dur: 2 }, { id: 'A', dur: 1 },
  { id: 'D', dur: 2 }, { id: 'B', dur: 2 }, { id: 'A', dur: 1 },
]

const gfpPeaks = (() => {
  const peaks = [
    { x: 40, y: 50, id: 'A' }, { x: 110, y: 30, id: 'C' }, { x: 195, y: 35, id: 'B' },
    { x: 275, y: 25, id: 'A' }, { x: 370, y: 40, id: 'C' }, { x: 470, y: 35, id: 'D' },
    { x: 575, y: 30, id: 'B' },
  ]
  return peaks
})()

const transitions = [
  [0.00, 0.31, 0.42, 0.27],
  [0.28, 0.00, 0.36, 0.36],
  [0.34, 0.34, 0.00, 0.32],
  [0.30, 0.32, 0.38, 0.00],
]
</script>

<style scoped>
:deep(.page) { padding: 0; }
.k-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.k-card {
  border: 1.5px solid var(--c-border);
  border-radius: var(--r-sm);
  padding: 6px 4px;
  text-align: center;
  cursor: pointer;
}
.k-card.is-on { border-color: var(--c-primary); background: var(--c-primary-soft); color: var(--c-primary); }
.k-card .num { font-size: 16px; font-weight: 700; font-family: var(--ff-mono); }
.k-card .gev { font-size: 10px; color: var(--c-text-3); }

.ms-stage {
  flex: 1;
  padding: 12px;
  display: grid;
  gap: 12px;
  grid-template-rows: auto 1fr 1fr;
  overflow: auto;
}
.viz-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.viz-card .cap {
  font-size: 12px;
  color: var(--c-text-2);
  font-weight: 600;
}
.viz-card .cap em {
  color: var(--c-text-3);
  font-style: normal;
  font-weight: 500;
  margin-left: 6px;
}

.ms-topo-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.ms-topo { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.ms-topo__map {
  width: 110px;
  height: 110px;
  border-radius: 50%;
  border: 2px solid var(--c-border-strong);
  position: relative;
}
.ms-topo__label {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-family: 'Times New Roman', serif;
  font-size: 16px;
}
.ms-topo__sub { font-size: 11px; color: var(--c-text-2); }

.ms-sequence {
  display: flex;
  height: 22px;
  border-radius: 6px;
  overflow: hidden;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  font-family: 'Times New Roman', serif;
}
.ms-sequence > div {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}

.ms-eeg {
  width: 100%;
  height: 100px;
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
}
.ms-axis {
  display: flex;
  justify-content: space-between;
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--c-text-3);
}

.params-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.params-tbl th, .params-tbl td {
  padding: 6px;
  border-bottom: 1px solid var(--c-border);
  text-align: left;
}
.params-tbl th { background: var(--c-bg-soft); font-size: 10px; color: var(--c-text-3); }
.params-tbl td.v { font-family: var(--ff-mono); font-weight: 600; color: var(--c-text); }
.ms-pin {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  color: #fff;
  font-weight: 700;
  font-size: 10px;
  font-family: 'Times New Roman', serif;
}

.tmatrix {
  display: grid;
  grid-template-columns: 36px repeat(4, 1fr);
  grid-template-rows: 24px repeat(4, 1fr);
  gap: 1px;
  background: var(--c-border);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  overflow: hidden;
  font-family: var(--ff-mono);
  font-size: 11px;
}
.tmatrix > div {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}
.tmatrix .head { background: var(--c-bg-soft); font-weight: 700; font-size: 10px; }
.tmatrix .ms-tag { width: 14px; height: 14px; border-radius: 3px; margin-right: 4px; }
.tmatrix .strong { font-weight: 700; color: var(--c-primary); }

.edu-card {
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  padding: 8px 10px;
  margin-bottom: 6px;
  border-left: 3px solid var(--c-accent);
}
.edu-card .ttl {
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--c-text);
  display: flex;
  align-items: center;
  gap: 4px;
}
.edu-card .body { font-size: 11px; color: var(--c-text-2); line-height: 1.5; }
</style>
