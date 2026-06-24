<template>
  <WorkbenchShell active-key="view-connectivity" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">2</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name" style="font-weight: 500">depri-affective-network</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">MDD · n=24 · resting</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">HC · n=22 · resting</span></div>
            <div class="ck-node"><input type="checkbox" /><span class="name" style="font-weight: 500">stroke-mi-rehab</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>频段 <span class="count">5</span></h4>
          <div style="display: flex; gap: 5px; flex-wrap: wrap">
            <span v-for="b in ['δ','θ','α','β','γ']" :key="b" class="cond-pill" :class="{ active: b === 'α', s1: b === 'α' }">{{ b }}</span>
          </div>
        </div>

        <div class="sel-section">
          <h4>连接方法</h4>
          <select class="select input--sm" style="width: 100%; font-size: 12px">
            <option>wPLI（加权相位滞后）</option>
            <option>PLV（相位锁定值）</option>
            <option>Coherence（相干性）</option>
            <option>dPLI（有向 PLI）</option>
            <option>Granger 因果</option>
          </select>
          <div style="margin-top: 8px; font-size: 11px; color: var(--c-text-2)">参考（脑解剖）</div>
          <select class="select input--sm" style="width: 100%; font-size: 12px; margin-top: 4px">
            <option>AAL · 90 ROI</option>
            <option>Desikan-Killiany · 68</option>
            <option>HCP-MMP1.0 · 360</option>
          </select>
        </div>

        <div class="sel-section">
          <h4>边阈值</h4>
          <div style="font-size: 11px; color: var(--c-text-2); margin-bottom: 4px">
            显示连接强度前 <strong style="color: var(--c-primary)">{{ threshold }}%</strong>
          </div>
          <input v-model.number="threshold" type="range" min="2" max="40" step="1" style="width: 100%" />
          <label class="checkbox-row" style="margin-top: 6px"><input type="checkbox" checked />FDR 校正后</label>
          <label class="checkbox-row"><input type="checkbox" />仅跨半球边</label>
        </div>

        <div class="sel-section">
          <h4>渲染配色</h4>
          <div class="cmap-grid">
            <div v-for="m in colormaps" :key="m.name" class="cmap-card" :class="{ 'is-on': m.active }">
              <div class="cmap-bar" :class="m.cls"></div>
              <span class="lbl">{{ m.name }}</span>
            </div>
          </div>
        </div>

        <div class="sel-section">
          <h4>显示控制</h4>
          <label class="checkbox-row"><input type="checkbox" checked />脑半透明</label>
          <label class="checkbox-row"><input type="checkbox" checked />节点填充按度</label>
          <label class="checkbox-row"><input type="checkbox" checked />边宽按权重</label>
          <label class="checkbox-row"><input type="checkbox" />仅显示显著边</label>
          <label class="checkbox-row"><input type="checkbox" checked />ROI 标签</label>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="conn">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">depri-affective-network · α · wPLI · 36 ROI</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">视图</span>
          <select><option>俯视（轴状）</option><option>侧视（左）</option><option>侧视（右）</option></select>
          <div class="divider-h"></div>
          <span class="tool-lbl">布局</span>
          <select><option>解剖位置</option><option>圆形</option><option>力导向</option></select>
          <div class="divider-h"></div>
          <span class="tool-lbl">种子</span>
          <select><option>L inf PCUN（默认）</option><option>L SPL</option><option>R AMYG</option></select>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">🔍 查找 ROI</button>
          <button class="btn btn--sm">导出</button>
        </div>

        <div class="viz-grid">
          <div class="viz-card">
            <span class="cap">a <em>俯视 · α 频段全网络</em></span>
            <div class="viz-body">
              <svg viewBox="0 0 220 240" preserveAspectRatio="xMidYMid meet">
                <ellipse cx="110" cy="120" rx="98" ry="108" fill="rgba(46,107,255,.06)" stroke="rgba(46,107,255,.4)" stroke-dasharray="3 3" />
                <line x1="110" y1="14" x2="110" y2="226" stroke="rgba(46,107,255,.25)" stroke-dasharray="2 3" />
                <g stroke="#C62828" stroke-opacity="0.55" stroke-width="0.8" fill="none">
                  <line v-for="(e, i) in brainEdges" :key="i" :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2" :stroke-width="e.w" />
                </g>
                <g>
                  <circle
                    v-for="(n, i) in brainNodes"
                    :key="i"
                    :cx="n.x"
                    :cy="n.y"
                    :r="n.r"
                    :fill="n.color"
                    stroke="#fff"
                    stroke-width="1.2"
                  />
                </g>
              </svg>
            </div>
            <div class="cbar-strip">
              <span>Low</span>
              <div class="grad"></div>
              <span>wPLI High</span>
            </div>
          </div>

          <div class="viz-card">
            <span class="cap">b <em>种子聚焦 · L inf PCUN</em></span>
            <div class="viz-body">
              <svg viewBox="0 0 220 240" preserveAspectRatio="xMidYMid meet">
                <ellipse cx="110" cy="120" rx="98" ry="108" fill="rgba(46,107,255,.06)" stroke="rgba(46,107,255,.4)" stroke-dasharray="3 3" />
                <g stroke="#F57C00" stroke-opacity="0.6" stroke-width="1.3" fill="none">
                  <line v-for="(e, i) in seedEdges" :key="i" :x1="100" y1="130" :x2="e.x" :y2="e.y" />
                </g>
                <circle cx="100" cy="130" r="9" fill="#C62828" stroke="#fff" stroke-width="2" />
                <circle v-for="(p, i) in seedTargets" :key="i" :cx="p.x" :cy="p.y" r="5" fill="#F57C00" stroke="#fff" stroke-width="1" />
              </svg>
            </div>
            <div class="cbar-strip"><span>Low</span><div class="grad"></div><span>High</span></div>
          </div>

          <div class="viz-card span-2">
            <span class="cap">c <em>Circos · 36 ROI · 全连接</em></span>
            <div class="viz-body">
              <svg viewBox="0 0 360 360" preserveAspectRatio="xMidYMid meet">
                <circle cx="180" cy="180" r="150" fill="none" stroke="var(--c-border)" />
                <g v-for="(seg, i) in circosSegments" :key="i">
                  <path :d="seg.path" :fill="seg.color" stroke="#fff" stroke-width="1" />
                  <text :x="seg.lx" :y="seg.ly" font-size="9" :fill="seg.color" :text-anchor="seg.anchor" font-family="monospace">
                    {{ seg.label }}
                  </text>
                </g>
                <g stroke-opacity="0.55" fill="none">
                  <path v-for="(c, i) in circosChords" :key="i" :d="c.d" :stroke="c.stroke" :stroke-width="c.width" />
                </g>
              </svg>
            </div>
          </div>

          <div v-for="seed in seedMiniSeeds" :key="seed.name" class="viz-card">
            <span class="cap">{{ seed.tag }} <em>seed: {{ seed.name }}</em></span>
            <div class="viz-body">
              <svg viewBox="0 0 200 200" preserveAspectRatio="xMidYMid meet">
                <circle cx="100" cy="100" r="80" fill="none" stroke="var(--c-border)" />
                <g stroke-opacity=".55" fill="none">
                  <path v-for="(c, i) in seed.chords" :key="i" :d="c" :stroke="seed.color" stroke-width="1.4" />
                </g>
                <circle cx="100" cy="100" r="6" :fill="seed.color" stroke="#fff" stroke-width="1.5" />
              </svg>
            </div>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>选中节点</h4>
          <div class="seed-card">
            <div class="seed-card__node">12</div>
            <div>
              <div style="font-weight: 600; font-size: 12px">L inf PCUN</div>
              <div style="font-size: 10px; color: var(--c-text-3)">Left Inf Precuneus · MNI [-12, -64, 32]</div>
            </div>
          </div>
          <div class="metric-grid">
            <div class="metric-cell"><div class="k">度</div><div class="v">12</div><div class="sub">/ 35 可能</div></div>
            <div class="metric-cell"><div class="k">介数中心性</div><div class="v">0.28</div><div class="sub">排名 4 / 36</div></div>
            <div class="metric-cell"><div class="k">聚类系数</div><div class="v">0.42</div><div class="sub">局部密度</div></div>
            <div class="metric-cell"><div class="k">所属模块</div><div class="v" style="font-size: 14px">M1·DMN</div><div class="sub">共 9 节点</div></div>
          </div>
        </div>

        <div class="st-section">
          <h4>全局图论指标 · α 频段</h4>
          <div class="metric-grid">
            <div class="metric-cell"><div class="k">全局效率</div><div class="v pos">0.71</div><div class="sub">信息整合好</div></div>
            <div class="metric-cell"><div class="k">特征路径</div><div class="v">2.4</div><div class="sub">L</div></div>
            <div class="metric-cell"><div class="k">聚类系数</div><div class="v">0.38</div><div class="sub">C</div></div>
            <div class="metric-cell"><div class="k">小世界 σ</div><div class="v pos">2.15</div><div class="sub">σ &gt; 1</div></div>
            <div class="metric-cell"><div class="k">模块化 Q</div><div class="v pos">0.45</div><div class="sub">4 个模块</div></div>
            <div class="metric-cell"><div class="k">同配性</div><div class="v warn">+0.07</div><div class="sub">弱正同配</div></div>
          </div>
        </div>

        <div class="st-section">
          <h4>种子节点列表（按度排序）</h4>
          <div class="seed-list">
            <div v-for="seed in seedList" :key="seed.name" class="seed-item" :class="{ 'is-on': seed.selected }">
              <span class="swatch" :style="{ background: seed.color }"></span>
              <span class="name">{{ seed.name }}</span>
              <span class="deg">deg {{ seed.deg }}</span>
            </div>
          </div>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <RouterLink class="btn" to="/figures">发送到作图</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计</RouterLink>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'

const threshold = ref(12)

const colormaps = [
  { name: 'YlOrRd', cls: 'cmap-ylorrd', active: true },
  { name: 'RdBu_r', cls: 'cmap-rdbu', active: false },
  { name: 'Spectral', cls: 'cmap-spec', active: false },
  { name: 'viridis', cls: 'cmap-vir', active: false },
]

const brainNodes = [
  { x: 70, y: 50, r: 7, color: '#C62828' },
  { x: 150, y: 50, r: 6, color: '#E53935' },
  { x: 50, y: 110, r: 7, color: '#FB8C00' },
  { x: 110, y: 130, r: 9, color: '#C62828' },
  { x: 170, y: 110, r: 6, color: '#F57C00' },
  { x: 60, y: 180, r: 6, color: '#FBC02D' },
  { x: 110, y: 200, r: 7, color: '#FB8C00' },
  { x: 160, y: 180, r: 6, color: '#F57C00' },
  { x: 90, y: 90, r: 5, color: '#FBC02D' },
  { x: 130, y: 90, r: 5, color: '#FBC02D' },
]

const brainEdges = [
  { x1: 110, y1: 130, x2: 70, y2: 50, w: 1.5 },
  { x1: 110, y1: 130, x2: 150, y2: 50, w: 1.2 },
  { x1: 110, y1: 130, x2: 50, y2: 110, w: 1.8 },
  { x1: 110, y1: 130, x2: 170, y2: 110, w: 1.2 },
  { x1: 110, y1: 130, x2: 110, y2: 200, w: 2.0 },
  { x1: 110, y1: 130, x2: 60, y2: 180, w: 1.0 },
  { x1: 110, y1: 130, x2: 160, y2: 180, w: 1.1 },
  { x1: 70, y1: 50, x2: 110, y2: 200, w: 0.7 },
  { x1: 50, y1: 110, x2: 170, y2: 110, w: 0.8 },
  { x1: 60, y1: 180, x2: 150, y2: 50, w: 0.6 },
]

const seedTargets = [
  { x: 60, y: 60 }, { x: 165, y: 70 }, { x: 50, y: 160 }, { x: 170, y: 170 },
  { x: 100, y: 200 }, { x: 80, y: 90 }, { x: 145, y: 100 },
]
const seedEdges = seedTargets

const circosSegments = (() => {
  const colors = ['#2E6BFF', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#0891B2', '#F97316']
  const labels = ['L Frontal', 'L Central', 'L Parietal', 'L Occipital', 'R Frontal', 'R Central', 'R Parietal', 'R Occipital']
  const cx = 180, cy = 180, r = 150
  return labels.map((label, i) => {
    const aStart = (i / labels.length) * Math.PI * 2 - Math.PI / 2
    const aEnd = ((i + 1) / labels.length) * Math.PI * 2 - Math.PI / 2 - 0.06
    const x1 = cx + Math.cos(aStart) * r
    const y1 = cy + Math.sin(aStart) * r
    const x2 = cx + Math.cos(aEnd) * r
    const y2 = cy + Math.sin(aEnd) * r
    const x1Out = cx + Math.cos(aStart) * (r + 12)
    const y1Out = cy + Math.sin(aStart) * (r + 12)
    const x2Out = cx + Math.cos(aEnd) * (r + 12)
    const y2Out = cy + Math.sin(aEnd) * (r + 12)
    const path = `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)} L ${x2Out.toFixed(1)} ${y2Out.toFixed(1)} A ${r + 12} ${r + 12} 0 0 0 ${x1Out.toFixed(1)} ${y1Out.toFixed(1)} Z`
    const aMid = (aStart + aEnd) / 2
    const lx = cx + Math.cos(aMid) * (r + 22)
    const ly = cy + Math.sin(aMid) * (r + 22)
    return {
      path,
      color: colors[i],
      label,
      lx,
      ly,
      anchor: Math.cos(aMid) > 0 ? 'start' : 'end',
    }
  })
})()

const circosChords = (() => {
  const cx = 180, cy = 180, r = 140
  const arr: { d: string; stroke: string; width: number }[] = []
  const colors = ['#C62828', '#E53935', '#F57C00', '#FB8C00', '#8B5CF6']
  for (let i = 0; i < 14; i++) {
    const a = Math.random() * Math.PI * 2
    const b = a + Math.PI * (0.4 + Math.random() * 0.9)
    const x1 = cx + Math.cos(a) * r
    const y1 = cy + Math.sin(a) * r
    const x2 = cx + Math.cos(b) * r
    const y2 = cy + Math.sin(b) * r
    arr.push({
      d: `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx} ${cy} ${x2.toFixed(1)} ${y2.toFixed(1)}`,
      stroke: colors[i % colors.length],
      width: 0.6 + Math.random() * 1.6,
    })
  }
  return arr
})()

function genSeedChords(color: string, count = 6) {
  const cx = 100, cy = 100, r = 78
  const chords: string[] = []
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2
    const x = cx + Math.cos(a) * r
    const y = cy + Math.sin(a) * r
    chords.push(`M ${cx} ${cy} Q ${cx + Math.cos(a) * 30} ${cy + Math.sin(a) * 30} ${x.toFixed(1)} ${y.toFixed(1)}`)
  }
  void color
  return chords
}

const seedMiniSeeds = [
  { tag: 'd', name: 'L SPL', color: '#E53935', chords: genSeedChords('#E53935') },
  { tag: 'e', name: 'L inf PCUN', color: '#C62828', chords: genSeedChords('#C62828', 8) },
  { tag: 'f', name: 'R AMYG', color: '#F57C00', chords: genSeedChords('#F57C00') },
]

const seedList = [
  { name: 'L inf PCUN', deg: 12, color: '#C62828', selected: true },
  { name: 'L SPL', deg: 10, color: '#E53935', selected: false },
  { name: 'R AMYG', deg: 9, color: '#F57C00', selected: false },
  { name: 'L MFG', deg: 8, color: '#FB8C00', selected: false },
  { name: 'L PCUN', deg: 7, color: '#FBC02D', selected: false },
  { name: 'R SPL', deg: 7, color: '#FBC02D', selected: false },
  { name: 'R MFG', deg: 6, color: '#F9A825', selected: false },
]
</script>

<style scoped>
:deep(.page) { padding: 0; }
.viz-grid {
  flex: 1;
  padding: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: 200px 1fr 200px;
  grid-template-rows: auto auto;
  overflow: auto;
}
.viz-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: 8px;
  position: relative;
  display: flex;
  flex-direction: column;
}
.viz-card.span-2 { grid-row: span 2; }
.viz-card .cap {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-2);
  padding: 0 2px 6px;
  display: block;
}
.viz-card .cap em {
  color: var(--c-text-3);
  font-style: normal;
  font-weight: 500;
  margin-left: 4px;
}
.viz-card .viz-body { flex: 1; min-height: 160px; }
.viz-card .viz-body svg { width: 100%; height: 100%; display: block; }
.cbar-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--c-text-3);
  margin-top: 6px;
}
.cbar-strip .grad {
  flex: 1;
  height: 6px;
  border-radius: 4px;
  background: var(--grad-ylorrd, linear-gradient(90deg, #FFC107, #FF9800, #FF5722, #C62828));
}
.cmap-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.cmap-card {
  border: 1.5px solid var(--c-border);
  border-radius: var(--r-sm);
  padding: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.cmap-card.is-on { border-color: var(--c-primary); background: var(--c-primary-soft); }
.cmap-card .cmap-bar { width: 100%; height: 8px; border-radius: 4px; }
.cmap-bar.cmap-ylorrd { background: linear-gradient(90deg, #FFC107, #FF9800, #FF5722, #C62828); }
.cmap-bar.cmap-rdbu { background: linear-gradient(90deg, #2E6BFF, #fff, #EF4444); }
.cmap-bar.cmap-spec { background: linear-gradient(90deg, #2E6BFF, #00C2A8, #F59E0B, #EF4444); }
.cmap-bar.cmap-vir { background: linear-gradient(90deg, #440154, #3B528B, #21918C, #5EC962, #FDE725); }
.cmap-card .lbl { font-size: 10px; color: var(--c-text-2); }

.seed-card {
  background: var(--c-primary-soft);
  padding: 10px;
  border-radius: var(--r);
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.seed-card__node {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #C62828;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--ff-mono);
  display: flex;
  align-items: center;
  justify-content: center;
}

.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.metric-cell {
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
  padding: 6px 8px;
}
.metric-cell .k { font-size: 10px; color: var(--c-text-3); }
.metric-cell .v {
  font-size: 18px;
  font-weight: 700;
  font-family: var(--ff-mono);
  margin-top: 2px;
  color: var(--c-text);
}
.metric-cell .v.pos { color: var(--c-success); }
.metric-cell .v.warn { color: var(--c-warning); }
.metric-cell .sub { font-size: 9px; color: var(--c-text-3); margin-top: 2px; }

.seed-list { display: grid; gap: 4px; }
.seed-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--r-sm);
  background: var(--c-bg-soft);
  font-size: 11px;
}
.seed-item.is-on { background: var(--c-primary-soft); }
.seed-item .swatch { width: 8px; height: 8px; border-radius: 50%; }
.seed-item .name { flex: 1; color: var(--c-text); font-weight: 600; }
.seed-item .deg { font-family: var(--ff-mono); color: var(--c-text-3); }

@media (max-width: 1300px) {
  .viz-grid { grid-template-columns: 180px 1fr 180px; }
}
@media (max-width: 1024px) {
  .viz-grid { grid-template-columns: 1fr; grid-template-rows: auto; }
}
</style>
