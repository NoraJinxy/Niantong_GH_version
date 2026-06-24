<template>
  <WorkbenchShell active-key="statistics" active-top-key="stats">
    <div class="page__header" style="margin: 0; padding: var(--s-4) var(--s-5) 0">
      <div>
        <h1 class="page__title">统计分析</h1>
        <p class="page__subtitle">从结果中提取统计推断 · 5 类 20+ 检验方法 · 含 Cluster Permutation 与 LME</p>
      </div>
    </div>

    <div class="stat-shell">
      <aside class="method-tree">
        <div class="row gap-2" style="background: var(--c-bg-tint); padding: 6px 10px; border-radius: 6px; margin-bottom: var(--s-3)">
          <AppIcon name="search" :size="14" />
          <input class="input input--sm" style="border: 0; background: transparent; height: 24px; padding: 0" placeholder="搜索检验方法…" />
        </div>

        <details v-for="group in methodGroups" :key="group.title" :open="group.open" class="mt-2">
          <summary>{{ group.title }}</summary>
          <div
            v-for="item in group.items"
            :key="item.name"
            class="method-item"
            :class="{ 'is-on': item.active }"
          >
            {{ item.name }}<span v-if="item.active"> ●</span>
          </div>
        </details>
      </aside>

      <section class="stat-center">
        <div class="config-panel">
          <div class="row row--between mb-3">
            <h3 style="margin: 0">配对 t 检验 — 配置</h3>
            <span class="muted text-sm">配对观测，差值近似正态</span>
          </div>

          <div class="grid grid-2">
            <div class="field">
              <label class="field__label">数据源</label>
              <select class="select">
                <option>erp_result · P300</option>
                <option>psd_result · resting</option>
              </select>
            </div>
            <div class="field">
              <label class="field__label">通道</label>
              <select class="select">
                <option>Pz（推荐）</option>
                <option>Cz</option>
                <option>FCz</option>
                <option>全部 EEG</option>
              </select>
            </div>
            <div class="field">
              <label class="field__label">条件 A</label>
              <select class="select"><option>target</option><option>standard</option></select>
            </div>
            <div class="field">
              <label class="field__label">条件 B</label>
              <select class="select"><option>standard</option><option>novel</option></select>
            </div>
            <div class="field">
              <label class="field__label">时间窗（s）</label>
              <div class="row gap-2">
                <input class="input" value="0.28" />
                <span class="muted">—</span>
                <input class="input" value="0.42" />
              </div>
            </div>
            <div class="field">
              <label class="field__label">尾检验</label>
              <select class="select">
                <option>双侧</option>
                <option>单侧（大于）</option>
                <option>单侧（小于）</option>
              </select>
            </div>
          </div>

          <div class="alert alert--warning mt-3">
            <AppIcon class="alert__icon" name="admin" :size="18" />
            <div>
              <div class="alert__title">假设检查 · Shapiro-Wilk W = 0.961, p = 0.32</div>
              <div class="alert__body">差值满足正态性假设 · 配对 t 检验适用 · 否则建议改用 Wilcoxon 符号秩</div>
            </div>
          </div>

          <div class="row row--end gap-2 mt-3">
            <button class="btn">重置</button>
            <button class="btn btn--primary">
              <IconLine name="play" :size="14" /> 运行检验
            </button>
          </div>
        </div>

        <div class="result-panel">
          <div class="tabs">
            <button
              v-for="tab in resultTabs"
              :key="tab.key"
              type="button"
              class="tabs__item"
              :class="{ 'is-active': tab.key === activeResultTab }"
              @click="activeResultTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <div v-if="activeResultTab === 'table'">
            <div class="stat-grade mb-3">
              <div class="row gap-3" style="flex-wrap: wrap; align-items: flex-end">
                <div>
                  <div class="muted text-sm">t 统计量</div>
                  <div class="stat-grade__big">−2.85</div>
                </div>
                <div>
                  <div class="muted text-sm">df</div>
                  <div class="stat-grade__big">29</div>
                </div>
                <div>
                  <div class="muted text-sm">p 值</div>
                  <div class="stat-grade__big" style="color: var(--c-success)">
                    0.008<span class="stat-grade__star">⋆⋆</span>
                  </div>
                </div>
                <div>
                  <div class="muted text-sm">Cohen's d</div>
                  <div class="stat-grade__big">−0.52</div>
                </div>
                <div>
                  <div class="muted text-sm">95% CI</div>
                  <div class="stat-grade__mid">[−0.91, −0.13]</div>
                </div>
              </div>
            </div>
            <div class="muted text-sm">
              假设检验：H₀ 表示两条件均值无差异。结果显示 target 条件下 Pz 通道在 280-420 ms 的均幅显著高于 standard 条件（t(29)=−2.85, p=0.008, Cohen's d=−0.52）。
            </div>
          </div>

          <div v-else-if="activeResultTab === 'viz'">
            <div class="grid grid-2">
              <div class="card" style="padding: var(--s-3)">
                <strong class="mb-2" style="display: block">小提琴图</strong>
                <svg viewBox="0 0 320 200" style="width: 100%">
                  <g transform="translate(80,180)">
                    <path
                      d="M0 0 Q-30 -50 -10 -90 Q0 -120 0 -160 Q0 -120 10 -90 Q30 -50 0 0 z"
                      fill="rgba(46,107,255,.3)" stroke="var(--c-primary)" stroke-width="1.3"
                    />
                    <line x1="-30" y1="-90" x2="30" y2="-90" stroke="var(--c-primary)" stroke-width="2" />
                    <text x="0" y="20" font-size="11" text-anchor="middle">target</text>
                  </g>
                  <g transform="translate(220,180)">
                    <path
                      d="M0 0 Q-25 -40 -5 -70 Q0 -100 0 -130 Q0 -100 5 -70 Q25 -40 0 0 z"
                      fill="rgba(0,194,168,.3)" stroke="var(--c-accent)" stroke-width="1.3"
                    />
                    <line x1="-25" y1="-70" x2="25" y2="-70" stroke="var(--c-accent)" stroke-width="2" />
                    <text x="0" y="20" font-size="11" text-anchor="middle">standard</text>
                  </g>
                  <line x1="80" y1="20" x2="220" y2="20" stroke="var(--c-text)" stroke-width="1" />
                  <line x1="80" y1="20" x2="80" y2="28" stroke="var(--c-text)" stroke-width="1" />
                  <line x1="220" y1="20" x2="220" y2="28" stroke="var(--c-text)" stroke-width="1" />
                  <text x="150" y="14" font-size="12" text-anchor="middle">⋆⋆ p = 0.008</text>
                </svg>
              </div>
              <div class="card" style="padding: var(--s-3)">
                <strong class="mb-2" style="display: block">差异波 + 显著区域</strong>
                <svg viewBox="0 0 320 200" style="width: 100%">
                  <line x1="80" y1="0" x2="80" y2="200" stroke="var(--c-text-3)" stroke-dasharray="3 3" />
                  <line x1="0" y1="100" x2="320" y2="100" stroke="var(--c-border)" />
                  <rect x="120" y="0" width="60" height="200" fill="var(--c-success-soft)" />
                  <path
                    d="M0 100 L80 100 L120 80 L150 50 L180 80 L220 95 L320 100"
                    stroke="var(--c-primary)" stroke-width="2" fill="none"
                  />
                </svg>
              </div>
            </div>
          </div>

          <div v-else>
            <h3 style="margin: 0 0 12px">统计报告</h3>
            <div class="card card--flat report-card">
              <p>
                <strong>方法.</strong> 对 30 名被试在 target 与 standard 条件下 Pz 通道 280-420 ms 的均幅做配对 t 检验，差值的 Shapiro-Wilk 检验未拒绝正态性假设（W=0.961, p=0.32）。
              </p>
              <p>
                <strong>结果.</strong> target 条件 Pz 均幅（M=8.23, SD=3.41 μV）显著大于 standard 条件（M=4.18, SD=2.18 μV）：t(29)=−2.85, p=0.008, Cohen's d=−0.52, 95% CI [−0.91, −0.13]。
              </p>
              <p>
                <strong>结论.</strong> 上肢康复任务下 P300 振幅在 target 与 standard 条件间存在中等效应量的统计显著差异。
              </p>
            </div>
            <div class="row gap-2 mt-3">
              <button class="btn btn--sm"><IconLine name="save" :size="14" /> 导出 HTML</button>
              <button class="btn btn--sm"><IconLine name="save" :size="14" /> 导出 PDF</button>
              <button class="btn btn--sm"><IconLine name="clipboard" :size="14" /> 复制为 LaTeX</button>
            </div>
          </div>
        </div>
      </section>

      <aside class="result-panel">
        <h3 style="margin: 0 0 8px">附加分析</h3>
        <div class="muted text-sm mb-3">同一数据可一键做多重比较校正</div>

        <div class="card card--flat addon-card">
          <div class="row row--between mb-2">
            <strong style="font-size: 13px">多通道 p 值校正</strong>
            <select class="select input--sm" style="width: 110px">
              <option>FDR (BH)</option>
              <option>Bonferroni</option>
              <option>Holm</option>
            </select>
          </div>
          <table class="table table--compact pval-tab" style="margin: 0">
            <thead>
              <tr><th>通道</th><th>原 p</th><th>校正 p</th><th></th></tr>
            </thead>
            <tbody>
              <tr class="is-sig"><td>Pz</td><td>0.001</td><td>0.006</td><td>⋆⋆</td></tr>
              <tr class="is-sig"><td>CPz</td><td>0.003</td><td>0.012</td><td>⋆</td></tr>
              <tr><td>Cz</td><td>0.018</td><td>0.054</td><td>n.s.</td></tr>
              <tr><td>P3</td><td>0.082</td><td>0.164</td><td>n.s.</td></tr>
              <tr><td>P4</td><td>0.105</td><td>0.175</td><td>n.s.</td></tr>
            </tbody>
          </table>
          <div class="muted text-sm mt-2">原始显著 5 → 校正后 2</div>
        </div>

        <div class="card card--flat addon-card" style="margin-top: var(--s-3)">
          <strong style="font-size: 13px; display: block; margin-bottom: var(--s-2)">Cluster Permutation</strong>
          <div class="muted text-sm mb-2">控制族错误率，对脑电时空数据最常用</div>
          <table class="table table--compact" style="margin: 0; font-size: 12px">
            <tbody>
              <tr><td>簇形成阈值</td><td>p &lt; 0.05</td></tr>
              <tr><td>排列次数</td><td>1024</td></tr>
              <tr><td>邻接</td><td>时间 + 空间</td></tr>
            </tbody>
          </table>
          <div class="alert alert--success mt-3" style="padding: 8px; margin: 0">
            <div>
              <strong>Cluster 1</strong>
              <div class="muted text-sm">280-420 ms · Pz/CPz/P4</div>
              <div class="muted text-sm">Σt=156.3 · p=0.004（校正）</div>
            </div>
          </div>
          <div class="alert alert--warning mt-2" style="padding: 8px; margin: 0">
            <div>
              <strong>Cluster 2</strong>
              <div class="muted text-sm">500-620 ms · Fz/FCz/F4</div>
              <div class="muted text-sm">Σt=89.7 · p=0.032</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'

const methodGroups = [
  {
    title: '📊 描述性统计', open: true,
    items: [{ name: 'Describe 描述统计' }],
  },
  {
    title: '📈 参数检验', open: true,
    items: [
      { name: '单样本 t 检验' },
      { name: '配对 t 检验', active: true },
      { name: '独立样本 t 检验' },
      { name: '单因素 ANOVA' },
      { name: '重复测量 ANOVA' },
      { name: '混合设计 ANOVA' },
      { name: '线性回归' },
      { name: '逻辑回归' },
      { name: '相关分析 (Pearson/Spearman)' },
    ],
  },
  {
    title: '🔢 非参数检验', open: false,
    items: [
      { name: 'Wilcoxon 符号秩' },
      { name: 'Mann-Whitney U' },
      { name: 'Kruskal-Wallis' },
      { name: 'Friedman' },
    ],
  },
  {
    title: '🎯 多重比较校正', open: true,
    items: [
      { name: 'Bonferroni' },
      { name: 'Holm-Bonferroni' },
      { name: 'FDR (BH)' },
      { name: 'FDR (BY)' },
      { name: 'Cluster Permutation', active: true },
      { name: 'TFCE' },
      { name: 'Max-T' },
    ],
  },
  {
    title: '🧩 混合效应模型', open: false,
    items: [
      { name: '线性混合效应 (LME)' },
      { name: '广义线性混合效应 (GLME)' },
    ],
  },
  {
    title: '📐 效应量', open: false,
    items: [
      { name: "Cohen's d" },
      { name: "Hedges' g" },
      { name: 'η² / η²p' },
      { name: 'Bootstrap 置信区间' },
    ],
  },
]

const resultTabs = [
  { key: 'table', label: '📋 统计表' },
  { key: 'viz', label: '📊 可视化' },
  { key: 'report', label: '📄 报告' },
] as const
const activeResultTab = ref<'table' | 'viz' | 'report'>('table')
</script>

<style scoped>
:deep(.page) { padding: 0; }
.stat-shell {
  display: grid;
  grid-template-columns: 260px 1fr 320px;
  gap: var(--s-3);
  padding: var(--s-3) var(--s-4) var(--s-4);
  height: calc(100vh - var(--header-h));
}
@media (max-width: 1100px) {
  .stat-shell { grid-template-columns: 1fr; height: auto; }
}
.method-tree {
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-3);
  overflow-y: auto;
}
.method-tree summary {
  cursor: pointer;
  padding: 6px 0;
  font-weight: 600;
  font-size: 13px;
  color: var(--c-text);
}
.method-tree .method-item {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--c-text-2);
}
.method-tree .method-item:hover { background: var(--c-bg-tint); color: var(--c-text); }
.method-tree .method-item.is-on {
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-weight: 600;
}

.stat-center {
  display: flex;
  flex-direction: column;
  gap: var(--s-3);
  overflow-y: auto;
  min-width: 0;
}
.config-panel,
.result-panel {
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-4);
  overflow-y: auto;
}
.stat-grade {
  background: linear-gradient(135deg, var(--c-primary-soft), #fff);
  border-left: 4px solid var(--c-primary);
  padding: var(--s-3) var(--s-4);
  border-radius: 0 var(--r) var(--r) 0;
}
.stat-grade__big {
  font-size: 24px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.stat-grade__star { font-size: 14px; }
.stat-grade__mid { font-size: 18px; font-weight: 600; }
.report-card {
  border: 1px solid var(--c-border);
  padding: var(--s-4);
  font-size: 13px;
  line-height: 1.7;
}
.addon-card {
  border: 1px solid var(--c-border);
  padding: var(--s-3);
}
.pval-tab td { font-family: var(--ff-mono); font-size: 12px; }
.pval-tab tbody tr.is-sig { background: var(--c-success-soft); }
</style>
