<template>
  <WorkbenchShell active-key="ml" active-top-key="ai">
    <div class="ml-toolbar">
      <span class="text-mono muted"><IconLine name="folder" :size="16" /></span>
      <input class="input" value="P300 分类器 — SVM-RBF" style="width: 240px; height: 32px" />
      <span class="badge badge--success">已训练</span>
      <div style="flex: 1"></div>
      <span class="muted text-sm">最近训练：</span>
      <span class="text-sm">11:42 · 45.2s · LOSO-CV · 30 被试</span>
    </div>

    <div class="ml-shell">
      <section class="ml-palette">
        <template v-for="group in palette" :key="group.cat">
          <div class="palette-cat"><IconLine name="chevronDown" :size="12" /> {{ group.cat }}</div>
          <div v-for="item in group.items" :key="item.name" class="node-item" :class="item.cat">
            <span class="swatch"></span>{{ item.name }}
          </div>
        </template>
      </section>

      <section class="ml-canvas">
        <div class="canvas-bg">
          <div class="pl-node is-success" style="left: 30px; top: 60px">
            <div class="pl-node__head"><IconLine name="folder" :size="14" /> LoadData</div>
            <div class="pl-node__body">SSVEP · 18 sub · 4 类</div>
            <span class="pl-node__port out"></span>
          </div>
          <div class="pl-node is-success" style="left: 220px; top: 60px">
            <div class="pl-node__head"><IconLine name="settings" :size="14" /> Feature</div>
            <div class="pl-node__body">CSP + Bandpower</div>
            <span class="pl-node__port in"></span>
            <span class="pl-node__port out"></span>
          </div>
          <div class="pl-node is-success is-active" style="left: 410px; top: 60px">
            <div class="pl-node__head"><IconLine name="brain" :size="14" /> SVM</div>
            <div class="pl-node__body">RBF · C=1.0 · γ=scale</div>
            <span class="pl-node__port in"></span>
            <span class="pl-node__port out"></span>
          </div>
          <div class="pl-node is-success" style="left: 600px; top: 60px">
            <div class="pl-node__head"><IconLine name="barChart" :size="14" /> Evaluate</div>
            <div class="pl-node__body">LOSO-CV · 18 折</div>
            <span class="pl-node__port in"></span>
            <span class="pl-node__port out"></span>
          </div>
          <div class="pl-node is-success" style="left: 790px; top: 60px">
            <div class="pl-node__head"><IconLine name="search" :size="14" /> SHAP</div>
            <div class="pl-node__body">100 样本</div>
            <span class="pl-node__port in"></span>
          </div>

          <div class="pl-node" style="left: 220px; top: 200px">
            <div class="pl-node__head"><IconLine name="target" :size="14" /> Optuna</div>
            <div class="pl-node__body">TPE · 100 试验</div>
            <span class="pl-node__port in"></span>
            <span class="pl-node__port out"></span>
          </div>

          <svg style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none">
            <defs>
              <marker id="ar-ok" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0 0L10 5L0 10z" fill="var(--c-success)" />
              </marker>
            </defs>
            <path stroke="var(--c-success)" stroke-width="1.6" fill="none" d="M162 90 L220 90" marker-end="url(#ar-ok)" />
            <path stroke="var(--c-success)" stroke-width="1.6" fill="none" d="M352 90 L410 90" marker-end="url(#ar-ok)" />
            <path stroke="var(--c-success)" stroke-width="1.6" fill="none" d="M542 90 L600 90" marker-end="url(#ar-ok)" />
            <path stroke="var(--c-success)" stroke-width="1.6" fill="none" d="M732 90 L790 90" marker-end="url(#ar-ok)" />
            <path stroke="var(--c-text-3)" stroke-width="1.4" stroke-dasharray="4 3" fill="none" d="M352 90 C 380 130, 200 180, 220 230" marker-end="url(#ar-ok)" />
          </svg>
        </div>
      </section>

      <section class="ml-results">
        <h3 class="mb-3 ml-results__title" style="margin: 0 0 var(--s-3)">
          <IconLine name="barChart" :size="18" /> 训练结果
        </h3>
        <div class="card mb-3 result-summary">
          <div class="muted text-sm">SVM (RBF) · LOSO-CV</div>
          <div class="row gap-3 mt-2">
            <div>
              <div class="muted text-sm">准确率</div>
              <div class="result-summary__big">0.823<span class="result-summary__pm"> ± 0.045</span></div>
            </div>
            <div>
              <div class="muted text-sm">AUC</div>
              <div class="result-summary__big" style="color: var(--c-success)">0.891</div>
            </div>
          </div>
        </div>

        <div class="card mb-3" style="padding: var(--s-3)">
          <strong style="display: block; margin-bottom: var(--s-2)">分类指标</strong>
          <table class="table table--compact" style="margin: 0; font-size: 12px">
            <tbody>
              <tr><td>精确率</td><td>0.851</td></tr>
              <tr><td>召回率</td><td>0.796</td></tr>
              <tr><td>F1 分数</td><td>0.822</td></tr>
              <tr><td>AUC-ROC</td><td><strong>0.891</strong></td></tr>
              <tr><td>耗时</td><td>45.2 s</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card mb-3" style="padding: var(--s-3)">
          <strong style="display: block; margin-bottom: var(--s-2)">混淆矩阵</strong>
          <div class="conf-mat">
            <div></div>
            <div class="head">P̂ Target</div>
            <div class="head">P̂ Standard</div>
            <div class="head">Target</div>
            <div class="conf-mat__hit">241</div>
            <div>59</div>
            <div class="head">Standard</div>
            <div>48</div>
            <div class="conf-mat__hit">252</div>
          </div>
        </div>

        <div class="card mb-3" style="padding: var(--s-3)">
          <strong style="display: block; margin-bottom: var(--s-2)">ROC 曲线</strong>
          <div class="roc">
            <svg viewBox="0 0 200 200" style="width: 100%">
              <line x1="0" y1="200" x2="200" y2="0" stroke="var(--c-text-3)" stroke-dasharray="3 3" />
              <path d="M0 200 Q20 80 50 50 Q90 30 130 20 L200 0" stroke="var(--c-primary)" stroke-width="2" fill="none" />
              <path d="M0 200 Q20 80 50 50 Q90 30 130 20 L200 0 L200 200 L0 200z" fill="var(--c-primary-soft)" />
              <text x="100" y="180" font-size="10" text-anchor="middle">AUC = 0.891</text>
            </svg>
          </div>
        </div>

        <div class="card" style="padding: var(--s-3)">
          <strong style="display: block; margin-bottom: var(--s-2)">SHAP 特征重要性</strong>
          <div class="shap-list">
            <div v-for="feat in shapFeatures" :key="feat.name" class="shap-row">
              <span>{{ feat.name }}</span>
              <div class="shap-bar"><div class="shap-bar__fill" :style="{ width: feat.width }"></div></div>
              <span class="shap-val">{{ feat.value }}</span>
            </div>
          </div>
        </div>

        <details class="mt-3">
          <summary class="saliency-summary">显著性图（Saliency Map）</summary>
          <div class="muted text-sm mt-2">时间×通道热图，亮处=模型关注的判别区域</div>
          <svg viewBox="0 0 240 80" class="saliency-svg">
            <rect x="0" y="0" width="240" height="20" fill="rgba(46,107,255,.15)" />
            <rect x="80" y="0" width="80" height="20" fill="rgba(46,107,255,.7)" />
            <rect x="0" y="20" width="240" height="20" fill="rgba(46,107,255,.2)" />
            <rect x="60" y="20" width="120" height="20" fill="rgba(46,107,255,.85)" />
            <rect x="0" y="40" width="240" height="20" fill="rgba(46,107,255,.18)" />
            <rect x="80" y="40" width="80" height="20" fill="rgba(46,107,255,.7)" />
            <rect x="0" y="60" width="240" height="20" fill="rgba(46,107,255,.1)" />
            <text x="0" y="14" font-size="9" fill="var(--c-text-2)">Fz</text>
            <text x="0" y="34" font-size="9" fill="var(--c-text-2)">Cz</text>
            <text x="0" y="54" font-size="9" fill="var(--c-text-2)">Pz</text>
            <text x="0" y="74" font-size="9" fill="var(--c-text-2)">Oz</text>
          </svg>
          <div class="row row--between text-sm muted mt-1"><span>0 ms</span><span>500</span><span>1000 ms</span></div>
        </details>

        <div class="alert alert--info mt-3">
          <AppIcon class="alert__icon" name="admin" :size="18" />
          <div>
            <div class="alert__title">推荐：尝试 AutoML</div>
            <div class="alert__body">使用 Optuna TPE 搜索 100 次，可能进一步提升 2-5% 准确率。</div>
          </div>
        </div>
      </section>
    </div>

    <div class="ml-dock">
      <span style="color: var(--c-success); display: inline-flex; align-items: center">
        <IconLine name="check" :size="16" />
      </span>
      <strong>SVM 训练已完成 · 11:42</strong>
      <span class="muted text-sm">输出 1 个模型 / SHAP 解释 · 评估指标见右栏</span>
      <div style="flex: 1"></div>
      <button class="btn btn--sm">查看日志</button>
      <button class="btn btn--sm">下载 .pkl 模型</button>
      <button class="btn btn--sm btn--primary">部署到推理服务</button>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'

const palette = [
  {
    cat: '数据',
    items: [
      { name: '📂 LoadData', cat: 'cat-data' },
      { name: '📤 Export', cat: 'cat-data' },
    ],
  },
  {
    cat: '特征提取',
    items: [
      { name: '时域 (Hjorth/熵)', cat: 'cat-prep' },
      { name: '频域 (Bandpower)', cat: 'cat-prep' },
      { name: '时频 (TFR)', cat: 'cat-prep' },
      { name: '空间 (CSP / PCA)', cat: 'cat-prep' },
    ],
  },
  {
    cat: '模型',
    items: [
      { name: '🧠 SVM', cat: 'cat-ml' },
      { name: '🌳 Random Forest', cat: 'cat-ml' },
      { name: '⚡ XGBoost', cat: 'cat-ml' },
      { name: '📍 k-NN', cat: 'cat-ml' },
    ],
  },
  {
    cat: '深度学习',
    items: [
      { name: '🧬 EEGNet', cat: 'cat-ml' },
      { name: '🧠 CNN', cat: 'cat-ml' },
      { name: '↻ LSTM', cat: 'cat-ml' },
      { name: '🤖 Transformer', cat: 'cat-ml' },
    ],
  },
  {
    cat: '评估',
    items: [
      { name: 'CrossVal', cat: 'cat-stat' },
      { name: 'Metrics', cat: 'cat-stat' },
    ],
  },
  {
    cat: '可解释性',
    items: [
      { name: '🔍 SHAP', cat: 'cat-viz' },
      { name: '🎯 LIME', cat: 'cat-viz' },
      { name: '👁 Saliency', cat: 'cat-viz' },
    ],
  },
  {
    cat: 'AutoML',
    items: [{ name: '🔭 Optuna 搜索', cat: 'cat-analyse' }],
  },
]

const shapFeatures = [
  { name: 'Cz_θ_power', width: '80%', value: '.42' },
  { name: 'Fz_α_power', width: '62%', value: '.31' },
  { name: 'Pz_Hjorth_mob', width: '48%', value: '.24' },
  { name: 'Pz_β_power', width: '36%', value: '.18' },
  { name: 'CSP_comp_1', width: '30%', value: '.15' },
]
</script>

<style scoped>
:deep(.page) { padding: 0; }
.ml-toolbar {
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 0 var(--s-4);
  border-bottom: 1px solid var(--c-border);
  background: rgba(255, 255, 255, .92);
}
.ml-shell {
  display: grid;
  grid-template-columns: 220px 1fr 320px;
  height: calc(100vh - var(--header-h) - 56px - 56px);
  min-height: 480px;
}
.ml-shell > section {
  padding: var(--s-3);
  overflow-y: auto;
  border-left: 1px solid var(--c-border);
}
.ml-shell > section:first-child { border-left: 0; }
.palette-cat {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-3);
  text-transform: uppercase;
  padding: 8px 4px 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.node-item {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: 6px 10px;
  border-radius: var(--r);
  font-size: 12px;
  color: var(--c-text);
  cursor: grab;
  border: 1px solid transparent;
  transition: all var(--t-fast);
}
.node-item:hover { background: var(--c-bg-tint); border-color: var(--c-border); }
.node-item .swatch { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.node-item.cat-data .swatch { background: #2E6BFF; }
.node-item.cat-prep .swatch { background: #10B981; }
.node-item.cat-analyse .swatch { background: #F59E0B; }
.node-item.cat-stat .swatch { background: #8B5CF6; }
.node-item.cat-viz .swatch { background: #F97316; }
.node-item.cat-ml .swatch { background: #EF4444; }

.ml-canvas {
  background: var(--c-bg-soft);
  padding: 0;
  position: relative;
  overflow: auto;
  min-height: 540px;
}
.canvas-bg {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(var(--c-bg-tint) 1px, transparent 1px) 0 0/20px 20px,
    linear-gradient(90deg, var(--c-bg-tint) 1px, transparent 1px) 0 0/20px 20px,
    var(--c-bg-soft);
  min-height: 540px;
}
.pl-node {
  position: absolute;
  background: #fff;
  border: 1.5px solid var(--c-border-2);
  border-radius: 10px;
  min-width: 132px;
  box-shadow: var(--shadow-sm);
  font-size: 12px;
  user-select: none;
}
.pl-node.is-active { border-color: var(--c-primary); box-shadow: 0 0 0 3px var(--c-primary-soft); }
.pl-node.is-success { border-color: var(--c-success); }
.pl-node__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-weight: 600;
  color: var(--c-text);
  border-bottom: 1px dashed var(--c-border);
}
.ml-results__title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--c-text);
}
.pl-node__body { padding: 6px 10px; color: var(--c-text-2); font-size: 11px; }
.pl-node__port {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--c-primary);
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px var(--c-border-strong);
}
.pl-node__port.in { left: -5px; top: 50%; transform: translateY(-50%); }
.pl-node__port.out { right: -5px; top: 50%; transform: translateY(-50%); }

.result-summary {
  padding: var(--s-3);
  background: linear-gradient(135deg, #ECFAF3, #fff);
  border-color: var(--c-success);
}
.result-summary__big {
  font-size: 24px;
  font-weight: 700;
}
.result-summary__pm { font-size: 12px; color: var(--c-text-3); }

.conf-mat {
  display: grid;
  grid-template-columns: 60px 1fr 1fr;
  gap: 1px;
  background: var(--c-border);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  overflow: hidden;
}
.conf-mat > div { background: #fff; padding: 8px; text-align: center; font-size: 12px; }
.conf-mat .head { background: var(--c-bg-soft); font-weight: 600; }
.conf-mat__hit { background: #ECFAF3; color: var(--c-success); font-weight: 700; }

.roc {
  background: linear-gradient(180deg, #fff, var(--c-bg-soft));
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 12px;
}

.shap-list { font-family: var(--ff-mono); font-size: 11px; }
.shap-row {
  display: grid;
  grid-template-columns: 140px 1fr 36px;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
  color: var(--c-text-2);
}
.shap-bar { background: var(--c-bg-tint); height: 10px; border-radius: 4px; overflow: hidden; }
.shap-bar__fill { background: var(--c-primary); height: 100%; border-radius: 4px; }
.shap-val { text-align: right; }

.saliency-summary {
  cursor: pointer;
  color: var(--c-primary);
  font-size: 13px;
}
.saliency-svg {
  width: 100%;
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  margin-top: 6px;
}

.ml-dock {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 10px var(--s-5);
  background: rgba(255, 255, 255, .95);
  backdrop-filter: blur(8px);
  border-top: 1px solid var(--c-border);
  box-shadow: 0 -4px 14px rgba(27, 41, 64, .06);
  z-index: 5;
}

@media (max-width: 1100px) {
  .ml-shell { grid-template-columns: 1fr; height: auto; }
  .ml-shell > section { border-left: 0; border-top: 1px solid var(--c-border); }
}
</style>
