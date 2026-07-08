<template>
  <div class="stats-page">
    <PerfBadge :perf="probe.perf" />
    <header class="sp-head">
      <div class="sp-id">
        <span class="sp-badge">STAT</span>
        <div>
          <div class="sp-title">{{ contrastLabel }}<span class="sp-region">统计比较</span></div>
          <div class="sp-sub" v-if="data">
            <span class="sp-tag">{{ baseLabel }}</span>
            <span class="sp-tag">{{ designLabel }}</span>
            <span class="sp-tag">{{ methodLabel }}</span>
            <span class="sp-tag" v-if="data.condition">{{ data.condition }}</span>
            <span class="sp-tag" v-if="data.method === 'cluster'">{{ clusterModeLabel }}</span>
            <span class="sp-tag" v-if="data.method === 'pointwise'">{{ correctionLabel }}</span>
            <span class="sp-tag">α = {{ data.alpha }}</span>
            <span class="sp-tag">n: {{ data.n_a }} vs {{ data.n_b }}</span>
          </div>
        </div>
      </div>
      <button class="sp-btn" @click="load()" :disabled="loading">刷新</button>
    </header>

    <section class="sp-overview" v-if="data">
      <div class="sp-condition-strip" v-if="relatedOutputs.length > 1">
        <span class="sp-section-label">条件</span>
        <button
          v-for="item in relatedOutputs"
          :key="item.study_output_id"
          class="sp-condition"
          :class="{ 'is-sel': item.study_output_id === activeOutputId, 'is-sig': item.has_significant }"
          @click="selectOutput(item.study_output_id)"
        >
          <span>{{ outputLabel(item) }}</span>
          <b>{{ outputBadge(item) }}</b>
        </button>
      </div>

      <div class="sp-summary-grid">
        <div class="sp-summary sp-summary-main" :class="{ 'is-ok': !overviewHasSignificant, 'is-hit': overviewHasSignificant }">
          <span class="sp-summary-k">结论</span>
          <b>{{ overviewConclusion }}</b>
          <small>{{ overviewExplain }}</small>
        </div>
        <div class="sp-summary">
          <span class="sp-summary-k">最强差异</span>
          <b>{{ strongestText }}</b>
          <small>{{ strongestDirection }}</small>
        </div>
        <div class="sp-summary">
          <span class="sp-summary-k">显著范围</span>
          <b>{{ significanceText }}</b>
          <small>{{ significanceSubtext }}</small>
        </div>
      </div>
    </section>

    <div class="sp-main" v-if="data">
      <!-- 左：通道 -->
      <aside class="sp-left">
        <div class="sp-left-h">通道<span class="sp-cnt">{{ data.ch_names.length }}</span></div>
        <div class="sp-chan-list">
          <button
            v-for="ch in data.ch_names"
            :key="ch"
            class="sp-chan"
            :class="{ 'is-sel': ch === selectedChannel, 'is-roi': roiSet.has(ch) }"
            @click="selectChannel(ch)"
          >
            <span class="sp-chan-name">{{ ch }}</span>
            <span v-if="roiSet.has(ch)" class="sp-chan-roi" title="cluster ROI 通道">◆</span>
          </button>
        </div>
      </aside>

      <!-- 中：主图 -->
      <section class="sp-canvas">
        <div v-if="!is1D" class="sp-canvas-head">
          <div class="sp-canvas-title-wrap">
            <span class="sp-canvas-title">通道 {{ selectedChannel }} · {{ heatTitle }}</span>
            <span class="sp-canvas-sub">{{ heatSubtitle }}</span>
          </div>
          <div class="sp-mode-tabs" role="tablist" aria-label="TFR 统计图显示模式">
            <button
              v-for="mode in heatModes"
              :key="mode.key"
              class="sp-mode-tab"
              :class="{ 'is-sel': heatMode === mode.key }"
              type="button"
              @click="setHeatMode(mode.key)"
            >
              {{ mode.label }}
            </button>
          </div>
        </div>

        <!-- 1D：ERP / PSD -->
        <template v-if="is1D">
          <div class="sp-plot-stack">
            <section class="sp-chart-card sp-chart-card-main">
              <div class="sp-chart-head">
                <div class="sp-chart-title-wrap">
                  <span class="sp-chart-title">通道 {{ selectedChannel }} · t 统计曲线</span>
                  <span class="sp-chart-sub">正值表示 {{ labelA }} 大于 {{ labelB }}，负值表示 {{ labelB }} 大于 {{ labelA }}</span>
                </div>
                <span class="sp-legend">
                  <i class="lg lg-t"></i>t 值
                  <template v-if="data.method === 'cluster'">
                    <i class="lg lg-clu-sig"></i>显著簇<i class="lg lg-clu-cand"></i>候选簇
                  </template>
                  <template v-else>
                    <i class="lg lg-sig"></i>显著
                  </template>
                </span>
              </div>
              <div ref="mainPlotRef" class="sp-chart-body">
                <svg class="sp-svg" :width="plotW" :height="plotH">
                  <line
                    v-for="tick in xTicks"
                    :key="'xg' + tick.label"
                    :x1="tick.x"
                    :y1="CHART_T"
                    :x2="tick.x"
                    :y2="chartBottom"
                    class="sp-grid-line"
                  />
                  <line
                    v-for="tick in yTicks"
                    :key="'yg' + tick.label"
                    :x1="CHART_L"
                    :y1="tick.y"
                    :x2="chartRight"
                    :y2="tick.y"
                    class="sp-grid-line"
                  />
                  <rect v-for="(s, i) in sigSegments" :key="'s' + i" :x="s.x" :y="CHART_T" :width="s.w" :height="chartH" class="sp-sig-band" />
                  <rect
                    v-for="(c, i) in clusterBands"
                    :key="'c' + i"
                    :x="c.x"
                    :y="CHART_T"
                    :width="c.w"
                    :height="chartH"
                    class="sp-clu-band"
                    :class="{ 'is-sig': c.sig }"
                  />
                  <line v-if="zeroInRange" :x1="CHART_L" :y1="zeroY" :x2="chartRight" :y2="zeroY" class="sp-zero" />
                  <polyline :points="ptsT" class="sp-line sp-line-t" />
                  <text v-for="(c, i) in clusterBands" :key="'ct' + i" :x="c.cx" y="16" class="sp-clu-label" v-show="c.sig">
                    p={{ c.p }}
                  </text>
                  <line :x1="CHART_L" :y1="chartBottom" :x2="chartRight" :y2="chartBottom" class="sp-axis-line" />
                  <line :x1="CHART_L" :y1="CHART_T" :x2="CHART_L" :y2="chartBottom" class="sp-axis-line" />
                  <g v-for="tick in xTicks" :key="'xt' + tick.label">
                    <line :x1="tick.x" :y1="chartBottom" :x2="tick.x" :y2="chartBottom + 5" class="sp-axis-line" />
                    <text :x="tick.x" :y="chartBottom + 20" class="sp-tick" text-anchor="middle">{{ tick.label }}</text>
                  </g>
                  <g v-for="tick in yTicks" :key="'yt' + tick.label">
                    <line :x1="CHART_L - 5" :y1="tick.y" :x2="CHART_L" :y2="tick.y" class="sp-axis-line" />
                    <text :x="CHART_L - 9" :y="tick.y + 4" class="sp-tick" text-anchor="end">{{ tick.label }}</text>
                  </g>
                  <text :x="CHART_L + chartW / 2" :y="plotH - 9" class="sp-axis-title" text-anchor="middle">{{ xAxisTitle }}</text>
                  <text
                    :x="16"
                    :y="CHART_T + chartH / 2"
                    :transform="`rotate(-90 16 ${CHART_T + chartH / 2})`"
                    class="sp-axis-title"
                    text-anchor="middle"
                  >{{ yAxisTitle }}</text>
                </svg>
              </div>
            </section>

            <section class="sp-chart-card sp-chart-card-mean">
              <div class="sp-chart-head">
                <div class="sp-chart-title-wrap">
                  <span class="sp-chart-title">通道 {{ selectedChannel }} · A/B 均值辅助图</span>
                  <span class="sp-chart-sub">虚线显示两组均值，仅用于辅助观察波形形态</span>
                </div>
                <span class="sp-legend">
                  <i class="lg lg-mean-a"></i>{{ labelA }} 均值<i class="lg lg-mean-b"></i>{{ labelB }} 均值
                </span>
              </div>
              <div ref="meanPlotRef" class="sp-chart-body">
                <svg class="sp-svg" :width="plotW" :height="meanPlotH">
                  <line
                    v-for="tick in xTicks"
                    :key="'mxg' + tick.label"
                    :x1="tick.x"
                    :y1="MEAN_CHART_T"
                    :x2="tick.x"
                    :y2="meanChartBottom"
                    class="sp-grid-line"
                  />
                  <line
                    v-for="tick in meanYTicks"
                    :key="'myg' + tick.label"
                    :x1="CHART_L"
                    :y1="tick.y"
                    :x2="chartRight"
                    :y2="tick.y"
                    class="sp-grid-line"
                  />
                  <line v-if="meanZeroInRange" :x1="CHART_L" :y1="meanZeroY" :x2="chartRight" :y2="meanZeroY" class="sp-zero" />
                  <polyline :points="ptsMeanA" class="sp-line sp-line-mean-a" />
                  <polyline :points="ptsMeanB" class="sp-line sp-line-mean-b" />
                  <line :x1="CHART_L" :y1="meanChartBottom" :x2="chartRight" :y2="meanChartBottom" class="sp-axis-line" />
                  <line :x1="CHART_L" :y1="MEAN_CHART_T" :x2="CHART_L" :y2="meanChartBottom" class="sp-axis-line" />
                  <g v-for="tick in xTicks" :key="'mxt' + tick.label">
                    <line :x1="tick.x" :y1="meanChartBottom" :x2="tick.x" :y2="meanChartBottom + 4" class="sp-axis-line" />
                    <text :x="tick.x" :y="meanChartBottom + 18" class="sp-tick" text-anchor="middle">{{ tick.label }}</text>
                  </g>
                  <g v-for="tick in meanYTicks" :key="'myt' + tick.label">
                    <line :x1="CHART_L - 5" :y1="tick.y" :x2="CHART_L" :y2="tick.y" class="sp-axis-line" />
                    <text :x="CHART_L - 9" :y="tick.y + 4" class="sp-tick" text-anchor="end">{{ tick.label }}</text>
                  </g>
                  <text :x="CHART_L + chartW / 2" :y="meanPlotH - 8" class="sp-axis-title" text-anchor="middle">{{ xAxisTitle }}</text>
                  <text
                    :x="16"
                    :y="MEAN_CHART_T + meanChartH / 2"
                    :transform="`rotate(-90 16 ${MEAN_CHART_T + meanChartH / 2})`"
                    class="sp-axis-title"
                    text-anchor="middle"
                  >{{ meanAxisTitle }}</text>
                </svg>
              </div>
            </section>
          </div>
        </template>

        <!-- 2D：TFR -->
        <template v-else>
          <div class="sp-heat-wrap"><canvas ref="heatCanvas" class="sp-heat"></canvas></div>
          <div class="sp-heat-scale">
            <span>{{ heatScaleLeft }}</span>
            <i :style="{ background: heatScaleGradient }"></i>
            <span>{{ heatScaleRight }}</span>
          </div>
          <div class="sp-axis-row">
            <span>{{ heatTimeLabel }}</span><span class="sp-axis-name">时间 × 频率（{{ heatFreqLabel }}）</span><span>{{ heatScaleNote }}</span>
          </div>
        </template>
      </section>

      <!-- 右：摘要 + cluster 表 -->
      <aside class="sp-right">
        <div class="sp-card">
          <div class="sp-card-h">对比摘要</div>
          <div class="sp-stat"><span>对比</span><b>{{ contrastLabel }}</b></div>
          <div class="sp-stat" v-if="data.condition"><span>条件</span><b>{{ data.condition }}</b></div>
          <div class="sp-stat"><span>设计</span><b>{{ designLabel }}</b></div>
          <div class="sp-stat"><span>方法</span><b>{{ methodLabel }}</b></div>
          <div class="sp-stat" v-if="data.method === 'cluster'"><span>簇模式</span><b>{{ clusterModeLabel }}</b></div>
          <div class="sp-stat" v-if="data.method === 'pointwise'"><span>校正</span><b>{{ correctionLabel }}</b></div>
          <div class="sp-stat"><span>显著点</span><b>{{ data.n_significant }} / {{ data.n_total }}</b></div>
          <div class="sp-stat"><span>max |t|</span><b>{{ data.tmax_abs }}</b></div>
        </div>

        <div class="sp-card" v-if="data.method === 'cluster'">
          <div class="sp-card-h">{{ clusterCardTitle }}</div>
          <div v-if="!data.clusters.length" class="sp-empty">未检出任何候选簇</div>
          <table v-else class="sp-clu-table">
            <thead><tr><th>窗口</th><th>p</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="(c, i) in data.clusters" :key="i" :class="{ 'is-sig': c.significant }">
                <td>{{ clusterWindowText(c) }}</td>
                <td>{{ c.p }}<span v-if="c.significant" class="sp-star">*</span></td>
                <td><span class="sp-clu-status" :class="{ 'is-sig': c.significant }">{{ c.significant ? '显著' : '候选' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="sp-note">{{ statNote }}</div>
      </aside>
    </div>

    <div v-else-if="loading" class="sp-state">加载统计图…</div>
    <div v-else class="sp-state sp-err">{{ error || '无数据' }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import { pipelineApi } from '@/api/pipelines'
import { useQueryString } from '@/composables/observe/observeUtils'
import { usePerfProbe } from '@/composables/observe/usePerfProbe'
import PerfBadge from '@/components/observe/PerfBadge.vue'
import type { StudyOutputStat, StudyOutputStatCluster, StudyOutputStatSibling } from '@/types'

type HeatMode = 't' | 'probability' | 'delta'

const DEFAULT_PLOT_W = 1000
const DEFAULT_PLOT_H = 320
const DEFAULT_MEAN_PLOT_H = 120
const CHART_L = 58
const CHART_R = 18
const CHART_T = 18
const CHART_B = 44
const MEAN_CHART_T = 16
const MEAN_CHART_B = 28

const qstr = useQueryString()
const studyId = qstr('studyId') || qstr('study_id')
const initialOutputId = (qstr('study_output_id') || qstr('dd')).split(',')[0]?.trim() || ''
const probe = usePerfProbe('stats') // 临时性能探针，测完删

const data = ref<StudyOutputStat | null>(null)
const loading = ref(false)
const error = ref('')
const selectedChannel = ref('')
const activeOutputId = ref(initialOutputId)
const heatMode = ref<HeatMode>('t')
let loadToken = 0
const heatCanvas = ref<HTMLCanvasElement | null>(null)
const mainPlotRef = ref<HTMLElement | null>(null)
const meanPlotRef = ref<HTMLElement | null>(null)
const plotSize = ref({ w: DEFAULT_PLOT_W, h: DEFAULT_PLOT_H })
const meanPlotSize = ref({ h: DEFAULT_MEAN_PLOT_H })
let plotResizeObserver: ResizeObserver | null = null

const is1D = computed(() => (data.value?.base_type || '') !== 'tfr')
const plotW = computed(() => Math.max(320, plotSize.value.w))
const plotH = computed(() => Math.max(180, plotSize.value.h))
const meanPlotH = computed(() => Math.max(110, meanPlotSize.value.h))
const chartW = computed(() => Math.max(1, plotW.value - CHART_L - CHART_R))
const chartH = computed(() => Math.max(1, plotH.value - CHART_T - CHART_B))
const chartRight = computed(() => CHART_L + chartW.value)
const chartBottom = computed(() => CHART_T + chartH.value)
const meanChartH = computed(() => Math.max(1, meanPlotH.value - MEAN_CHART_T - MEAN_CHART_B))
const meanChartBottom = computed(() => MEAN_CHART_T + meanChartH.value)

function readPlotSizes() {
  const mainRect = mainPlotRef.value?.getBoundingClientRect()
  if (mainRect && mainRect.width > 0 && mainRect.height > 0) {
    plotSize.value = {
      w: Math.round(mainRect.width),
      h: Math.round(mainRect.height),
    }
  }
  const meanRect = meanPlotRef.value?.getBoundingClientRect()
  if (meanRect && meanRect.height > 0) {
    meanPlotSize.value = { h: Math.round(meanRect.height) }
  }
}

function observePlotSizes() {
  plotResizeObserver?.disconnect()
  if (!is1D.value || typeof ResizeObserver === 'undefined') return
  const ro = new ResizeObserver(() => readPlotSizes())
  if (mainPlotRef.value) ro.observe(mainPlotRef.value)
  if (meanPlotRef.value) ro.observe(meanPlotRef.value)
  plotResizeObserver = ro
  readPlotSizes()
}

function syncOutputUrl(id: string) {
  if (!id) return
  const url = new URL(window.location.href)
  url.searchParams.set('study_output_id', id)
  url.searchParams.delete('dd')
  window.history.replaceState(null, '', url.toString())
}

async function load(channel?: string, targetOutputId = activeOutputId.value) {
  if (!studyId || !targetOutputId) {
    error.value = '缺少参数：需要 studyId 与 study_output_id。'
    return
  }
  const token = ++loadToken
  loading.value = true
  error.value = ''
  try {
    const res = await pipelineApi.getStudyOutputStat(studyId, targetOutputId, { channel })
    if (token !== loadToken) return
    data.value = res.data
    if (!heatModeAvailable(heatMode.value, res.data)) heatMode.value = 't'
    activeOutputId.value = res.data.study_output_id || targetOutputId
    syncOutputUrl(activeOutputId.value)
    probe.done('数据'); probe.paint(); probe.log() // 临时探针
    selectedChannel.value = res.data.channel
    await nextTick()
    if (is1D.value) {
      observePlotSizes()
    } else {
      plotResizeObserver?.disconnect()
      plotResizeObserver = null
      drawHeat()
    }
  } catch (e: unknown) {
    if (token !== loadToken) return
    const err = e as { response?: { data?: { detail?: { message?: string } } }; message?: string }
    error.value = err?.response?.data?.detail?.message || err?.message || '加载失败'
  } finally {
    if (token === loadToken) loading.value = false
  }
}

function selectChannel(ch: string) {
  if (ch !== selectedChannel.value) load(ch)
}

function selectOutput(id: string) {
  if (!id || id === activeOutputId.value) return
  load(selectedChannel.value || undefined, id)
}

function heatModeAvailable(mode: HeatMode, source: StudyOutputStat | null = data.value): boolean {
  if (mode === 't') return !!source?.t_grid?.length
  if (mode === 'probability') return !!source?.q_grid?.length
  return !!source?.delta_grid?.length
}

function setHeatMode(mode: HeatMode) {
  if (!heatModeAvailable(mode)) return
  heatMode.value = mode
  nextTick(() => drawHeat())
}

const heatModes = computed(() => {
  const modes: { key: HeatMode; label: string }[] = [{ key: 't', label: 't 值' }]
  if (heatModeAvailable('probability')) modes.push({ key: 'probability', label: '显著性' })
  if (heatModeAvailable('delta')) modes.push({ key: 'delta', label: 'A-B 差值' })
  return modes
})

// ---------- 文案 ----------
const contrastLabel = computed(() => data.value?.contrast_label || '统计比较')
const labelAB = computed(() => contrastLabel.value.split('·')[0].split(/[−-]/).map((s) => s.trim()))
const labelA = computed(() => labelAB.value[0] || '组 A')
const labelB = computed(() => labelAB.value[1] || '组 B')
const baseLabel = computed(
  () => ({ evoked: 'ERP（时域）', psd: 'PSD（频域）', tfr: 'TFR（时频）' } as Record<string, string>)[data.value?.base_type || ''] || data.value?.base_type || '',
)
const designLabel = computed(() => (data.value?.design === 'paired' ? '配对' : '独立'))
const methodLabel = computed(() => (data.value?.method === 'cluster' ? 'Cluster permutation' : '逐点 t 检验'))
const correctionLabel = computed(() => (data.value?.correction === 'fdr' ? 'FDR 校正' : '未校正'))
const clusterModeLabel = computed(() => {
  const mode = data.value?.cluster_mode || 'roi'
  if (mode === 'single_sensor') return '单通道簇'
  if (mode === 'multi_sensor') return '空间-时间簇'
  return 'ROI 平均簇'
})
const roiSet = computed(() => new Set(data.value?.roi_channels || []))
const roiText = computed(() => {
  const roi = data.value?.roi_channels || []
  if (!roi.length || roi.length === (data.value?.ch_names.length || 0)) return '全通道'
  return roi.join('、')
})
const clusterCardTitle = computed(() => {
  if (data.value?.cluster_mode === 'single_sensor') return `簇窗口（当前通道：${selectedChannel.value}）`
  if (data.value?.cluster_mode === 'multi_sensor') return `簇窗口（包含通道：${selectedChannel.value}）`
  return `簇窗口（ROI：${roiText.value}）`
})
const statNote = computed(() =>
  data.value?.method === 'cluster'
    ? data.value?.cluster_mode === 'multi_sensor'
      ? '空间-时间置换聚类检验：t 图显示未校正统计量；实线红带/深色轮廓表示通过 cluster 校正的显著簇，虚线红框表示候选簇但 p ≥ α。'
      : data.value?.cluster_mode === 'single_sensor'
        ? '单通道置换聚类检验：t 图显示未校正统计量；实线红带/深色轮廓表示通过 cluster 校正的显著簇，虚线红框表示候选簇但 p ≥ α。'
        : 'ROI 置换聚类检验：t 图显示未校正统计量；实线红带/深色轮廓表示通过 cluster 校正的显著簇，虚线红框表示候选簇但 p ≥ α。'
    : `逐点 t 检验：t 图显示未校正统计量；${correctionLabel.value}后 p < α 的点以着色带或深色轮廓标出。`,
)

const relatedOutputs = computed(() => data.value?.related_outputs || [])
const overview = computed(() => data.value?.overview || null)
const overviewHasSignificant = computed(() => !!overview.value?.has_significant)
const overviewConclusion = computed(() => overview.value?.conclusion || '统计结果摘要暂不可用。')
const overviewExplain = computed(() => {
  if (!overview.value) return '请检查该 stat_map 是否包含完整统计元数据。'
  if (data.value?.method === 'cluster') {
    return overviewHasSignificant.value
      ? '显著性以 cluster-corrected p 值为准，单点波形只用于定位细节。'
      : '没有簇通过当前 α 阈值；下方仍可查看未校正的均值差异位置。'
  }
  return overviewHasSignificant.value
    ? `${correctionLabel.value}后仍有显著点，通过左侧通道列表查看分布。`
    : `虽然局部 |t| 可能较高，但${correctionLabel.value}后没有点通过 α 阈值。`
})
const strongestText = computed(() => {
  const s = overview.value?.strongest
  if (!s) return '—'
  const parts = [`通道 ${s.channel || selectedChannel.value || '—'}`]
  if (s.axis_label) parts.push(s.axis_label)
  return parts.join(' · ')
})
const strongestDirection = computed(() => {
  const s = overview.value?.strongest
  if (!s) return '尚无可定位的最强差异。'
  return `${s.direction_label || 'A/B 差异'}；t = ${s.t ?? 0}`
})
const significanceText = computed(() => {
  const o = overview.value
  if (!o) return '—'
  if (data.value?.method === 'cluster') return `${o.n_significant_clusters} / ${o.n_clusters} 个簇`
  return `${o.n_significant} / ${o.n_total} 个点`
})
const significanceSubtext = computed(() => {
  const o = overview.value
  if (!o) return '暂无显著范围信息。'
  if (data.value?.method === 'cluster') {
    return o.n_significant_clusters > 0 ? '右侧簇表列出通过校正的时间/频率窗口。' : '当前没有通过校正的显著簇。'
  }
  if (o.significant_channels_total > 0) {
    const listed = o.significant_channels.join('、')
    const suffix = o.significant_channels_total > o.significant_channels.length ? ` 等 ${o.significant_channels_total} 个通道` : ''
    return `涉及 ${listed}${suffix}`
  }
  return '所有通道/特征点在当前阈值下均不显著。'
})

function outputLabel(item: StudyOutputStatSibling): string {
  if (item.condition) return item.condition
  if (item.contrast_label) return item.contrast_label.split('·').pop()?.trim() || item.contrast_label
  return item.display_name || '统计结果'
}

function outputBadge(item: StudyOutputStatSibling): string {
  if ((item.n_significant_clusters || 0) > 0) return `${item.n_significant_clusters} 簇`
  if (item.n_significant > 0) return `${item.n_significant} 点`
  return '无显著'
}

// ---------- 1D 几何 ----------
const axisValues = computed(() => (is1D.value ? data.value?.axis?.values || [] : []))
const tValues = computed(() => (data.value?.t || []).map((v) => Number(v)))
const sigArr = computed(() => data.value?.sig || [])
const xAxisTitle = computed(() => (data.value?.base_type === 'evoked' ? '时间 (s)' : '频率 (Hz)'))
const yAxisTitle = computed(() => 't 值')
const meanScale = computed(() => (data.value?.base_type === 'evoked' ? 1e6 : 1))
const meanUnit = computed(() => (data.value?.base_type === 'evoked' ? 'µV' : 'dB'))
const meanAxisTitle = computed(() => `均值 (${meanUnit.value})`)
const meanAValues = computed(() => (data.value?.mean_a || []).map((v) => Number(v) * meanScale.value))
const meanBValues = computed(() => (data.value?.mean_b || []).map((v) => Number(v) * meanScale.value))
const axisMin = computed(() => (axisValues.value.length ? axisValues.value[0] : 0))
const axisMax = computed(() => (axisValues.value.length ? axisValues.value[axisValues.value.length - 1] : 0))

const yDomain = computed(() => {
  const all = tValues.value.filter((v) => Number.isFinite(v))
  if (!all.length) return [0, 1]
  let lo = Math.min(...all)
  let hi = Math.max(...all)
  lo = Math.min(lo, 0)
  hi = Math.max(hi, 0)
  if (lo === hi) { lo -= 1; hi += 1 }
  const pad = (hi - lo) * 0.08
  return [lo - pad, hi + pad]
})
function xOf(i: number): number {
  const n = axisValues.value.length
  return n > 1 ? CHART_L + (i / (n - 1)) * chartW.value : CHART_L
}
function xVal(v: number): number {
  const lo = axisMin.value
  const hi = axisMax.value
  return hi > lo ? CHART_L + ((v - lo) / (hi - lo)) * chartW.value : CHART_L
}
function yOf(v: number): number {
  const [lo, hi] = yDomain.value
  return hi > lo ? CHART_T + (1 - (v - lo) / (hi - lo)) * chartH.value : CHART_T + chartH.value / 2
}
function trimNumber(value: number, digits: number): string {
  return value.toFixed(digits).replace(/\.?0+$/, '')
}
function formatTick(value: number): string {
  if (!Number.isFinite(value)) return ''
  const abs = Math.abs(value)
  if (abs === 0) return '0'
  if (abs >= 100) return trimNumber(value, 0)
  if (abs >= 10) return trimNumber(value, 1)
  if (abs >= 1) return trimNumber(value, 2)
  if (abs >= 0.01) return trimNumber(value, 3)
  return value.toExponential(1)
}
function linearTicks(min: number, max: number, count: number): { value: number; label: string }[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || count <= 1) return []
  if (min === max) return [{ value: min, label: formatTick(min) }]
  return Array.from({ length: count }, (_, i) => {
    const value = min + ((max - min) * i) / (count - 1)
    return { value, label: formatTick(value) }
  })
}
function polyline(arr: number[]): string {
  return arr.map((v, i) => `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`).join(' ')
}
const ptsT = computed(() => polyline(tValues.value))
const zeroInRange = computed(() => yDomain.value[0] < 0 && yDomain.value[1] > 0)
const zeroY = computed(() => yOf(0))
const xTicks = computed(() => linearTicks(axisMin.value, axisMax.value, 6).map((tick) => ({ ...tick, x: xVal(tick.value) })))
const yTicks = computed(() => linearTicks(yDomain.value[0], yDomain.value[1], 5).map((tick) => ({ ...tick, y: yOf(tick.value) })))

const meanDomain = computed(() => {
  const all = [...meanAValues.value, ...meanBValues.value].filter((v) => Number.isFinite(v))
  if (!all.length) return [0, 1]
  let lo = Math.min(...all)
  let hi = Math.max(...all)
  lo = Math.min(lo, 0)
  hi = Math.max(hi, 0)
  if (lo === hi) { lo -= 1; hi += 1 }
  const pad = (hi - lo) * 0.1
  return [lo - pad, hi + pad]
})
function meanYOf(v: number): number {
  const [lo, hi] = meanDomain.value
  return hi > lo ? MEAN_CHART_T + (1 - (v - lo) / (hi - lo)) * meanChartH.value : MEAN_CHART_T + meanChartH.value / 2
}
function meanPolyline(arr: number[]): string {
  return arr.map((v, i) => `${xOf(i).toFixed(1)},${meanYOf(v).toFixed(1)}`).join(' ')
}
const ptsMeanA = computed(() => meanPolyline(meanAValues.value))
const ptsMeanB = computed(() => meanPolyline(meanBValues.value))
const meanZeroInRange = computed(() => meanDomain.value[0] < 0 && meanDomain.value[1] > 0)
const meanZeroY = computed(() => meanYOf(0))
const meanYTicks = computed(() => linearTicks(meanDomain.value[0], meanDomain.value[1], 3).map((tick) => ({ ...tick, y: meanYOf(tick.value) })))

// 显著点的连续段 → 着色带
const sigSegments = computed(() => {
  const sig = sigArr.value
  const segs: { x: number; w: number }[] = []
  let start = -1
  for (let i = 0; i <= sig.length; i++) {
    if (i < sig.length && sig[i]) {
      if (start < 0) start = i
    } else if (start >= 0) {
      const x0 = xOf(start)
      const x1 = xOf(i - 1)
      segs.push({ x: x0, w: Math.max(1.5, x1 - x0) })
      start = -1
    }
  }
  return segs
})

// cluster 窗口 → 着色带（沿轴映射）
const clusterBands = computed(() => {
  const base = data.value?.base_type
  const out: { x: number; w: number; cx: number; sig: boolean; p: number }[] = []
  for (const c of data.value?.clusters || []) {
    let lo: number | undefined
    let hi: number | undefined
    if (base === 'evoked') { lo = c.tmin; hi = c.tmax }
    else if (base === 'psd') { lo = c.fmin; hi = c.fmax }
    if (lo === undefined || hi === undefined) continue
    const x0 = xVal(lo)
    const x1 = xVal(hi)
    out.push({ x: x0, w: Math.max(2, x1 - x0), cx: (x0 + x1) / 2, sig: !!c.significant, p: c.p })
  }
  return out
})

// ---------- 2D 热图 ----------
const heatFreqLabel = computed(() => {
  const f = data.value?.axis?.freqs || []
  return f.length ? `${f[0]}–${f[f.length - 1]} Hz` : ''
})
const heatTimeLabel = computed(() => {
  const t = data.value?.axis?.times || []
  return t.length ? `${t[0]} – ${t[t.length - 1]} s` : ''
})

const probabilityLabel = computed(() => (data.value?.probability_kind === 'fdr_q' ? '-log10(q)' : '-log10(p)'))
const heatTitle = computed(() => {
  if (heatMode.value === 'probability') return `${probabilityLabel.value} 显著性热图`
  if (heatMode.value === 'delta') return 'A-B 均值差热图'
  return 't 统计热图'
})
const heatSubtitle = computed(() => {
  if (heatMode.value === 'probability') {
    const tail = heatHasSignificant.value ? '深色轮廓才是校正后显著。' : '当前通道没有通过校正阈值的格点。'
    return `${probabilityLabel.value} 按阈值拉伸；接近阈值变黄，过阈值变红，${tail}`
  }
  if (heatMode.value === 'delta') return `正值表示 ${labelA.value} 大于 ${labelB.value}，负值表示 ${labelB.value} 大于 ${labelA.value}。`
  return '稳健色标会裁剪极端 t 值，显著格点用轮廓叠加。'
})
const probabilityGrid = computed(() => {
  const grid = data.value?.q_grid?.length ? data.value.q_grid : data.value?.p_grid || []
  return grid.map((row) => row.map((v) => -Math.log10(Math.min(1, Math.max(Number(v) || 0, 1e-300)))))
})
const heatValueGrid = computed(() => {
  if (heatMode.value === 'probability') return probabilityGrid.value
  if (heatMode.value === 'delta') return data.value?.delta_grid || []
  return data.value?.t_grid || []
})

function finiteGridValues(grid: number[][], abs = false): number[] {
  const out: number[] = []
  for (const row of grid) {
    for (const raw of row) {
      const v = Number(raw)
      if (Number.isFinite(v)) out.push(abs ? Math.abs(v) : v)
    }
  }
  return out
}

function percentile(values: number[], q: number): number {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * q)))
  return sorted[index]
}

function robustAbsScale(grid: number[][]): number {
  const values = finiteGridValues(grid, true)
  const max = values.length ? Math.max(...values) : 1
  const robust = percentile(values, 0.975)
  return Math.max(robust, max * 0.08, 1e-9)
}

function probabilityScale(grid: number[][]): number {
  const values = finiteGridValues(grid)
  const threshold = probabilityThresholdValue.value
  return Math.max(percentile(values, 0.985), threshold * 1.08, 1)
}

const probabilityThresholdValue = computed(() => -Math.log10(Math.max(data.value?.alpha || 0.05, 1e-300)))
const heatSigCount = computed(() => {
  const grid = data.value?.sig_grid || []
  let count = 0
  for (const row of grid) for (const item of row) if (item) count++
  return count
})
const heatHasSignificant = computed(() => heatSigCount.value > 0)

const heatScaleValue = computed(() => (
  heatMode.value === 'probability'
    ? probabilityScale(heatValueGrid.value)
    : robustAbsScale(heatValueGrid.value)
))
const heatScaleLeft = computed(() => {
  if (heatMode.value === 'probability') return '0'
  return `-${formatTick(heatScaleValue.value)}`
})
const heatScaleRight = computed(() => {
  if (heatMode.value === 'probability') return formatTick(heatScaleValue.value)
  return `+${formatTick(heatScaleValue.value)}`
})
const heatScaleNote = computed(() => {
  if (heatMode.value === 'probability') {
    const prefix = heatHasSignificant.value ? '显著格点以深色轮廓标出 · ' : '当前通道无校正后显著格点 · '
    return `${prefix}阈值 ${probabilityLabel.value}=${formatTick(probabilityThresholdValue.value)}`
  }
  return `色标裁剪 ±${formatTick(heatScaleValue.value)}`
})
const heatScaleGradient = computed(() => (
  heatMode.value === 'probability'
    ? `linear-gradient(90deg, #f8fafc 0%, #facc15 ${Math.round(clamp01(probabilityThresholdValue.value / Math.max(heatScaleValue.value, 1e-9)) * 100)}%, #b42318 100%)`
    : 'linear-gradient(90deg, #285ab4 0%, #ffffff 50%, #c83820 100%)'
))

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function mixChannel(from: number, to: number, amount: number): number {
  return Math.round(from + (to - from) * amount)
}

function rgb(from: [number, number, number], to: [number, number, number], amount: number): string {
  return `${mixChannel(from[0], to[0], amount)},${mixChannel(from[1], to[1], amount)},${mixChannel(from[2], to[2], amount)}`
}

function divergeColor(value: number, scale: number): string {
  const signed = scale > 0 ? Math.max(-1, Math.min(1, value / scale)) : 0
  const amount = Math.pow(Math.abs(signed), 0.68)
  return signed >= 0 ? rgb([255, 255, 255], [200, 56, 32], amount) : rgb([255, 255, 255], [40, 90, 180], amount)
}

function probabilityColor(value: number, scale: number): string {
  if (value <= 1e-6) return '248,250,252'
  const threshold = probabilityThresholdValue.value
  if (value < threshold) {
    const amount = 0.08 + Math.pow(clamp01(value / threshold), 0.55) * 0.62
    return rgb([248, 250, 252], [250, 204, 21], amount)
  }
  const denom = Math.max(scale - threshold, threshold * 0.15, 1e-9)
  const amount = Math.pow(clamp01((value - threshold) / denom), 0.65)
  return rgb([245, 158, 11], [180, 35, 24], amount)
}

function drawNoSignificanceOverlay(ctx: CanvasRenderingContext2D, cw: number, ch: number) {
  ctx.save()
  ctx.strokeStyle = 'rgba(71, 85, 105, 0.18)'
  ctx.lineWidth = 1
  ctx.setLineDash([5, 8])
  const gap = 34
  for (let x = -ch; x < cw + ch; x += gap) {
    ctx.beginPath()
    ctx.moveTo(x, ch)
    ctx.lineTo(x + ch, 0)
    ctx.stroke()
  }
  ctx.setLineDash([])

  const text = '当前通道无校正后显著格点'
  ctx.font = '600 14px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  const metrics = ctx.measureText(text)
  const boxW = Math.min(cw - 28, metrics.width + 32)
  const boxH = 34
  const boxX = Math.max(14, (cw - boxW) / 2)
  const boxY = Math.max(14, (ch - boxH) / 2)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.88)'
  ctx.fillRect(boxX, boxY, boxW, boxH)
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.55)'
  ctx.strokeRect(boxX + 0.5, boxY + 0.5, boxW - 1, boxH - 1)
  ctx.fillStyle = '#475569'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, cw / 2, boxY + boxH / 2)
  ctx.restore()
}

function drawHeat() {
  const c = heatCanvas.value
  const d = data.value
  const grid = heatValueGrid.value
  if (!c || !d || !grid.length) return
  const sg = d.sig_grid || []
  const nf = grid.length
  const nt = grid[0]?.length || 0
  if (!nf || !nt) return
  const cw = c.clientWidth || 600
  const ch = c.clientHeight || 320
  const dpr = window.devicePixelRatio || 1
  c.width = Math.round(cw * dpr)
  c.height = Math.round(ch * dpr)
  const ctx = c.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cw, ch)
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, cw, ch)
  const scale = heatScaleValue.value || 1
  const cellW = cw / nt
  const cellH = ch / nf
  for (let fi = 0; fi < nf; fi++) {
    const rowY = (nf - 1 - fi) * cellH // 高频在上
    for (let ti = 0; ti < nt; ti++) {
      const value = Number(grid[fi][ti]) || 0
      const color = heatMode.value === 'probability' ? probabilityColor(value, scale) : divergeColor(value, scale)
      ctx.fillStyle = `rgb(${color})`
      ctx.fillRect(ti * cellW, rowY, cellW + 0.6, cellH + 0.6)
    }
  }
  ctx.save()
  ctx.lineWidth = Math.max(1, Math.min(2, Math.max(cellW, cellH) * 0.08))
  ctx.strokeStyle = 'rgba(17, 24, 39, 0.62)'
  ctx.fillStyle = 'rgba(17, 24, 39, 0.10)'
  for (let fi = 0; fi < nf; fi++) {
    const rowY = (nf - 1 - fi) * cellH
    for (let ti = 0; ti < nt; ti++) {
      if (!sg[fi]?.[ti]) continue
      const x = ti * cellW
      ctx.fillRect(x, rowY, cellW + 0.6, cellH + 0.6)
      ctx.strokeRect(x + 0.5, rowY + 0.5, Math.max(1, cellW - 1), Math.max(1, cellH - 1))
    }
  }
  ctx.restore()
  if (heatMode.value === 'probability' && !heatHasSignificant.value) {
    drawNoSignificanceOverlay(ctx, cw, ch)
  }
}

function clusterWindowText(c: StudyOutputStatCluster): string {
  const base = data.value?.base_type
  const ch = c.n_channels ? ` · ${c.n_channels} 通道` : ''
  if (base === 'evoked') return `${c.tmin} – ${c.tmax} s${ch}`
  if (base === 'psd') return `${c.fmin} – ${c.fmax} Hz${ch}`
  if (base === 'tfr') return `${c.fmin}–${c.fmax} Hz × ${c.tmin}–${c.tmax} s${ch}`
  return `${c.n_points} 点${ch}`
}

function onResize() {
  if (is1D.value) readPlotSizes()
  else drawHeat()
}
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  plotResizeObserver?.disconnect()
})
</script>

<style scoped>
.stats-page { display: flex; flex-direction: column; height: 100vh; background: #f6f7f9; color: #1f2937; font-size: 13px; }
.sp-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.sp-id { display: flex; align-items: center; gap: 10px; }
.sp-badge { background: #b42318; color: #fff; font-weight: 700; font-size: 11px; padding: 3px 7px; border-radius: 5px; letter-spacing: 0; }
.sp-title { font-size: 15px; font-weight: 600; }
.sp-region { color: #9ca3af; font-weight: 400; font-size: 12px; margin-left: 8px; }
.sp-sub { margin-top: 3px; display: flex; flex-wrap: wrap; gap: 6px; }
.sp-tag { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 1px 6px; font-size: 11px; color: #4b5563; }
.sp-btn { border: 1px solid #d1d5db; background: #fff; border-radius: 6px; padding: 5px 12px; cursor: pointer; color: #374151; }
.sp-btn:hover { background: #f9fafb; }
.sp-btn:disabled { opacity: 0.5; cursor: default; }

.sp-overview { background: #fff; border-bottom: 1px solid #e5e7eb; padding: 10px 16px 12px; display: flex; flex-direction: column; gap: 10px; }
.sp-condition-strip { display: flex; align-items: center; gap: 8px; min-width: 0; overflow-x: auto; padding-bottom: 1px; }
.sp-section-label { flex: 0 0 auto; color: #6b7280; font-size: 12px; font-weight: 600; }
.sp-condition { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 8px; border: 1px solid #d8dee8; background: #f8fafc; border-radius: 6px; padding: 5px 9px; color: #334155; cursor: pointer; font-size: 12px; }
.sp-condition b { color: #64748b; font-size: 11px; font-weight: 600; }
.sp-condition:hover { background: #f1f5f9; }
.sp-condition.is-sel { border-color: #2f5f8f; background: #eaf1f8; color: #1f456d; font-weight: 600; }
.sp-condition.is-sig b { color: #b42318; }
.sp-summary-grid { display: grid; grid-template-columns: minmax(260px, 1.5fr) minmax(190px, 1fr) minmax(190px, 1fr); gap: 10px; }
.sp-summary { min-width: 0; border: 1px solid #e3e8ef; border-radius: 8px; background: #f8fafc; padding: 9px 11px; display: flex; flex-direction: column; gap: 4px; }
.sp-summary-main.is-ok { background: #f4f8f6; border-color: #d8e8df; }
.sp-summary-main.is-hit { background: #fff7ed; border-color: #fed7aa; }
.sp-summary-k { color: #64748b; font-size: 12px; font-weight: 600; }
.sp-summary b { color: #111827; font-size: 13px; font-weight: 700; line-height: 1.35; overflow-wrap: anywhere; }
.sp-summary small { color: #64748b; font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }

.sp-main { flex: 1; display: flex; min-height: 0; }
.sp-left { width: 150px; border-right: 1px solid #e5e7eb; background: #fff; display: flex; flex-direction: column; min-height: 0; }
.sp-left-h { padding: 8px 12px; font-weight: 600; border-bottom: 1px solid #f0f1f3; display: flex; justify-content: space-between; }
.sp-cnt { color: #9ca3af; font-weight: 400; }
.sp-chan-list { overflow-y: auto; flex: 1; padding: 4px; }
.sp-chan { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 4px; border: none; background: transparent; padding: 5px 8px; border-radius: 5px; cursor: pointer; color: #374151; font-size: 12px; }
.sp-chan:hover { background: #f3f4f6; }
.sp-chan.is-sel { background: #fce9e7; color: #b42318; font-weight: 600; }
.sp-chan-roi { color: #b42318; font-size: 9px; }

.sp-canvas { flex: 1; display: flex; flex-direction: column; min-width: 0; padding: 12px 16px; }
.sp-canvas-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; min-width: 0; }
.sp-canvas-title-wrap { min-width: 0; display: flex; align-items: baseline; gap: 9px; overflow: hidden; }
.sp-canvas-title { flex: 0 0 auto; font-weight: 600; }
.sp-canvas-sub { min-width: 0; color: #64748b; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sp-mode-tabs { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 2px; padding: 2px; border: 1px solid #d8dee8; border-radius: 7px; background: #f8fafc; }
.sp-mode-tab { border: 0; background: transparent; color: #475569; border-radius: 5px; padding: 4px 9px; font-size: 12px; cursor: pointer; }
.sp-mode-tab:hover { background: #eef3f8; }
.sp-mode-tab.is-sel { background: #2f5f8f; color: #fff; font-weight: 600; }
.sp-legend { color: #64748b; font-size: 12px; display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.lg { display: inline-block; width: 14px; height: 3px; border-radius: 2px; margin: 0 2px 0 8px; flex: 0 0 auto; }
.lg-t { background: #2f5f8f; }
.lg-sig { background: rgba(180, 35, 24, 0.25); height: 10px; }
.lg-clu-sig { border: 1px solid rgba(180, 35, 24, 0.8); background: rgba(180, 35, 24, 0.18); height: 10px; }
.lg-clu-cand { border: 1px dashed rgba(180, 35, 24, 0.55); background: rgba(180, 35, 24, 0.04); height: 10px; }
.lg-pos { background: #c83820; height: 10px; width: 10px; } .lg-neg { background: #285ab4; height: 10px; width: 10px; }
.lg-mean-a,
.lg-mean-b { height: 0; border-top: 2px dashed; background: transparent; border-radius: 0; }
.lg-mean-a { border-color: #64748b; }
.lg-mean-b { border-color: #a66d19; }
.sp-plot-stack { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.sp-chart-card { min-height: 0; display: flex; flex-direction: column; background: #fff; border: 1px solid #dbe3ee; border-radius: 7px; overflow: hidden; }
.sp-chart-card-main { flex: 3 1 0; }
.sp-chart-card-mean { flex: 1 1 0; }
.sp-chart-head { min-height: 34px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 7px 11px; background: #f8fafc; border-bottom: 1px solid #e5eaf2; }
.sp-chart-title-wrap { min-width: 0; display: flex; align-items: baseline; gap: 9px; overflow: hidden; }
.sp-chart-title { flex: 0 0 auto; color: #26364d; font-size: 12px; font-weight: 700; }
.sp-chart-sub { min-width: 0; color: #7a8799; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sp-chart-body { flex: 1; min-height: 0; background: #fff; }
.sp-svg { width: 100%; height: 100%; min-height: 0; display: block; background: #fff; font-family: var(--ff-mono); }
.sp-sig-band { fill: rgba(180, 35, 24, 0.1); }
.sp-clu-band { fill: rgba(180, 35, 24, 0.04); stroke: rgba(180, 35, 24, 0.35); stroke-dasharray: 3 3; stroke-width: 1; }
.sp-clu-band.is-sig { fill: rgba(180, 35, 24, 0.13); stroke: rgba(180, 35, 24, 0.7); stroke-dasharray: none; }
.sp-clu-label { fill: #b42318; font-size: 11px; font-weight: 600; }
.sp-zero { stroke: #9aa7bb; stroke-width: 1; stroke-dasharray: 4 3; }
.sp-line { fill: none; stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.sp-line-t { stroke: #2f5f8f; }
.sp-line-mean-a,
.sp-line-mean-b { fill: none; stroke-width: 1.4; stroke-dasharray: 6 5; vector-effect: non-scaling-stroke; }
.sp-line-mean-a { stroke: #64748b; }
.sp-line-mean-b { stroke: #a66d19; }
.sp-heat-wrap { flex: 1; min-height: 0; background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.sp-heat { width: 100%; height: 100%; display: block; }
.sp-heat-scale { display: grid; grid-template-columns: auto minmax(120px, 220px) auto; align-items: center; gap: 7px; color: #64748b; font-size: 11px; margin-top: 6px; align-self: flex-end; }
.sp-heat-scale i { display: block; height: 9px; border: 1px solid #cbd5e1; border-radius: 999px; }
.sp-axis-row { display: flex; justify-content: space-between; color: #9ca3af; font-size: 11px; margin-top: 4px; }
.sp-axis-name { color: #6b7280; }
.sp-grid-line { stroke: #d3dae6; stroke-width: 1; vector-effect: non-scaling-stroke; }
.sp-axis-line { stroke: #aeb7c6; stroke-width: 1; vector-effect: non-scaling-stroke; }
.sp-tick { fill: #51607a; font-size: 12px; font-weight: 400; }
.sp-axis-title { fill: #51607a; font-size: 13px; font-weight: 600; }

.sp-right { width: 230px; border-left: 1px solid #e5e7eb; background: #fff; padding: 12px; overflow-y: auto; }
.sp-card { border: 1px solid #eceef1; border-radius: 8px; padding: 10px; margin-bottom: 12px; }
.sp-card-h { font-weight: 600; margin-bottom: 8px; font-size: 12px; }
.sp-stat { display: flex; justify-content: space-between; padding: 3px 0; color: #6b7280; }
.sp-stat b { color: #1f2937; font-weight: 600; }
.sp-clu-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sp-clu-table th { text-align: left; color: #9ca3af; font-weight: 500; border-bottom: 1px solid #f0f1f3; padding: 3px 2px; }
.sp-clu-table td { padding: 4px 2px; border-bottom: 1px solid #f6f7f8; color: #6b7280; }
.sp-clu-table tr.is-sig td { color: #1f2937; font-weight: 600; }
.sp-clu-status { color: #94a3b8; font-weight: 600; }
.sp-clu-status.is-sig { color: #b42318; }
.sp-star { color: #b42318; margin-left: 2px; }
.sp-empty { color: #9ca3af; font-size: 12px; }
.sp-note { color: #9ca3af; font-size: 11px; line-height: 1.5; margin-top: 4px; }
.sp-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #9ca3af; }
.sp-err { color: #b42318; }
</style>
