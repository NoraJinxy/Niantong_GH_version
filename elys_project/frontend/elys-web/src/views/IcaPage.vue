<template>
  <WorkbenchShell active-key="ica" active-top-key="analysis">
    <div class="ica-shell">
      <div class="ica-toolbar">
        <h1 class="page__title ica-title" style="font-size: 22px; margin: 0">
          <IconLine name="brain" :size="24" /> ICA 成分审核
        </h1>
        <span v-if="isLive && overview" class="muted text-sm">
          {{ overview.method || 'ICA' }} · {{ overview.n_components }} 成分 · {{ overview.n_channels }} 通道
          <template v-if="overview.total_variance_explained != null">
            · 解释方差 {{ overview.total_variance_explained.toFixed(1) }}%
          </template>
        </span>
        <span class="ica-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实 ICA 数据' : '查看模式' }}</span>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="load">刷新</button>
      </div>

      <div class="ica-body">
        <!-- 无参数：诚实空态 -->
        <div v-if="!isLive" class="ica-empty">
          <AppIcon name="brain" :size="40" />
          <p class="ica-empty-title">从结果选择一个 ICA 结果查看成分</p>
          <p class="muted text-sm">
            在工作流运行「Compute ICA」节点后，于结果页或 ICA Apply 节点处打开本页，
            即可看到真实的成分地形图、时域、频谱与去除前后对比。
          </p>
        </div>
        <div v-else-if="error" class="ica-empty is-error">
          <AppIcon name="warning" :size="32" />
          <p class="ica-empty-title">{{ error }}</p>
          <button class="btn btn--sm" :disabled="loading" @click="load">重试</button>
        </div>
        <div v-else-if="loading && !components.length" class="ica-empty">
          <p class="muted">加载 ICA 成分中…</p>
        </div>

        <template v-else>
          <!-- 成分网格 -->
          <div class="card mb-3">
            <div class="card__header">
              <div>
                <h3 class="card__title">ICA 成分 · {{ components.length }} 个</h3>
                <div class="card__sub">点击卡片看详情；右下角按钮标记剔除。颜色为成分在各电极的权重（蓝负红正）。</div>
              </div>
              <span class="badge badge--primary">{{ keepCount }} 保留 / {{ removeList.length }} 剔除</span>
            </div>

            <div class="ic-grid">
              <div
                v-for="comp in components"
                :key="comp.index"
                class="ic-card"
                :class="{ 'is-remove': removeSet.has(comp.index), 'is-active': comp.index === selectedIndex }"
                @click="selectComponent(comp.index)"
              >
                <svg viewBox="-1.28 -1.34 2.56 2.62" class="ic-topo">
                  <circle cx="0" cy="0" r="1" fill="#FCFCFE" stroke="#C4CCD8" stroke-width="0.02" />
                  <path d="M -0.13 -0.99 Q 0 -1.24 0.13 -0.99" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
                  <circle
                    v-for="p in comp.topography"
                    :key="p.name"
                    :cx="p.x"
                    :cy="-p.y"
                    r="0.07"
                    :fill="topoColor(p.weight, comp.vmax)"
                    stroke="#fff"
                    stroke-width="0.014"
                  />
                </svg>
                <strong class="ic-card-id">{{ comp.label }}</strong>
                <div class="muted text-sm">{{ comp.explained_variance != null ? comp.explained_variance.toFixed(1) + '%' : '—' }}</div>
                <button class="ic-mark" :class="{ 'is-on': removeSet.has(comp.index) }" @click.stop="toggleRemove(comp.index)">
                  {{ removeSet.has(comp.index) ? '剔除 ✕' : '保留' }}
                </button>
              </div>
            </div>
          </div>

          <!-- 选中成分详情 -->
          <div v-if="activeComp" class="card">
            <div class="card__header">
              <div>
                <h3 class="card__title">
                  选中：{{ activeComp.label }}
                  <span v-if="activeComp.explained_variance != null" class="muted">· 解释方差 {{ activeComp.explained_variance.toFixed(1) }}%</span>
                </h3>
                <div class="card__sub">地形图 · 时域波形 · Welch 频谱 · 去除前后对比{{ detailLoading ? ' · 加载中…' : '' }}</div>
              </div>
              <button class="btn btn--sm" :class="removeSet.has(activeComp.index) ? 'btn--danger' : 'btn--primary'" @click="toggleRemove(activeComp.index)">
                {{ removeSet.has(activeComp.index) ? '取消剔除' : '标记剔除' }}
              </button>
            </div>

            <div class="grid grid-3">
              <div>
                <div class="panel__title">地形图</div>
                <svg viewBox="-1.28 -1.34 2.56 2.62" class="ic-topo-lg">
                  <circle cx="0" cy="0" r="1" fill="#FCFCFE" stroke="#C4CCD8" stroke-width="0.02" />
                  <path d="M -0.13 -0.99 Q 0 -1.24 0.13 -0.99" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
                  <path d="M -1 -0.2 Q -1.13 0 -1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
                  <path d="M 1 -0.2 Q 1.13 0 1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
                  <circle
                    v-for="p in activeComp.topography"
                    :key="p.name"
                    :cx="p.x"
                    :cy="-p.y"
                    r="0.06"
                    :fill="topoColor(p.weight, activeComp.vmax)"
                    stroke="#fff"
                    stroke-width="0.012"
                  >
                    <title>{{ p.name }}: {{ p.weight.toFixed(3) }}</title>
                  </circle>
                </svg>
                <div class="muted text-sm">主导通道：{{ activeComp.top_channels.join(' · ') || '—' }}</div>
              </div>

              <div>
                <div class="panel__title">时域波形</div>
                <svg viewBox="0 0 300 90" class="ic-plot">
                  <path :d="timecoursePath" stroke="var(--c-primary)" stroke-width="1" fill="none" />
                </svg>
                <div class="muted text-sm">{{ detail ? detail.timecourse.values.length + ' 点 · 前 ' + maxSeconds + ' 秒' : '—' }}</div>
              </div>

              <div>
                <div class="panel__title">Welch 频谱 (dB)</div>
                <svg viewBox="0 0 300 90" class="ic-plot">
                  <path :d="spectrumPath" stroke="var(--c-accent)" stroke-width="1.2" fill="none" />
                </svg>
                <div class="muted text-sm">{{ detail ? '0–' + detail.spectrum.fmax + ' Hz' : '—' }}</div>
              </div>
            </div>

            <div class="divider"></div>

            <div class="panel__title">原始 vs 去除选定成分后</div>
            <svg v-if="comparison && comparison.has_comparison" viewBox="0 0 1000 90" class="ic-wide">
              <path :d="comparisonPath.original" stroke="var(--c-text-3)" stroke-width="1" fill="none" opacity=".6" />
              <path :d="comparisonPath.filtered" stroke="var(--c-primary)" stroke-width="1.2" fill="none" />
            </svg>
            <p v-else class="muted text-sm">标记要剔除的成分后，这里显示某通道（{{ comparison?.channel_name || '首通道' }}）去除前后的对比波形。</p>
            <div v-if="comparison && comparison.has_comparison" class="row gap-3 muted text-sm mt-2">
              <span class="legend"><span class="swatch" style="background: var(--c-text-3)"></span>原始（{{ comparison.channel_name }}）</span>
              <span class="legend"><span class="swatch" style="background: var(--c-primary)"></span>去除 {{ removeList.length }} 个成分后</span>
            </div>
          </div>
        </template>
      </div>

      <aside class="ica-side" v-if="isLive">
        <div class="panel__title">去除清单</div>
        <ul class="ic-removelist">
          <li v-if="!removeList.length" class="muted text-sm">未标记任何成分</li>
          <li v-for="idx in removeList" :key="idx">
            <span class="dot" style="background: var(--c-danger)"></span>
            {{ labelOf(idx) }}
            <button class="ic-x" @click="toggleRemove(idx)">✕</button>
          </li>
        </ul>

        <div class="panel__title">参数</div>
        <div class="ic-param-row"><span>算法</span><strong>{{ overview?.method || '—' }}</strong></div>
        <div class="ic-param-row"><span>成分数</span><strong>{{ overview?.n_components ?? '—' }}</strong></div>
        <div class="ic-param-row"><span>通道</span><strong>{{ overview?.n_channels ?? '—' }}</strong></div>

        <div class="panel__title">操作</div>
        <button class="btn btn--block btn--primary" :disabled="!canApply || applying" @click="applyDecision">
          <AppIcon name="check" :size="16" />
          {{ applying ? '提交中…' : '应用去除 ' + removeList.length + ' 个成分' }}
        </button>
        <p v-if="!jobContext" class="muted text-sm mt-2">查看模式：在工作流的「ICA Apply」节点处打开本页才能提交剔除决策。</p>
        <p v-if="applyMsg" class="ica-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</p>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, dataApi } from '@/api/client'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'

// ---- 后端返回结构（对齐 app/pipeline/ica_inspect.py） ----
interface TopoPoint { name: string; x: number; y: number; weight: number }
interface IcaComponent {
  index: number
  label: string
  vmax: number
  explained_variance: number | null
  topography: TopoPoint[]
  top_channels: string[]
  has_positions: boolean
}
interface IcaComponentsResponse {
  n_components: number
  method: string | null
  exclude: number[]
  ch_names: string[]
  n_channels: number
  total_variance_explained: number | null
  study_output_id: string
  has_source_raw: boolean
  components: IcaComponent[]
}
interface IcaComparison {
  has_comparison: boolean
  channel_name?: string
  components_removed?: number[]
  times?: number[]
  original?: number[]
  filtered?: number[]
  message?: string
}
interface IcaDetail {
  index: number
  label: string
  explained_variance: number | null
  sfreq: number
  timecourse: { times: number[]; values: number[] }
  spectrum: { frequencies: number[]; power_db: number[]; fmax: number }
  comparison?: IcaComparison
}

const route = useRoute()
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return (raw as string | null) ?? fallback
}

const studyId = qstr('studyId') || qstr('study')
const outputId = qstr('study_output_id') || qstr('dd')
// 交互上下文（从工作流 waiting_user_input 的 ICA Apply 节点打开时带上），用于提交剔除决策
const executionId = qstr('executionId') || qstr('execution_id')
const jobId = qstr('jobId') || qstr('job_id')
const decisionVersion = Number(qstr('decisionVersion') || qstr('decision_version') || '0')

const maxSeconds = 10
const isLive = computed(() => Boolean(studyId && outputId))
const jobContext = computed(() => Boolean(isLive.value && executionId && jobId && decisionVersion > 0))

const loading = ref(false)
const error = ref('')
const overview = ref<IcaComponentsResponse | null>(null)
const components = ref<IcaComponent[]>([])
const removeSet = ref<Set<number>>(new Set())

const selectedIndex = ref<number | null>(null)
const detail = ref<IcaDetail | null>(null)
const detailLoading = ref(false)
let detailSeq = 0

const applying = ref(false)
const applyMsg = ref('')
const applyError = ref(false)

const activeComp = computed(() => components.value.find((c) => c.index === selectedIndex.value) || null)
const comparison = computed(() => detail.value?.comparison || null)
const keepCount = computed(() => components.value.length - removeSet.value.size)
const removeList = computed(() => [...removeSet.value].sort((a, b) => a - b))
const canApply = computed(() => jobContext.value && removeList.value.length >= 0 && !applying.value)

function labelOf(idx: number): string {
  return components.value.find((c) => c.index === idx)?.label || `IC${String(idx).padStart(3, '0')}`
}

// 发散色：负→蓝、零→近白、正→红（与时域看图地形图条同源）
function topoColor(w: number, vmax: number): string {
  const m = vmax > 0 ? vmax : 1
  const t = Math.max(-1, Math.min(1, w / m))
  const white = [244, 246, 249]
  const target = t < 0 ? [63, 94, 143] : [176, 84, 76]
  const k = Math.abs(t)
  const r = Math.round(white[0] + (target[0] - white[0]) * k)
  const g = Math.round(white[1] + (target[1] - white[1]) * k)
  const b = Math.round(white[2] + (target[2] - white[2]) * k)
  return `rgb(${r}, ${g}, ${b})`
}

// 把一维序列映射成 SVG path；可传入共享 lo/hi 让多条线同尺度
function linePath(ys: number[], w: number, h: number, pad = 8, lo?: number, hi?: number): string {
  if (!ys.length) return ''
  let mn = lo ?? Infinity
  let mx = hi ?? -Infinity
  if (lo === undefined || hi === undefined) {
    for (const v of ys) {
      if (v < mn) mn = v
      if (v > mx) mx = v
    }
  }
  const span = mx - mn || 1
  const n = ys.length
  return ys
    .map((v, i) => {
      const x = (i / (n - 1 || 1)) * w
      const y = h - pad - ((v - mn) / span) * (h - 2 * pad)
      return `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')
}

const timecoursePath = computed(() => (detail.value ? linePath(detail.value.timecourse.values, 300, 90) : ''))
const spectrumPath = computed(() => (detail.value ? linePath(detail.value.spectrum.power_db, 300, 90) : ''))
const comparisonPath = computed(() => {
  const c = comparison.value
  if (!c || !c.has_comparison || !c.original || !c.filtered) return { original: '', filtered: '' }
  let lo = Infinity
  let hi = -Infinity
  for (const v of [...c.original, ...c.filtered]) {
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  return {
    original: linePath(c.original, 1000, 90, 8, lo, hi),
    filtered: linePath(c.filtered, 1000, 90, 8, lo, hi),
  }
})

async function load() {
  if (!isLive.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await dataApi.get<IcaComponentsResponse>(`/studies/${studyId}/outputs/${outputId}/ica-components`)
    overview.value = res.data
    components.value = res.data.components || []
    removeSet.value = new Set(res.data.exclude || [])
    if (components.value.length) {
      selectComponent(selectedIndex.value ?? components.value[0].index)
    }
    document.title = `ICA 审核 · ${res.data.n_components} 成分 — 念析`
  } catch (err: unknown) {
    error.value = describeError(err)
    components.value = []
    overview.value = null
  } finally {
    loading.value = false
  }
}

async function selectComponent(index: number) {
  selectedIndex.value = index
  const myId = ++detailSeq
  detailLoading.value = true
  try {
    const excluded = removeList.value.join(',')
    const res = await dataApi.get<IcaDetail>(`/studies/${studyId}/outputs/${outputId}/ica-components/${index}`, {
      params: { excluded: excluded || undefined, max_seconds: maxSeconds },
    })
    if (myId !== detailSeq) return
    detail.value = res.data
  } catch {
    if (myId === detailSeq) detail.value = null
  } finally {
    if (myId === detailSeq) detailLoading.value = false
  }
}

function toggleRemove(index: number) {
  const next = new Set(removeSet.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  removeSet.value = next
}

// 剔除清单变化且有选中成分 → 刷新该成分详情（更新去除前后对比）
watch(removeSet, () => {
  if (selectedIndex.value != null) selectComponent(selectedIndex.value)
})

async function applyDecision() {
  if (!jobContext.value) return
  applying.value = true
  applyMsg.value = ''
  applyError.value = false
  try {
    await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/decision`, {
      excluded_components: removeList.value,
      decision_version: decisionVersion,
    })
    applyMsg.value = `已提交剔除 ${removeList.value.length} 个成分，流水线将继续执行。`
  } catch (err: unknown) {
    applyError.value = true
    applyMsg.value = describeError(err)
  } finally {
    applying.value = false
  }
}

function describeError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: { message?: string } | string } }; message?: string }
  const detailField = e?.response?.data?.detail
  if (typeof detailField === 'string') return detailField
  if (detailField?.message) return detailField.message
  return e?.message || '加载失败'
}

onMounted(load)
</script>

<style scoped>
:deep(.page) { padding: 0; }
.ica-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  grid-template-rows: 56px 1fr;
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
.ica-title { display: flex; align-items: center; gap: 8px; }
.ica-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.ica-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.ica-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.ica-body { padding: var(--s-4); min-width: 0; overflow-y: auto; }
.ica-side {
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  padding: var(--s-4);
  overflow-y: auto;
}

.ica-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.ica-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.ica-empty.is-error .ica-empty-title { color: var(--c-danger); }

.ic-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(108px, 1fr)); gap: 10px; }
.ic-card {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 8px 6px 6px; border: 1px solid var(--c-border); border-radius: var(--r-sm);
  background: var(--c-surface); cursor: pointer; transition: border-color .12s, box-shadow .12s;
}
.ic-card:hover { border-color: var(--c-primary); }
.ic-card.is-active { border-color: var(--c-primary); box-shadow: 0 0 0 2px rgba(46, 107, 255, .18); }
.ic-card.is-remove { background: rgba(239, 68, 68, .05); border-color: rgba(239, 68, 68, .4); }
.ic-topo { width: 84px; height: 84px; }
.ic-card-id { font-size: 12px; }
.ic-mark { font-size: 10px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--c-border); background: var(--c-surface); color: var(--c-text-3); cursor: pointer; }
.ic-mark.is-on { background: var(--c-danger); color: #fff; border-color: var(--c-danger); }

.ic-topo-lg { width: 100%; max-width: 180px; height: 180px; display: block; }
.ic-plot { width: 100%; height: 90px; display: block; background: var(--c-bg-soft, #f7f9fc); border-radius: var(--r-sm); }
.ic-wide { width: 100%; height: 90px; display: block; background: var(--c-bg-soft, #f7f9fc); border-radius: var(--r-sm); }

.ic-removelist { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.ic-removelist li { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.ic-removelist .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ic-x { margin-left: auto; border: none; background: none; color: var(--c-text-3); cursor: pointer; }
.ic-param-row { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; color: var(--c-text-2); }
.legend { display: inline-flex; align-items: center; gap: 4px; }
.swatch { width: 10px; height: 3px; border-radius: 2px; display: inline-block; }
.ica-applymsg { font-size: 12px; margin-top: 8px; color: var(--c-success); }
.ica-applymsg.is-error { color: var(--c-danger); }
</style>
