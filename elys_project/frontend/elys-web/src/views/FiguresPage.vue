<template>
  <WorkbenchShell active-key="figures" active-top-key="figure">
    <div class="fig-layout">
      <aside class="lib-panel">
        <div class="lp-section">
          <h4>组件库 · 数据图 <span class="count">8</span></h4>
          <div class="lib-grid">
            <div v-for="card in dataCards" :key="card.label" class="lib-card" :title="card.label">
              <span v-html="card.icon"></span>
              <span class="lbl">{{ card.label }}</span>
            </div>
          </div>
        </div>

        <div class="lp-section">
          <h4>装饰元素 <span class="count">8</span></h4>
          <div class="lib-grid">
            <div v-for="card in decoCards" :key="card.label" class="lib-card" :title="card.label">
              <span v-html="card.icon"></span>
              <span class="lbl">{{ card.label }}</span>
            </div>
          </div>
        </div>

        <div class="lp-section">
          <h4>论文模板 <span class="count">3</span></h4>
          <div v-for="t in templates" :key="t.name" class="template-card">
            <div class="preview">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--c-primary)" stroke-width="2">
                <rect v-for="(r, i) in t.rects" :key="i" :x="r.x" :y="r.y" :width="r.w" :height="r.h" />
              </svg>
            </div>
            <div class="info">
              <div class="name">{{ t.name }}</div>
              <div class="meta">{{ t.meta }}</div>
            </div>
          </div>
        </div>

        <div class="lp-section">
          <h4>数据源</h4>
          <button class="lp-btn"><IconLine name="trendingUp" :size="14" /> 从分析结果导入</button>
          <button class="lp-btn"><IconLine name="folder" :size="14" /> 加载 CSV / NumPy</button>
          <button class="lp-btn"><IconLine name="clipboard" :size="14" /> 粘贴剪贴板</button>
        </div>
      </aside>

      <main class="fig-main">
        <div class="fig-toolbar">
          <div class="tool-grp">
            <button class="tool-btn" title="撤销">↶</button>
            <button class="tool-btn" title="重做">↷</button>
          </div>
          <div class="divider-h"></div>
          <div class="tool-grp">
            <span style="font-size: 11px; color: var(--c-text-3)">画布</span>
            <select class="select input--sm" style="width: 80px"><option>A4</option><option selected>Letter</option><option>自定义</option></select>
            <select class="select input--sm" style="width: 70px"><option>纵向</option><option>横向</option></select>
          </div>
          <div class="divider-h"></div>
          <div class="tool-grp">
            <button class="tool-btn" title="对齐左">⫷</button>
            <button class="tool-btn" title="水平居中">⊟</button>
            <button class="tool-btn" title="对齐右">⫸</button>
            <button class="tool-btn" title="均匀分布">≡</button>
          </div>
          <div class="divider-h"></div>
          <div class="tool-grp">
            <button class="tool-btn" title="组合">⬚</button>
            <button class="tool-btn" title="锁定"><IconLine name="lock" :size="14" /></button>
          </div>
          <div class="divider-h"></div>
          <div class="tool-grp">
            <button class="tool-btn">−</button>
            <span style="font-size: 11px; font-family: var(--ff-mono); color: var(--c-text-2); min-width: 38px; text-align: center">100%</span>
            <button class="tool-btn">+</button>
          </div>
          <div style="flex: 1"></div>
          <button class="tool-btn" style="width: auto; padding: 0 10px; font-size: 12px">网格</button>
        </div>

        <div class="fig-paper">
          <div class="paper-card">
            <div class="paper-meta">Figure 1 · P300 standard analysis · 7 × 9 in · 600 dpi</div>

            <div class="panel-grid">
              <div class="paper-panel pp-erp">
                <span class="panel-letter">a</span>
                <span class="panel-cap">ERP waveforms · Cz / Pz · target vs standard</span>
                <svg viewBox="0 0 380 180" preserveAspectRatio="none" class="paper-svg">
                  <rect width="380" height="180" fill="#fff" />
                  <line x1="0" y1="100" x2="380" y2="100" stroke="#9aa7b8" stroke-dasharray="3 3" />
                  <line x1="60" y1="0" x2="60" y2="180" stroke="#9aa7b8" />
                  <rect x="160" y="0" width="60" height="180" fill="rgba(46,107,255,.10)" />
                  <path d="M0 100 L40 100 L60 100 L80 80 L120 60 L160 30 L190 18 L220 35 L260 70 L300 90 L340 95 L380 100" stroke="#2E6BFF" stroke-width="2" fill="none" />
                  <path d="M0 100 L60 100 L100 95 L140 90 L180 75 L220 80 L260 95 L300 100 L380 100" stroke="#10B981" stroke-width="2" fill="none" />
                  <text x="6" y="18" font-family="Times New Roman, serif" font-size="11">μV</text>
                  <text x="370" y="174" font-family="Times New Roman, serif" font-size="11" text-anchor="end">ms</text>
                </svg>
              </div>

              <div class="paper-panel pp-topo">
                <span class="panel-letter">b</span>
                <span class="panel-cap">Topography · P300 peak 380 ms</span>
                <div class="topomap-fig">
                  <div class="topomap__big"></div>
                  <div class="topo-axis">
                    <span>−10 μV</span>
                    <div class="topo-bar"></div>
                    <span>+10 μV</span>
                  </div>
                </div>
              </div>

              <div class="paper-panel pp-tfr">
                <span class="panel-letter">c</span>
                <span class="panel-cap">Time–frequency · Cz · ERSP</span>
                <svg viewBox="0 0 380 180" preserveAspectRatio="none" class="paper-svg">
                  <defs>
                    <linearGradient id="tfrGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" stop-color="#fff5d6" />
                      <stop offset="0.5" stop-color="#fac874" />
                      <stop offset="1" stop-color="#7c1d6f" />
                    </linearGradient>
                  </defs>
                  <rect width="380" height="180" fill="#fff" />
                  <g>
                    <rect v-for="cell in tfrCells" :key="cell.id" :x="cell.x" :y="cell.y" :width="cell.w" :height="cell.h" :fill="cell.fill" />
                  </g>
                  <line x1="100" y1="0" x2="100" y2="180" stroke="#d43f34" stroke-width="1.5" stroke-dasharray="3 3" />
                </svg>
              </div>

              <div class="paper-panel pp-bar">
                <span class="panel-letter">d</span>
                <span class="panel-cap">Peak amplitude · target vs standard (n=30) ⋆⋆ p=0.008</span>
                <svg viewBox="0 0 380 180" preserveAspectRatio="none" class="paper-svg">
                  <rect width="380" height="180" fill="#fff" />
                  <line x1="40" y1="160" x2="370" y2="160" stroke="#9aa7b8" />
                  <line x1="40" y1="20" x2="40" y2="160" stroke="#9aa7b8" />
                  <rect x="130" y="50" width="60" height="110" fill="rgba(46,107,255,.5)" stroke="#2E6BFF" />
                  <line x1="160" y1="40" x2="160" y2="60" stroke="#2E6BFF" stroke-width="2" />
                  <rect x="240" y="90" width="60" height="70" fill="rgba(16,185,129,.5)" stroke="#10B981" />
                  <line x1="270" y1="80" x2="270" y2="100" stroke="#10B981" stroke-width="2" />
                  <line x1="160" y1="34" x2="270" y2="34" stroke="#1f2e3a" stroke-width="1" />
                  <line x1="160" y1="34" x2="160" y2="42" stroke="#1f2e3a" stroke-width="1" />
                  <line x1="270" y1="34" x2="270" y2="42" stroke="#1f2e3a" stroke-width="1" />
                  <text x="215" y="28" font-family="Times New Roman, serif" font-size="12" text-anchor="middle">⋆⋆</text>
                  <text x="160" y="175" font-family="Times New Roman, serif" font-size="11" text-anchor="middle">target</text>
                  <text x="270" y="175" font-family="Times New Roman, serif" font-size="11" text-anchor="middle">standard</text>
                  <text x="20" y="100" font-family="Times New Roman, serif" font-size="11" transform="rotate(-90 20 100)">μV</text>
                </svg>
              </div>
            </div>

            <div class="paper-caption">
              <strong>Figure 1.</strong> P300 standard analysis. (a) Grand-average ERP at Cz/Pz for target vs standard conditions (n=30). (b) Topography at the P300 peak (380 ms). (c) Time–frequency representation (ERSP, dB re. baseline) at Cz. (d) Peak amplitude comparison; ⋆⋆ p = 0.008, Cohen's d = 0.52.
            </div>
          </div>
        </div>
      </main>

      <aside class="prop-panel">
        <div class="lp-section">
          <h4>图层</h4>
          <div v-for="layer in layers" :key="layer.name" class="layer-row" :class="{ 'is-active': layer.active }">
            <span v-html="layer.icon"></span>
            <span class="name">{{ layer.name }}</span>
            <span class="vis"><IconLine name="check" :size="12" /></span>
          </div>
        </div>

        <div class="lp-section">
          <h4>选中：ERP 波形 (a)</h4>
          <div class="field-mini-row">
            <div class="field-mini">
              <label>X</label>
              <input class="input input--sm" value="0.6 in" />
            </div>
            <div class="field-mini">
              <label>Y</label>
              <input class="input input--sm" value="0.6 in" />
            </div>
            <div class="field-mini">
              <label>宽</label>
              <input class="input input--sm" value="3.3 in" />
            </div>
            <div class="field-mini">
              <label>高</label>
              <input class="input input--sm" value="2.0 in" />
            </div>
          </div>
          <div class="field-mini" style="margin-top: 6px">
            <label>字体</label>
            <select class="select input--sm">
              <option>Times New Roman</option>
              <option>Arial</option>
              <option>Helvetica</option>
            </select>
          </div>
          <div class="field-mini" style="margin-top: 6px">
            <label>线宽 (pt)</label>
            <div class="range-row">
              <input type="range" min="0.5" max="3" step="0.1" value="1.4" />
              <span class="range-val">1.4</span>
            </div>
          </div>
        </div>

        <div class="lp-section">
          <h4>统计标注</h4>
          <label class="checkbox-row"><input type="checkbox" checked />显示显著性符号</label>
          <label class="checkbox-row"><input type="checkbox" checked />误差线（SEM）</label>
          <label class="checkbox-row"><input type="checkbox" />置信区间阴影</label>
          <label class="checkbox-row"><input type="checkbox" />Cluster mask 高亮</label>
        </div>

        <div class="lp-section">
          <h4>导出</h4>
          <div class="field-mini">
            <label>格式</label>
            <select class="select input--sm">
              <option selected>SVG（矢量）</option>
              <option>PNG (600 dpi)</option>
              <option>PDF</option>
              <option>TIFF (LZW)</option>
            </select>
          </div>
          <div class="field-mini" style="margin-top: 6px">
            <label>分辨率</label>
            <select class="select input--sm">
              <option>300 dpi</option>
              <option selected>600 dpi</option>
              <option>1200 dpi</option>
            </select>
          </div>
          <button class="export-btn"><IconLine name="save" :size="14" /> 导出 Figure 1</button>
          <button class="btn" style="width: 100%; margin-top: 6px">批量导出全部图</button>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import IconLine from '@/components/IconLine.vue'

const dataCards = [
  { label: 'ERP 波形', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>' },
  { label: 'PSD', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h4l3-9 4 18 3-9h4"/></svg>' },
  { label: '时频图', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="1"/></svg>' },
  { label: '拓扑图', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>' },
  { label: '脑网络', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><line x1="11" y1="7.5" x2="7" y2="16.5"/><line x1="13" y1="7.5" x2="17" y2="16.5"/></svg>' },
  { label: '柱状图', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="20" x2="6" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="18" y1="20" x2="18" y2="14"/></svg>' },
  { label: '箱线图', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="6" x2="6" y2="18"/><rect x="3" y="9" width="6" height="6"/><line x1="14" y1="6" x2="14" y2="18"/><rect x="11" y="11" width="6" height="6"/></svg>' },
  { label: '散点', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="12" cy="12" r="2"/></svg>' },
]

const decoCards = [
  { label: '文本/标题', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="12" y1="4" x2="12" y2="20"/></svg>' },
  { label: '箭头', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>' },
  { label: '矩形', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>' },
  { label: '直线', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="19" x2="19" y2="5"/></svg>' },
  { label: '比例尺', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="2"/></svg>' },
  { label: '图例', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><line x1="14" y1="6.5" x2="20" y2="6.5"/></svg>' },
  { label: '子图标签', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>' },
  { label: '注释', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
]

const templates = [
  {
    name: 'Cell 风格 (2+1)',
    meta: '3 panels · 7 × 9 in',
    rects: [
      { x: 3, y: 3, w: 8, h: 8 },
      { x: 13, y: 3, w: 8, h: 8 },
      { x: 3, y: 13, w: 18, h: 8 },
    ],
  },
  {
    name: 'Nature 风格',
    meta: '1 wide + 2 panels',
    rects: [
      { x: 3, y: 3, w: 18, h: 6 },
      { x: 3, y: 11, w: 8, h: 10 },
      { x: 13, y: 11, w: 8, h: 10 },
    ],
  },
  {
    name: 'IEEE TBME',
    meta: '3.5 in column',
    rects: [
      { x: 3, y: 3, w: 8, h: 18 },
      { x: 13, y: 3, w: 8, h: 8 },
      { x: 13, y: 13, w: 8, h: 8 },
    ],
  },
]

const layers = [
  {
    name: 'Figure 1 caption',
    active: false,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 7h16M4 12h10M4 17h6"/></svg>',
  },
  {
    name: 'panel-a ERP',
    active: true,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
  },
  {
    name: 'panel-b Topo',
    active: false,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>',
  },
  {
    name: 'panel-c TFR',
    active: false,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="18" height="18" rx="1"/></svg>',
  },
  {
    name: 'panel-d Bar',
    active: false,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><line x1="6" y1="20" x2="6" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="18" y1="20" x2="18" y2="14"/></svg>',
  },
  {
    name: 'sig-marker ⋆⋆',
    active: false,
    icon: '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><polygon points="12 2 15 9 22 9 17 14 19 21 12 17 5 21 7 14 2 9 9 9"/></svg>',
  },
]

const tfrCells = (() => {
  const cells: { id: number; x: number; y: number; w: number; h: number; fill: string }[] = []
  const NX = 30, NY = 20
  const cellW = 380 / NX
  const cellH = 180 / NY
  for (let i = 0; i < NX; i++) {
    for (let j = 0; j < NY; j++) {
      const ts = (i / NX) * 2 - 0.5
      const freq = 1 + (j / NY) * 49
      let v = 0
      if (freq >= 13 && freq <= 28) v += 0.7 * Math.exp(-Math.pow((ts - 0.4) / 0.25, 2))
      if (freq >= 4 && freq <= 8) v += 0.4 * Math.exp(-Math.pow((ts - 0.3) / 0.2, 2))
      if (freq >= 8 && freq <= 13) v -= 0.6 * Math.exp(-Math.pow((ts - 0.6) / 0.3, 2))
      const t = Math.max(-1, Math.min(1, v))
      const k = (t + 1) / 2
      const fill = `rgb(${Math.round(68 + 188 * k)}, ${Math.round(1 + 230 * k)}, ${Math.round(84 + 138 * (1 - k))})`
      cells.push({
        id: i * NY + j,
        x: i * cellW,
        y: 180 - (j + 1) * cellH,
        w: cellW + 0.5,
        h: cellH + 0.5,
        fill,
      })
    }
  }
  return cells
})()
</script>

<style scoped>
:deep(.page) { padding: 0; }
.fig-layout {
  display: grid;
  grid-template-columns: 240px 1fr 280px;
  height: calc(100vh - var(--header-h));
  background: var(--c-bg-soft);
}
.lib-panel,
.prop-panel {
  background: var(--c-surface);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.lib-panel { border-right: 1px solid var(--c-border); }
.prop-panel { border-left: 1px solid var(--c-border); }
.lp-section { padding: 14px 14px; border-bottom: 1px solid var(--c-border); }
.lp-section h4 {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-3);
  letter-spacing: .8px;
  text-transform: uppercase;
  margin: 0 0 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.lp-section h4 .count {
  background: var(--c-primary);
  color: #fff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  font-family: var(--ff-mono);
  font-weight: 700;
}
.lib-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.lib-card {
  border: 1.5px solid var(--c-border);
  border-radius: var(--r-sm);
  padding: 8px 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: grab;
  color: var(--c-text-2);
}
.lib-card svg { width: 22px; height: 22px; color: var(--c-primary); }
.lib-card:hover { border-color: var(--c-primary); color: var(--c-primary); background: var(--c-primary-soft); }
.lib-card .lbl { font-size: 10px; text-align: center; }

.template-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  margin-bottom: 6px;
  cursor: pointer;
}
.template-card:hover { background: var(--c-bg-tint); }
.template-card .preview {
  width: 30px;
  height: 30px;
  background: var(--c-bg-soft);
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}
.template-card .name { font-size: 12px; font-weight: 600; color: var(--c-text); }
.template-card .meta { font-size: 10px; color: var(--c-text-3); }

.lp-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  font-size: 12px;
  color: var(--c-text-2);
  margin-bottom: 5px;
  cursor: pointer;
}
.lp-btn:hover { border-color: var(--c-primary); color: var(--c-primary); }

.fig-main {
  display: flex;
  flex-direction: column;
  background: var(--c-bg-soft);
  overflow: hidden;
}
.fig-toolbar {
  padding: 8px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}
.tool-grp { display: flex; align-items: center; gap: 6px; }
.tool-btn {
  width: 30px;
  height: 28px;
  border: 1px solid transparent;
  background: transparent;
  border-radius: var(--r-sm);
  cursor: pointer;
  color: var(--c-text-2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tool-btn:hover { background: var(--c-bg-tint); }

.fig-paper {
  flex: 1;
  overflow: auto;
  padding: 24px;
  background: linear-gradient(180deg, #f3f5f9, #e8edf3);
}
.paper-card {
  width: 760px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: 4px;
  box-shadow: 0 24px 60px rgba(27, 41, 64, .12);
  padding: 36px 42px 30px;
}
.paper-meta {
  font-size: 11px;
  color: var(--c-text-3);
  margin-bottom: 16px;
  text-align: center;
  font-family: 'Times New Roman', serif;
}
.panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.paper-panel {
  position: relative;
  border: 1px solid #e1e6ee;
  border-radius: 4px;
  padding: 24px 12px 12px;
  min-height: 220px;
  background: #fff;
}
.panel-letter {
  position: absolute;
  top: 6px;
  left: 10px;
  font-family: 'Times New Roman', serif;
  font-size: 14px;
  font-weight: 700;
}
.panel-cap {
  position: absolute;
  top: 6px;
  left: 32px;
  right: 10px;
  font-family: 'Times New Roman', serif;
  font-size: 11px;
  color: var(--c-text-2);
}
.paper-svg { width: 100%; height: auto; }

.topomap-fig { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.topomap__big {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  border: 1.5px solid var(--c-border-strong);
  background:
    radial-gradient(circle at 50% 35%, rgba(239, 68, 68, .65), transparent 35%),
    radial-gradient(circle at 50% 70%, rgba(46, 107, 255, .55), transparent 35%),
    radial-gradient(circle at 50% 50%, #FBE9E0 0%, #f7f9fc 80%);
}
.topo-axis {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Times New Roman', serif;
  font-size: 11px;
}
.topo-bar {
  width: 80px;
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(90deg, #2E6BFF, #fff, #EF4444);
}

.paper-caption {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid var(--c-border);
  font-family: 'Times New Roman', serif;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-text-2);
}

.layer-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--r-sm);
  font-size: 12px;
  cursor: pointer;
  color: var(--c-text-2);
}
.layer-row:hover { background: var(--c-bg-tint); }
.layer-row.is-active { background: var(--c-primary-soft); color: var(--c-primary); font-weight: 600; }
.layer-row .name { flex: 1; font-family: var(--ff-mono); font-size: 11px; }
.layer-row .vis { opacity: .5; font-size: 12px; }

.field-mini-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.field-mini { display: grid; gap: 4px; font-size: 11px; }
.field-mini label { color: var(--c-text-3); font-size: 10px; }
.range-row { display: flex; align-items: center; gap: 8px; }
.range-row input[type=range] { flex: 1; accent-color: var(--c-primary); height: 4px; }
.range-val { font-size: 11px; font-family: var(--ff-mono); color: var(--c-text); min-width: 36px; text-align: right; }

.export-btn {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  background: var(--c-primary);
  color: #fff;
  border: 0;
  border-radius: var(--r);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  margin-top: 6px;
  box-shadow: var(--shadow-glow-primary);
}
.export-btn:hover { background: var(--c-primary-hover); }

@media (max-width: 1280px) {
  .fig-layout { grid-template-columns: 200px 1fr 260px; }
  .paper-card { width: 700px; }
}
@media (max-width: 1024px) {
  .fig-layout { grid-template-columns: 1fr; }
  .lib-panel, .prop-panel { display: none; }
  .paper-card { width: 100%; }
}
</style>
