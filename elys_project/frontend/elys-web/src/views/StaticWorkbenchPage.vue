<template>
  <WorkbenchShell :active-key="page.navKey" :active-top-key="activeTopKey">
    <div class="page__header module-hero">
      <div class="module-hero__copy">
        <span class="badge badge--primary">
          <span class="dot"></span>{{ page.eyebrow }}
        </span>
        <div class="module-hero__title-row">
          <div class="module-hero__icon">
            <AppIcon :name="page.icon" :size="24" />
          </div>
          <h1 class="page__title">{{ page.title }}</h1>
        </div>
        <p class="page__subtitle">{{ page.description }}</p>
      </div>
      <div class="module-hero__status">
        <span class="badge badge--outline">当前状态</span>
        <strong>{{ page.status }}</strong>
      </div>
    </div>

    <div class="grid grid-4 mb-5">
      <div
        v-for="metric in page.metrics"
        :key="metric.label"
        class="stat"
        :class="metricClass(metric.tone)"
      >
        <div class="stat__label">{{ metric.label }}</div>
        <div class="stat__value">{{ metric.value }}</div>
        <div class="stat__delta">{{ metric.hint }}</div>
      </div>
    </div>

    <section class="module-stage mb-5">
      <div class="module-stage__visual">
        <div class="module-stage__bar">
          <strong>{{ page.title }}</strong>
          <span>Static Preview</span>
        </div>

        <div v-if="page.visualKind === 'pipeline'" class="viz-pipeline">
          <div v-for="step in page.workflow" :key="step" class="viz-node">
            <AppIcon name="check" :size="16" />
            <span>{{ step }}</span>
          </div>
        </div>

        <div v-else-if="page.visualKind === 'wave'" class="viz-wave">
          <span class="wave-line wave-line--a"></span>
          <span class="wave-line wave-line--b"></span>
          <span class="wave-line wave-line--c"></span>
          <span class="wave-axis wave-axis--x"></span>
          <span class="wave-axis wave-axis--y"></span>
        </div>

        <div v-else-if="page.visualKind === 'heatmap'" class="viz-heatmap">
          <span v-for="i in 48" :key="i" :class="`heat-cell heat-cell--${(i % 8) + 1}`"></span>
        </div>

        <div v-else-if="page.visualKind === 'network'" class="viz-network">
          <span class="net-edge e1"></span>
          <span class="net-edge e2"></span>
          <span class="net-edge e3"></span>
          <span class="net-edge e4"></span>
          <span class="net-node n1"></span>
          <span class="net-node n2"></span>
          <span class="net-node n3"></span>
          <span class="net-node n4"></span>
          <span class="net-node n5"></span>
        </div>

        <div v-else-if="page.visualKind === 'brain'" class="viz-brain">
          <div class="brain-map brain-map--a"></div>
          <div class="brain-map brain-map--b"></div>
          <div class="brain-map brain-map--c"></div>
          <div class="brain-map brain-map--d"></div>
        </div>

        <div v-else-if="page.visualKind === 'table'" class="viz-table">
          <div class="viz-table__row viz-table__head">
            <span>变量</span><span>均值差</span><span>p(FDR)</span><span>效应量</span>
          </div>
          <div class="viz-table__row">
            <span>P300 Amp</span><span>3.4</span><span>0.012</span><span>0.72</span>
          </div>
          <div class="viz-table__row">
            <span>Alpha Power</span><span>1.8</span><span>0.041</span><span>0.45</span>
          </div>
          <div class="viz-table__row">
            <span>Global Eff.</span><span>0.06</span><span>0.089</span><span>0.31</span>
          </div>
        </div>

        <div v-else-if="page.visualKind === 'figure'" class="viz-figure">
          <div class="figure-panel is-wide"></div>
          <div class="figure-panel"></div>
          <div class="figure-panel is-heat"></div>
          <div class="figure-caption"></div>
        </div>

        <div v-else-if="page.visualKind === 'ml'" class="viz-ml">
          <div class="roc-card">
            <span class="roc-line"></span>
          </div>
          <div class="feature-bars">
            <span style="height: 82%"></span>
            <span style="height: 64%"></span>
            <span style="height: 52%"></span>
            <span style="height: 41%"></span>
            <span style="height: 33%"></span>
          </div>
        </div>

        <div v-else-if="page.visualKind === 'gallery'" class="viz-gallery">
          <RouterLink
            v-for="action in page.actions"
            :key="action.key"
            class="gallery-tile"
            :class="{ 'is-preview': isWorkbenchNavPreview(action) }"
            :to="action.to"
            :title="isWorkbenchNavPreview(action) ? `${action.label}：静态预览，功能未接入` : action.label"
          >
            <AppIcon :name="action.icon" :size="22" />
            <span>{{ action.label }}</span>
            <small v-if="isWorkbenchNavPreview(action)">预览</small>
          </RouterLink>
        </div>

        <div v-else class="viz-admin">
          <div v-for="panel in page.panels" :key="panel.title" class="admin-row">
            <span>{{ panel.title }}</span>
            <strong>OK</strong>
          </div>
        </div>
      </div>

      <aside class="module-stage__steps">
        <h3>推荐流程</h3>
        <ol>
          <li v-for="step in page.workflow" :key="step">{{ step }}</li>
        </ol>
        <div v-if="page.actions?.length" class="module-actions">
          <RouterLink
            v-for="action in page.actions"
            :key="action.key"
            class="btn btn--sm"
            :class="{ 'btn--preview': isWorkbenchNavPreview(action) }"
            :to="action.to"
            :title="isWorkbenchNavPreview(action) ? `${action.label}：静态预览，功能未接入` : action.label"
          >
            <AppIcon :name="action.icon" :size="15" />
            {{ action.label }}
          </RouterLink>
        </div>
      </aside>
    </section>

    <div class="grid grid-3 mb-5">
      <div v-for="panel in page.panels" :key="panel.title" class="card module-panel">
        <div class="card__header">
          <div>
            <h3 class="card__title">{{ panel.title }}</h3>
            <div v-if="panel.caption" class="card__sub">{{ panel.caption }}</div>
          </div>
        </div>
        <ul class="module-list">
          <li v-for="item in panel.items" :key="item">
            <span class="check-dot"></span>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { getModulePage, isWorkbenchNavPreview } from '@/data/workbenchPages'

const route = useRoute()

const page = computed(() => getModulePage(String(route.meta.pageKey || 'observe')))
const activeTopKey = computed(() => {
  const key = page.value.navKey
  if (key.startsWith('view-') || key === 'observe') return 'observe'
  if (key === 'figures') return 'figure'
  if (key === 'statistics') return 'stats'
  if (key === 'ml') return 'ai'
  if (key === 'pipeline' || key === 'preprocess') return 'analysis'
  if (key === 'admin') return 'dashboard'
  return key
})

function metricClass(tone: string | undefined) {
  if (tone === 'accent') return 'stat--accent'
  if (tone === 'success') return 'stat--success'
  if (tone === 'warning') return 'stat--warn'
  if (tone === 'danger') return 'stat--danger'
  return ''
}
</script>
