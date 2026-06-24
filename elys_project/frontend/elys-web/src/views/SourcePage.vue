<template>
  <WorkbenchShell active-key="view-source" active-top-key="observe">
    <div class="obs-layout">
      <aside class="selector-panel">
        <div class="sel-section">
          <h4>数据集 <span class="count">2</span></h4>
          <div class="checkbox-tree">
            <div class="ck-node"><input type="checkbox" checked /><span class="name" style="font-weight: 500">stroke-mi-rehab</span></div>
            <div class="ck-node indent-1"><input type="checkbox" checked /><span class="name text-mono" style="font-size: 11px">sub-03 · MI · target</span></div>
            <div class="ck-node indent-1"><input type="checkbox" /><span class="name text-mono" style="font-size: 11px">sub-03 · MI · standard</span></div>
            <div class="ck-node"><input type="checkbox" /><span class="name" style="font-weight: 500">p300-bci-spelling</span></div>
          </div>
        </div>

        <div class="sel-section">
          <h4>溯源方法</h4>
          <div v-for="m in methods" :key="m.name" class="method-card" :class="{ 'is-on': m.active }">
            <span class="nm">{{ m.name }}</span>
            <span class="m-badge">{{ m.tag }}</span>
            <span class="desc">{{ m.desc }}</span>
          </div>
        </div>

        <div class="sel-section">
          <h4>解剖图谱</h4>
          <select class="select input--sm" style="width: 100%">
            <option>Desikan-Killiany · 68 ROI</option>
            <option>Destrieux · 148 ROI</option>
            <option>HCP-MMP1.0 · 360 ROI</option>
            <option>Brodmann · 44 区</option>
          </select>
          <div style="font-size: 11px; color: var(--c-text-2); margin-top: 8px; margin-bottom: 4px">头模板</div>
          <select class="select input--sm" style="width: 100%">
            <option>MNI152（默认）</option>
            <option>fsaverage5</option>
            <option>个体 MRI</option>
          </select>
        </div>

        <div class="sel-section">
          <h4>分析时窗</h4>
          <div style="display: flex; gap: 6px; align-items: center">
            <input class="input input--sm" value="280" style="width: 60px; font-family: var(--ff-mono); text-align: center" />
            <span style="color: var(--c-text-3)">→</span>
            <input class="input input--sm" value="420" style="width: 60px; font-family: var(--ff-mono); text-align: center" />
            <span style="color: var(--c-text-3); font-size: 11px">ms</span>
          </div>
          <div style="font-size: 11px; color: var(--c-text-2); margin-top: 10px; margin-bottom: 4px">频段</div>
          <select class="select input--sm" style="width: 100%">
            <option>Mu (8-13 Hz)</option>
            <option>Alpha (8-13 Hz)</option>
            <option>Beta (13-30 Hz)</option>
            <option>Gamma (30-50 Hz)</option>
          </select>
        </div>

        <div class="sel-section">
          <h4>阈值 / Log F-ratio</h4>
          <div style="font-size: 11px; color: var(--c-text-2); margin-bottom: 4px">
            最小显示 <strong style="color: var(--c-primary)">{{ (threshold / 100).toFixed(3) }}</strong>
          </div>
          <input v-model.number="threshold" type="range" min="0" max="124" step="1" style="width: 100%" />
          <label class="checkbox-row" style="margin-top: 6px"><input type="checkbox" checked />FDR 校正后</label>
          <label class="checkbox-row"><input type="checkbox" />仅显示 cluster</label>
        </div>

        <div class="sel-section">
          <h4>显示控制</h4>
          <label class="checkbox-row"><input type="checkbox" checked />皮层折叠</label>
          <label class="checkbox-row"><input type="checkbox" />皮层充气（inflated）</label>
          <label class="checkbox-row"><input type="checkbox" checked />MRI 切片背景</label>
          <label class="checkbox-row"><input type="checkbox" checked />十字光标联动</label>
          <label class="checkbox-row"><input type="checkbox" checked />ROI 轮廓</label>
        </div>
      </aside>

      <main class="obs-main">
        <ObserveTabs active="source">
          <template #meta>
            <span style="font-size: 11px; color: var(--c-text-3)">sub-03 · MI target · sLORETA · μ band · 280-420 ms</span>
          </template>
        </ObserveTabs>

        <div class="obs-toolbar">
          <span class="tool-lbl">峰值时刻</span>
          <input class="input input--sm" value="342" style="width: 62px; font-family: var(--ff-mono); text-align: center" />
          <span style="color: var(--c-text-3); font-size: 11px">ms</span>
          <div class="divider-h"></div>
          <span class="tool-lbl">坐标 (mm)</span>
          <span class="coord-tag">[X, Y, Z] = [−6, −28, +51]</span>
          <div class="divider-h"></div>
          <span class="tool-lbl">体素</span>
          <select><option>3 mm³</option><option>5 mm³</option><option>10 mm³</option></select>
          <span class="tool-lbl">投影</span>
          <select><option>固定方向</option><option>自由方向</option></select>
          <div style="flex: 1"></div>
          <button class="btn btn--sm">重置视角</button>
          <button class="btn btn--sm">导出</button>
        </div>

        <div class="src-stage">
          <div class="viz-card">
            <div class="cap">A <em>皮层表面渲染 · 5 视角 · 阈值化激活叠加</em></div>
            <div class="cortex-row">
              <div v-for="view in cortexViews" :key="view.label" class="cortex-cell">
                <span class="vlbl">{{ view.label }}</span>
                <svg viewBox="0 0 200 200" preserveAspectRatio="xMidYMid meet">
                  <defs>
                    <radialGradient :id="`g-${view.id}`" cx="50%" cy="40%" r="50%">
                      <stop offset="0%" stop-color="#fff8c2" />
                      <stop offset="40%" stop-color="#ff8a3d" />
                      <stop offset="100%" stop-color="#7c1d1d" />
                    </radialGradient>
                  </defs>
                  <ellipse cx="100" cy="105" rx="78" ry="82" fill="#F5E7D6" stroke="#a37d52" stroke-width="1.5" />
                  <path d="M40 100 Q60 60 100 70 T160 100 Q160 150 100 165 Q40 150 40 100 Z" fill="#FBE9E0" stroke="#a37d52" stroke-width="0.7" opacity="0.5" />
                  <circle :cx="view.hot.x" :cy="view.hot.y" :r="view.hot.r" :fill="`url(#g-${view.id})`" opacity="0.85" />
                  <circle v-if="view.hot2" :cx="view.hot2.x" :cy="view.hot2.y" :r="view.hot2.r" :fill="`url(#g-${view.id})`" opacity="0.6" />
                  <line x1="100" y1="20" x2="100" y2="190" stroke="#9aa7b8" stroke-width="0.6" stroke-dasharray="2 3" />
                  <line x1="20" y1="105" x2="180" y2="105" stroke="#9aa7b8" stroke-width="0.6" stroke-dasharray="2 3" />
                </svg>
              </div>
            </div>
          </div>

          <div class="viz-card">
            <div class="cap">B <em>三正交切片 · 十字光标定位 · MNI 模板</em></div>
            <div class="slice-row">
              <div v-for="slice in slices" :key="slice.label" class="slice-cell">
                <span class="vname">{{ slice.label }}</span>
                <span class="coord-tag">{{ slice.coord }}</span>
                <span class="method-tag">sLORETA</span>
                <svg viewBox="0 0 220 220" preserveAspectRatio="xMidYMid meet">
                  <rect width="220" height="220" fill="#1B2024" />
                  <g v-for="(ring, i) in slice.rings" :key="i">
                    <ellipse :cx="ring.cx" :cy="ring.cy" :rx="ring.rx" :ry="ring.ry" :fill="ring.fill" :opacity="ring.opacity" />
                  </g>
                  <circle :cx="110" cy="110" r="18" fill="rgba(255,138,61,.85)" />
                  <circle :cx="110" cy="110" r="6" fill="#fff8c2" />
                  <line x1="0" y1="110" x2="220" y2="110" stroke="#5db0ff" stroke-width="0.8" stroke-dasharray="2 3" />
                  <line x1="110" y1="0" x2="110" y2="220" stroke="#5db0ff" stroke-width="0.8" stroke-dasharray="2 3" />
                </svg>
              </div>
            </div>
          </div>

          <div class="viz-card cbar-card">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-size: 11px; color: var(--c-text-3); font-family: 'Times New Roman', serif">激活强度</span>
              <span style="font-family: 'Times New Roman', serif; font-style: italic">Log F-ratio</span>
            </div>
            <div class="cbar"></div>
            <div class="cbar-ticks">
              <span>0.000</span><span>0.207</span><span>0.413</span><span>0.620</span><span>0.827</span><span>1.033</span><span>1.240</span>
            </div>
          </div>
        </div>
      </main>

      <aside class="stats-panel">
        <div class="st-section">
          <h4>选中体素</h4>
          <div class="peak-card">
            <div><span class="k">激活峰</span><span class="v large">1.18</span></div>
            <div><span class="k">坐标 (mm)</span><span class="v">[−6, −28, +51]</span></div>
            <div><span class="k">解剖位置</span><span class="v">L Postcentral G.</span></div>
            <div><span class="k">峰值时刻</span><span class="v">342 ms</span></div>
            <div><span class="k">所属 cluster</span><span class="v">M1 sensorimotor</span></div>
          </div>
        </div>

        <div class="st-section">
          <h4>显著 ROI（FDR 校正）</h4>
          <div v-for="roi in significantRois" :key="roi.name" class="roi-card">
            <div class="row row--between">
              <strong style="font-size: 12px">{{ roi.name }}</strong>
              <span class="text-mono" style="font-size: 11px; color: var(--c-success)">{{ roi.value }}</span>
            </div>
            <div class="muted" style="font-size: 11px; margin-top: 2px">{{ roi.desc }}</div>
          </div>
        </div>

        <div class="st-section">
          <h4>方法说明</h4>
          <div class="edu-card">
            <div class="ttl">sLORETA</div>
            <div class="body">
              Standardized LOw Resolution brain Electromagnetic TomogrAphy — 假设源平滑分布，给出零定位误差的统计估计。结果以 <code>Log F-ratio</code> 表示偏离背景的程度。
            </div>
          </div>
        </div>

        <div class="st-section">
          <h4>导出</h4>
          <RouterLink class="btn" to="/figures">发送到作图</RouterLink>
          <RouterLink class="btn" to="/statistics">发送到统计</RouterLink>
          <button class="btn">导出 sources.stc</button>
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

const threshold = ref(62)

const methods = [
  { name: 'sLORETA', tag: '推荐', desc: '标准化低分辨率 · 假设源平滑', active: true },
  { name: 'eLORETA', tag: '改进', desc: '无偏估计的精确版' },
  { name: 'dSPM', tag: 'F-stat', desc: '噪声归一化 MNE' },
  { name: 'MNE', tag: '基础', desc: '最小范数估计' },
  { name: 'Beamformer (LCMV)', tag: '空间', desc: '线性约束最小方差' },
]

const cortexViews = [
  { id: 'll', label: 'Left Lateral', hot: { x: 80, y: 90, r: 28 }, hot2: { x: 50, y: 130, r: 16 } },
  { id: 'top', label: 'Top (axial)', hot: { x: 95, y: 100, r: 30 }, hot2: { x: 130, y: 70, r: 14 } },
  { id: 'rl', label: 'Right Lateral', hot: { x: 130, y: 95, r: 22 } },
  { id: 'lm', label: 'Left Medial', hot: { x: 95, y: 105, r: 20 } },
  { id: 'rm', label: 'Right Medial', hot: { x: 105, y: 115, r: 18 } },
]

const slices = [
  {
    label: 'Axial', coord: 'Z = +51',
    rings: [
      { cx: 110, cy: 110, rx: 90, ry: 80, fill: '#3a4960', opacity: 1 },
      { cx: 110, cy: 110, rx: 70, ry: 62, fill: '#2c3a4f', opacity: 1 },
      { cx: 110, cy: 110, rx: 40, ry: 36, fill: '#1f2a3a', opacity: 1 },
    ],
  },
  {
    label: 'Sagittal', coord: 'X = −6',
    rings: [
      { cx: 110, cy: 110, rx: 80, ry: 90, fill: '#3a4960', opacity: 1 },
      { cx: 110, cy: 110, rx: 60, ry: 70, fill: '#2c3a4f', opacity: 1 },
      { cx: 110, cy: 110, rx: 32, ry: 40, fill: '#1f2a3a', opacity: 1 },
    ],
  },
  {
    label: 'Coronal', coord: 'Y = −28',
    rings: [
      { cx: 110, cy: 110, rx: 92, ry: 80, fill: '#3a4960', opacity: 1 },
      { cx: 110, cy: 110, rx: 72, ry: 62, fill: '#2c3a4f', opacity: 1 },
      { cx: 110, cy: 110, rx: 38, ry: 34, fill: '#1f2a3a', opacity: 1 },
    ],
  },
]

const significantRois = [
  { name: 'L Postcentral G.', value: '1.18', desc: '中央后回 · 感觉运动区' },
  { name: 'L Precentral G.', value: '0.97', desc: '中央前回 · M1' },
  { name: 'L Sup. Parietal L.', value: '0.74', desc: '上顶小叶 · 运动想象' },
  { name: 'R Postcentral G.', value: '0.68', desc: '对侧感觉运动区' },
]
</script>

<style scoped>
:deep(.page) { padding: 0; }
.src-stage {
  flex: 1;
  padding: 12px;
  display: grid;
  gap: 12px;
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
.viz-card .cap em { color: var(--c-text-3); font-style: normal; font-weight: 500; margin-left: 6px; }

.method-card {
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  padding: 8px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px;
}
.method-card.is-on { border-color: var(--c-primary); background: var(--c-primary-soft); }
.method-card .nm { font-weight: 600; font-size: 12px; }
.method-card .m-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--c-bg-tint);
  color: var(--c-text-2);
}
.method-card.is-on .m-badge { background: var(--c-primary); color: #fff; }
.method-card .desc { grid-column: 1 / -1; font-size: 11px; color: var(--c-text-2); }

.coord-tag {
  font-family: var(--ff-mono);
  font-size: 11px;
  background: var(--c-bg-tint);
  padding: 3px 8px;
  border-radius: 4px;
}

.cortex-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.cortex-cell {
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  padding: 8px;
  position: relative;
  text-align: center;
}
.cortex-cell svg { width: 100%; height: auto; max-height: 180px; }
.vlbl {
  font-size: 10px;
  color: var(--c-text-3);
  font-family: 'Times New Roman', serif;
  font-style: italic;
}

.slice-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.slice-cell {
  position: relative;
  background: #1B2024;
  border-radius: var(--r-sm);
  overflow: hidden;
  padding: 8px;
}
.slice-cell svg { width: 100%; max-height: 220px; }
.slice-cell .vname {
  position: absolute;
  top: 8px;
  left: 8px;
  color: #fff;
  font-size: 11px;
  font-family: 'Times New Roman', serif;
  z-index: 2;
}
.slice-cell .coord-tag {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, .15);
  color: #fff;
  z-index: 2;
}
.slice-cell .method-tag {
  position: absolute;
  bottom: 8px;
  left: 8px;
  font-size: 10px;
  color: rgba(255, 255, 255, .7);
  font-family: 'Times New Roman', serif;
  font-style: italic;
}

.cbar-card { padding: 12px 16px; }
.cbar {
  height: 16px;
  border-radius: 4px;
  background: linear-gradient(90deg, #000 0%, #5a0000 25%, #ff4500 50%, #ffa500 70%, #ffff00 90%, #fff 100%);
  margin: 8px 0 4px;
}
.cbar-ticks {
  display: flex;
  justify-content: space-between;
  font-family: var(--ff-mono);
  font-size: 10px;
  color: var(--c-text-3);
}

.peak-card {
  background: var(--c-primary-soft);
  border-radius: var(--r);
  padding: 10px;
  display: grid;
  gap: 6px;
}
.peak-card > div {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--c-text-2);
}
.peak-card .k { color: var(--c-text-3); }
.peak-card .v { font-family: var(--ff-mono); font-weight: 600; color: var(--c-text); }
.peak-card .v.large { font-size: 18px; color: var(--c-primary); }

.roi-card {
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  padding: 8px 10px;
  margin-bottom: 6px;
}

.edu-card {
  background: var(--c-bg-soft);
  border: 1px solid var(--c-border);
  border-radius: var(--r);
  padding: 8px 10px;
  border-left: 3px solid var(--c-accent);
}
.edu-card .ttl { font-size: 11px; font-weight: 700; margin-bottom: 4px; color: var(--c-text); }
.edu-card .body { font-size: 11px; color: var(--c-text-2); line-height: 1.5; }
.edu-card code {
  font-family: var(--ff-mono);
  font-size: 10px;
  background: var(--c-surface);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--c-primary);
}

@media (max-width: 1300px) { .cortex-row { grid-template-columns: repeat(3, 1fr); } }
</style>
