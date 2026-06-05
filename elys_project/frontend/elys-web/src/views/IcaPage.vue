<template>
  <WorkbenchShell active-key="ica" active-top-key="analysis">
    <div class="ica-shell">
      <div class="ica-toolbar">
        <h1 class="page__title ica-title" style="font-size: 22px; margin: 0">
          <IconLine name="brain" :size="24" /> ICA 审核
        </h1>
        <span class="muted text-sm">采样率 250 Hz · 64 通道 · 10:32 · 20 个独立成分</span>
        <span class="qa-score is-A">A</span>
        <div style="flex: 1"></div>
        <select class="select input--sm" style="width: 160px">
          <option>按标签分组</option>
          <option>按置信度排序</option>
        </select>
        <button class="btn btn--sm">全选 Eye (3)</button>
        <button class="btn btn--sm">全选 Muscle (1)</button>
        <button class="btn btn--sm">全选 Heart (1)</button>
        <button class="btn btn--sm btn--primary">应用去除 (5)</button>
      </div>

      <div class="ica-body">
        <div class="card mb-3">
          <div class="card__header">
            <div>
              <h3 class="card__title">ICA 成分审核 · 20 个成分</h3>
              <div class="card__sub">点击卡片切换详情，颜色表示推荐操作。</div>
            </div>
            <span class="badge badge--primary">{{ keepCount }} 保留 / {{ removeCount }} 剔除 / {{ doubtCount }} 待审</span>
          </div>

          <div class="ic-grid">
            <div
              v-for="comp in components"
              :key="comp.id"
              class="ic-card"
              :class="comp.state"
              @click="selectedIc = comp.id"
            >
              <div class="topomap topomap--xs" :style="comp.topo"></div>
              <strong>{{ comp.id }}</strong>
              <div class="muted text-sm">{{ comp.label }}</div>
              <div class="text-mono text-sm" :style="{ color: comp.confColor }">
                {{ comp.confidence }} {{ comp.marker }}
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__header">
            <div>
              <h3 class="card__title">选中：{{ activeComponent.id }} · {{ activeComponent.label }}伪迹</h3>
              <div class="card__sub">详情包含地形图、时间序列、PSD 与去除前后对比。</div>
            </div>
            <span class="badge badge--danger">推荐去除</span>
          </div>

          <div class="grid grid-3">
            <div>
              <div class="panel__title">地形图（大）</div>
              <div
                class="topomap"
                style="
                  width: 180px;
                  height: 180px;
                  background:
                    radial-gradient(circle at 30% 50%, rgba(239, 68, 68, .7), transparent 30%),
                    radial-gradient(circle at 70% 50%, rgba(46, 107, 255, .7), transparent 30%),
                    #E8F0FF;
                "
              ></div>
            </div>
            <div>
              <div class="panel__title">时间序列</div>
              <svg viewBox="0 0 300 80" class="ica-mini-svg">
                <path
                  d="M0 40 Q20 10 40 40 T80 40 T120 60 T160 30 T200 50 T240 35 T280 45 T300 40"
                  stroke="var(--c-danger)"
                  stroke-width="1.4"
                  fill="none"
                />
              </svg>
              <div class="muted text-sm mt-2">幅值峰峰 ±60 μV · 周期 0.4 s</div>
            </div>
            <div>
              <div class="panel__title">PSD 谱</div>
              <svg viewBox="0 0 200 80" class="ica-mini-svg">
                <path
                  d="M0 30 L20 18 L40 12 L60 22 L80 38 L100 50 L120 60 L140 68 L160 72 L180 74 L200 75"
                  stroke="var(--c-danger)"
                  stroke-width="1.6"
                  fill="none"
                />
              </svg>
              <div class="muted text-sm mt-2">低频（1-3 Hz）强势功率，典型眼动</div>
            </div>
          </div>

          <div class="divider"></div>

          <div class="panel__title">原始 vs 去除 {{ activeComponent.id }} 后</div>
          <svg viewBox="0 0 1000 80" class="ica-wide-svg">
            <path
              d="M0 40 L60 20 L120 60 L180 20 L240 60 L300 30 L360 50 L420 35 L480 45 L540 40 L600 40 L660 40 L720 40 L780 40 L840 40 L900 40 L1000 40"
              stroke="var(--c-text-3)"
              stroke-width="1"
              fill="none"
              opacity=".6"
            />
            <path
              d="M0 40 L60 38 L120 42 L180 38 L240 42 L300 40 L360 42 L420 39 L480 41 L540 40 L600 40 L660 40 L720 40 L780 40 L840 40 L900 40 L1000 40"
              stroke="var(--c-primary)"
              stroke-width="1.4"
              fill="none"
            />
          </svg>
          <div class="row gap-3 muted text-sm mt-2">
            <span class="legend"><span class="swatch" style="background: var(--c-text-3)"></span>原始信号</span>
            <span class="legend"><span class="swatch c1"></span>去除 {{ activeComponent.id }} 后</span>
          </div>
        </div>
      </div>

      <aside class="ica-side">
        <div class="panel__title">推荐操作</div>
        <div class="alert alert--warning">
          <AppIcon class="alert__icon" name="admin" :size="18" />
          <div>
            <div class="alert__title">已自动标记 5 个待剔除成分</div>
            <div class="alert__body">眼动 3 / 肌电 1 / 心电 1，全部置信度 ≥ 0.84。</div>
          </div>
        </div>

        <div class="panel__title">伪迹类型</div>
        <ul class="ic-summary">
          <li><span class="dot" style="background: var(--c-danger)"></span>眼眨 / 眼动<strong class="ml-auto">3</strong></li>
          <li><span class="dot" style="background: var(--c-warning)"></span>肌电<strong class="ml-auto">1</strong></li>
          <li><span class="dot" style="background: var(--c-accent)"></span>心电<strong class="ml-auto">1</strong></li>
          <li><span class="dot" style="background: var(--c-text-3)"></span>不确定<strong class="ml-auto">2</strong></li>
          <li><span class="dot" style="background: var(--c-success)"></span>脑活动（保留）<strong class="ml-auto">13</strong></li>
        </ul>

        <div class="panel__title">参数</div>
        <div class="ic-param-row"><span>算法</span><strong>Infomax</strong></div>
        <div class="ic-param-row"><span>成分数</span><strong>20</strong></div>
        <div class="ic-param-row"><span>白化</span><strong>PCA · 64 → 20</strong></div>
        <div class="ic-param-row"><span>随机种子</span><strong>97</strong></div>

        <div class="panel__title">操作</div>
        <button class="btn btn--block btn--primary">
          <AppIcon name="check" :size="16" />
          应用去除 5 个成分
        </button>
        <button class="btn btn--block" style="margin-top: 8px">
          <AppIcon name="refresh" :size="16" />
          重新拟合 ICA
        </button>
        <button class="btn btn--block" style="margin-top: 8px">
          <AppIcon name="export" :size="16" />
          导出 ica.json
        </button>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'

const selectedIc = ref('IC03')

const components = [
  {
    id: 'IC01', state: 'is-remove', label: '眼眨', confidence: '0.98', marker: '✕',
    confColor: 'var(--c-danger)',
    topo: 'background: radial-gradient(circle at 50% 25%, rgba(46,107,255,.7), transparent 40%), radial-gradient(circle at 50% 75%, rgba(239,68,68,.6), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC02', state: 'is-keep', label: '脑', confidence: '0.95', marker: '✓',
    confColor: 'var(--c-success)',
    topo: 'background: radial-gradient(circle at 50% 50%, rgba(46,107,255,.5), transparent 40%), #E8F0FF;',
  },
  {
    id: 'IC03', state: 'is-remove', label: '眼动', confidence: '0.91', marker: '✕',
    confColor: 'var(--c-danger)',
    topo: 'background: radial-gradient(circle at 30% 50%, rgba(239,68,68,.7), transparent 30%), radial-gradient(circle at 70% 50%, rgba(46,107,255,.7), transparent 30%), #E8F0FF;',
  },
  {
    id: 'IC04', state: 'is-keep', label: '脑', confidence: '0.88', marker: '✓',
    confColor: 'var(--c-success)',
    topo: 'background: radial-gradient(circle at 40% 40%, rgba(0,194,168,.5), transparent 30%), radial-gradient(circle at 60% 60%, rgba(46,107,255,.4), transparent 30%), #E8F0FF;',
  },
  {
    id: 'IC05', state: 'is-keep', label: '脑', confidence: '0.85', marker: '✓',
    confColor: 'var(--c-success)',
    topo: 'background: radial-gradient(circle at 50% 30%, rgba(46,107,255,.45), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC06', state: 'is-remove', label: '肌电', confidence: '0.93', marker: '✕',
    confColor: 'var(--c-danger)',
    topo: 'background: radial-gradient(circle at 80% 80%, rgba(245,158,11,.8), transparent 30%), #E8F0FF;',
  },
  {
    id: 'IC07', state: 'is-doubt', label: '不确定', confidence: '0.62', marker: '?',
    confColor: 'var(--c-warning)',
    topo: 'background: radial-gradient(circle at 45% 55%, rgba(139,92,246,.4), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC08', state: 'is-keep', label: '脑', confidence: '0.79', marker: '✓',
    confColor: 'var(--c-success)',
    topo: 'background: radial-gradient(circle at 60% 40%, rgba(0,194,168,.4), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC09', state: 'is-remove', label: '心电', confidence: '0.84', marker: '✕',
    confColor: 'var(--c-danger)',
    topo: 'background: radial-gradient(circle at 50% 50%, rgba(239,68,68,.4), transparent 30%), #E8F0FF;',
  },
  {
    id: 'IC10', state: 'is-doubt', label: '不确定', confidence: '0.58', marker: '?',
    confColor: 'var(--c-warning)',
    topo: 'background: radial-gradient(circle at 35% 65%, rgba(245,158,11,.35), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC11', state: 'is-keep', label: '脑', confidence: '0.72', marker: '✓',
    confColor: 'var(--c-text-2)',
    topo: 'background: radial-gradient(circle at 50% 45%, rgba(46,107,255,.35), transparent 35%), #E8F0FF;',
  },
  {
    id: 'IC12', state: 'is-keep', label: '脑', confidence: '0.69', marker: '✓',
    confColor: 'var(--c-text-2)',
    topo: 'background: radial-gradient(circle at 55% 55%, rgba(0,194,168,.3), transparent 35%), #E8F0FF;',
  },
]

const keepCount = computed(() => components.filter((c) => c.state === 'is-keep').length)
const removeCount = computed(() => components.filter((c) => c.state === 'is-remove').length)
const doubtCount = computed(() => components.filter((c) => c.state === 'is-doubt').length)

const activeComponent = computed(
  () => components.find((c) => c.id === selectedIc.value) || components[2],
)
</script>

<style scoped>
:deep(.page) { padding: 0; }
.ica-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  grid-template-rows: 56px 1fr;
  gap: 0;
  min-height: calc(100vh - var(--header-h));
}
.ica-toolbar {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 0 var(--s-5);
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}
.ica-body { padding: var(--s-4); min-width: 0; }
.ica-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--c-text);
}
.ica-side {
  padding: var(--s-4);
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex;
  flex-direction: column;
  gap: var(--s-3);
}

.qa-score {
  display: inline-flex;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 11px;
}
.qa-score.is-A { background: var(--c-success-soft); color: var(--c-success); }

.ic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--s-3);
}
.ic-card {
  border: 2px solid var(--c-border);
  border-radius: var(--r-md);
  padding: var(--s-3);
  background: #fff;
  text-align: center;
  cursor: pointer;
  font-size: 12px;
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}
.ic-card:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
.ic-card.is-keep { border-color: var(--c-success); }
.ic-card.is-remove { border-color: var(--c-danger); }
.ic-card.is-doubt { border-color: var(--c-warning); }
.ic-card strong { display: block; margin: 6px 0 2px; font-size: 13px; }

.topomap {
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 35%, rgba(46, 107, 255, .6), transparent 40%),
    radial-gradient(circle at 65% 60%, rgba(239, 68, 68, .5), transparent 35%),
    radial-gradient(circle at 50% 50%, #E8F0FF 0%, #F7F9FC 70%);
  border: 1.5px solid var(--c-border-strong);
  position: relative;
  margin: 0 auto;
}
.topomap--xs { width: 60px; height: 60px; }
.topomap::before, .topomap::after { content: ''; position: absolute; background: var(--c-border-strong); }
.topomap::before { top: -6px; left: 50%; width: 12px; height: 12px; border-radius: 50% 50% 0 0; transform: translateX(-50%); }
.topomap::after { left: -4px; top: 30%; width: 8px; height: 18px; border-radius: 4px; }

.panel__title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--c-text-3);
  letter-spacing: .06em;
  margin-bottom: var(--s-2);
}
.ica-mini-svg, .ica-wide-svg {
  width: 100%;
  background: var(--c-bg-soft);
  border-radius: 6px;
  margin-top: var(--s-2);
}

.legend { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
.legend .swatch { width: 12px; height: 12px; border-radius: 3px; }
.legend .swatch.c1 { background: var(--c-primary); }

.ic-summary {
  list-style: none;
  margin: 0 0 var(--s-3);
  padding: 0;
  display: grid;
  gap: 6px;
}
.ic-summary li {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  font-size: 13px;
}
.ic-summary li .dot { width: 8px; height: 8px; border-radius: 50%; }
.ic-summary li strong { font-family: var(--ff-mono); }
.ml-auto { margin-left: auto; }

.ic-param-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--c-border);
  color: var(--c-text-2);
}
.ic-param-row:last-of-type { border-bottom: 0; margin-bottom: var(--s-3); }
.ic-param-row strong { color: var(--c-text); font-family: var(--ff-mono); }

@media (max-width: 960px) {
  .ica-shell { grid-template-columns: 1fr; }
  .ica-side { border-left: 0; border-top: 1px solid var(--c-border); }
}
</style>
