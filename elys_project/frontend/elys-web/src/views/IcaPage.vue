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
          <!-- 成分网格（插值头皮场，复用观察页 TopoStrip） -->
          <div class="card mb-3">
            <div class="card__header">
              <div>
                <h3 class="card__title">ICA 成分 · {{ components.length }} 个</h3>
                <div class="card__sub">
                  点击成分看详情并标记剔除；地形图是该成分在各电极的权重经插值的头皮场（红正·蓝负·白≈0，各成分独立归一）。被标记剔除的成分显红框。
                </div>
              </div>
              <div class="ic-wall-tools">
                <label class="ic-sort">
                  排序
                  <select v-model="sortMode" class="ic-sort-sel">
                    <option value="index">编号</option>
                    <option value="variance">解释方差 ↓</option>
                  </select>
                </label>
                <span class="badge badge--primary">{{ keepCount }} 保留 / {{ removeList.length }} 剔除</span>
              </div>
            </div>

            <TopoStrip
              layout="grid"
              selectable
              :cells="componentCells"
              :vmax="1"
              :active-seg="selectedIndex"
              subtitle="成分空间模式 · 各成分独立归一"
              unit=""
              lo-label="−"
              hi-label="+"
              @cell-click="selectComponent"
            />
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
                <TopoStrip :cells="detailCells" :vmax="1" subtitle="成分空间模式" unit="" lo-label="−" hi-label="+" />
                <div class="muted text-sm">主导通道：{{ activeComp.top_channels.join(' · ') || '—' }}</div>
              </div>

              <div>
                <div class="panel__title">时域波形（源激活）</div>
                <div class="ic-plot-host">
                  <TimeCourseCanvas :data="tcData" :series="tcSeries" x-label="时间 (s)" y-label="" :show-legend="false" :loading="detailLoading" />
                </div>
                <div class="muted text-sm">{{ detail ? detail.timecourse.values.length + ' 点 · 前 ' + maxSeconds + ' 秒' : '—' }}</div>
              </div>

              <div>
                <div class="panel__title">Welch 频谱 (dB)</div>
                <div class="ic-plot-host">
                  <TimeCourseCanvas :data="specData" :series="specSeries" x-label="Hz" y-label="dB" :show-legend="false" use-spline :loading="detailLoading" />
                </div>
                <div class="muted text-sm">{{ detail ? '0–' + detail.spectrum.fmax + ' Hz' : '—' }}</div>
              </div>
            </div>

            <div class="divider"></div>

            <div class="panel__title">
              原始 vs 去除选定成分后<template v-if="comparison && comparison.has_comparison && comparison.channel_name">（{{ comparison.channel_name }}）</template>
            </div>
            <div v-if="comparison && comparison.has_comparison" class="ic-plot-host ic-plot-host--wide">
              <TimeCourseCanvas :data="cmpData" :series="cmpSeries" x-label="时间 (s)" y-label="µV" show-legend />
            </div>
            <p v-else class="muted text-sm">标记要剔除的成分后，这里显示某通道（{{ comparison?.channel_name || '首通道' }}）去除前后的对比波形。</p>
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
          {{ applying ? '提交中…' : '应用去除 ' + removeList.length + ' 个成分并继续' }}
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
import TopoStrip from '@/components/observe/TopoStrip.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'

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

// TopoStrip 的 cell 形状（与组件内 TopoCell 结构兼容）
interface TopoCell {
  seg: number
  label: string
  color: string
  points: { name: string; x: number; y: number; value: number }[] | null
  sub?: string
  marked?: boolean
}

// 成分墙配色：中性灰=保留、红=标记剔除（选中态由 TopoStrip 自身的 active 环表达）。
const NEUTRAL = '#C4CCD8'
const DANGER = '#EF4444'
const PRIMARY = '#3F5E8F' // elys 招牌蓝（画布内硬编码，与观察页一致）
const ACCENT = '#7A5AA6' // 频谱用紫
const GRAY = '#79859A' // 对比图"原始"用灰

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

// 单成分权重 → TopoStrip 电极点：除以该成分自身 vmax 归一到 [-1,1]，配合 TopoStrip vmax=1 实现"每成分独立归一"。
function cellPoints(c: IcaComponent): TopoCell['points'] {
  if (!c.has_positions) return null
  const m = c.vmax > 0 ? c.vmax : 1
  return c.topography.map((p) => ({ name: p.name, x: p.x, y: p.y, value: p.weight / m }))
}

// 成分墙排序：默认按编号；可切"按解释方差↓"先看影响最大的成分（ICA 审阅常规起手式）。
const sortMode = ref<'index' | 'variance'>('index')
const sortedComponents = computed(() => {
  const list = [...components.value]
  if (sortMode.value === 'variance') {
    list.sort((a, b) => (b.explained_variance ?? -Infinity) - (a.explained_variance ?? -Infinity))
  }
  return list
})

// 成分墙：每成分一格插值地形图，颜色/标记态由 removeSet 驱动，sub 显解释方差%。
const componentCells = computed<TopoCell[]>(() =>
  sortedComponents.value.map((c) => {
    const removed = removeSet.value.has(c.index)
    return {
      seg: c.index,
      label: `IC ${c.index}`,
      color: removed ? DANGER : NEUTRAL,
      marked: removed,
      sub: c.explained_variance != null ? `${c.explained_variance.toFixed(1)}%` : '',
      points: cellPoints(c),
    }
  }),
)

// 详情区单成分大地形图（单元素数组喂 TopoStrip）
const detailCells = computed<TopoCell[]>(() => {
  const c = activeComp.value
  if (!c) return []
  return [
    {
      seg: c.index,
      label: c.label,
      color: removeSet.value.has(c.index) ? DANGER : PRIMARY,
      marked: removeSet.value.has(c.index),
      points: cellPoints(c),
    },
  ]
})

// 三图数据（喂 TimeCourseCanvas：data=[x, ...ys]）
const tcSeries = [{ name: '激活', color: PRIMARY }]
const specSeries = [{ name: '功率', color: ACCENT }]
const cmpSeries = [
  { name: '原始', color: GRAY },
  { name: '去除后', color: PRIMARY },
]
const tcData = computed<number[][]>(() => (detail.value ? [detail.value.timecourse.times, detail.value.timecourse.values] : [[], []]))
const specData = computed<number[][]>(() => (detail.value ? [detail.value.spectrum.frequencies, detail.value.spectrum.power_db] : [[], []]))
const cmpData = computed<number[][]>(() => {
  const c = comparison.value
  if (!c || !c.has_comparison || !c.times || !c.original || !c.filtered) return [[], []]
  // 后端给的是 Volts（~1e-5），×1e6 换成 µV，坐标轴才可读。
  return [c.times, c.original.map((v) => v * 1e6), c.filtered.map((v) => v * 1e6)]
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
    // 提交决策后顺势恢复运行——消除旧版"已提交但实际没续跑"的割裂/误导（职责合一：本页既能选也能续跑）。
    try {
      await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/resume`, {})
      applyMsg.value = `已提交剔除 ${removeList.value.length} 个成分，流水线已继续运行。`
    } catch {
      applyMsg.value = `已提交剔除 ${removeList.value.length} 个成分；自动继续未成功，请回工作流点「继续运行」。`
    }
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

/* 成分墙工具区：排序选择 + 计数徽标 */
.ic-wall-tools { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.ic-sort { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--c-text-3); white-space: nowrap; }
.ic-sort-sel { font-size: 12px; padding: 2px 6px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; }

/* 详情三图 / 对比图：给 TimeCourseCanvas 宿主一个明确高度（其 .tcc-host 为 100%×100%） */
.ic-plot-host { height: 120px; position: relative; }
.ic-plot-host--wide { height: 132px; }

.ic-removelist { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.ic-removelist li { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.ic-removelist .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ic-x { margin-left: auto; border: none; background: none; color: var(--c-text-3); cursor: pointer; }
.ic-param-row { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; color: var(--c-text-2); }
.ica-applymsg { font-size: 12px; margin-top: 8px; color: var(--c-success); }
.ica-applymsg.is-error { color: var(--c-danger); }
</style>
