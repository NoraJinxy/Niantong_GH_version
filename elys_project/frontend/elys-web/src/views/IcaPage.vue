<template>
  <WorkbenchShell active-key="ica" active-top-key="analysis">
    <div class="ica-shell">
      <!-- 顶部工具条 -->
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

      <!-- 空态 / 错误 / 加载 -->
      <div v-if="!isLive" class="ica-empty ica-empty--full">
        <AppIcon name="brain" :size="40" />
        <p class="ica-empty-title">从结果选择一个 ICA 结果查看成分</p>
        <p class="muted text-sm">
          在工作流运行「Compute ICA」节点后，于结果页或 ICA Apply 节点处打开本页，
          即可看到真实的成分地形图、时域、频谱与去除前后对比。
        </p>
      </div>
      <div v-else-if="error" class="ica-empty ica-empty--full is-error">
        <AppIcon name="warning" :size="32" />
        <p class="ica-empty-title">{{ error }}</p>
        <button class="btn btn--sm" :disabled="loading" @click="load">重试</button>
      </div>
      <div v-else-if="loading && !components.length" class="ica-empty ica-empty--full">
        <p class="muted">加载 ICA 成分中…</p>
      </div>

      <!-- 三区主体 + 底部操作条 -->
      <template v-else>
        <div class="ica-main">
          <!-- 左：成分墙（插值头皮场网格） -->
          <section class="ica-wall">
            <div class="ica-wall-head">
              <div class="ica-wall-title">成分墙 · {{ components.length }}</div>
              <div class="ica-wall-sub">单击看详情 · 双击标记剔除</div>
            </div>
            <div class="ica-wall-tools">
              <label class="ic-sort">
                排序
                <select v-model="sortMode" class="ic-sort-sel">
                  <option value="variance">方差 ↓</option>
                  <option value="index">编号</option>
                </select>
              </label>
              <span class="badge badge--primary">{{ keepCount }} 留 / {{ removeList.length }} 除</span>
            </div>
            <div class="ica-wall-body">
              <TopoStrip
                layout="grid"
                selectable
                :cells="componentCells"
                :vmax="1"
                :active-seg="selectedIndex"
                subtitle=""
                unit=""
                lo-label="−"
                hi-label="+"
                @cell-click="onCellClick"
                @cell-dblclick="toggleRemove"
              />
            </div>
          </section>

          <!-- 中：整体去除前后对比（主视图） -->
          <section class="ica-center">
            <div class="ica-center-head">
              <div class="ica-center-title">整体去除前后对比</div>
              <div class="ica-center-controls">
                <label>
                  通道
                  <select v-model="cmpChannel" class="ic-sort-sel">
                    <option v-for="ch in overview?.ch_names || []" :key="ch" :value="ch">{{ ch }}</option>
                  </select>
                </label>
                <label>
                  时窗
                  <select v-model.number="cmpSeconds" class="ic-sort-sel">
                    <option :value="10">前 10s</option>
                    <option :value="30">前 30s</option>
                    <option :value="60">前 60s</option>
                  </select>
                </label>
                <span v-if="previewLoading" class="ica-live">● 刷新中</span>
                <span v-else-if="preview?.has_comparison && preview.variance_reduction != null" class="ica-vr">
                  方差 ↓ {{ preview.variance_reduction }}%
                </span>
              </div>
            </div>
            <div class="ica-center-body">
              <div v-if="preview?.has_comparison" class="ica-cmp-host">
                <TimeCourseCanvas :data="previewData" :series="cmpSeries" x-label="时间 (s)" y-label="µV" show-legend />
              </div>
              <div v-else class="ica-cmp-empty">
                <AppIcon name="brain" :size="36" />
                <p class="ica-empty-title">标记要剔除的成分</p>
                <p class="muted text-sm">
                  在左侧成分墙双击成分（或在右栏点「标记剔除」），这里实时显示该通道去除前后的对比波形。
                  改任意成分组合都会自动刷新，方便比较不同剔除方案的整体效果。
                </p>
              </div>
            </div>
          </section>

          <!-- 右：选中成分详情 -->
          <aside v-if="activeComp" class="ica-detail">
            <div class="ica-detail-head">
              <div class="ica-detail-title">{{ activeComp.label }}</div>
              <div v-if="activeComp.explained_variance != null" class="muted text-sm">方差 {{ activeComp.explained_variance.toFixed(1) }}%</div>
            </div>

            <div class="ica-detail-sec">
              <div class="ica-detail-cap">地形图</div>
              <TopoStrip :cells="detailCells" :vmax="1" subtitle="" unit="" lo-label="−" hi-label="+" />
              <div class="muted text-sm ica-detail-chans">主导：{{ activeComp.top_channels.join(' · ') || '—' }}</div>
            </div>

            <div class="ica-detail-sec">
              <div class="ica-detail-cap">Welch 频谱 (dB)</div>
              <div class="ica-mini-host">
                <TimeCourseCanvas :data="specData" :series="specSeries" x-label="Hz" y-label="dB" :show-legend="false" use-spline :loading="detailLoading" />
              </div>
            </div>

            <div class="ica-detail-sec">
              <div class="ica-detail-cap">时域激活（源）</div>
              <div class="ica-mini-host">
                <TimeCourseCanvas :data="tcData" :series="tcSeries" x-label="s" y-label="" :show-legend="false" :loading="detailLoading" />
              </div>
            </div>

            <button
              class="btn btn--block"
              :class="isRemoved(activeComp.index) ? 'btn--danger' : 'btn--primary'"
              @click="toggleRemove(activeComp.index)"
            >
              {{ isRemoved(activeComp.index) ? '取消剔除' : '标记剔除' }}
            </button>
          </aside>
          <aside v-else class="ica-detail ica-detail--empty">
            <AppIcon name="brain" :size="28" />
            <p class="muted text-sm">点击成分查看地形图 / 频谱 / 时域激活</p>
          </aside>
        </div>

        <!-- 底部操作条：去除清单 + 应用并续跑 -->
        <div class="ica-bottom">
          <div class="ica-removelist">
            <span class="muted text-sm">待去除：</span>
            <span v-if="!removeList.length" class="muted text-sm">未标记任何成分</span>
            <button v-for="idx in removeList" :key="idx" class="ica-rmtag" title="点击取消剔除" @click="toggleRemove(idx)">
              {{ labelOf(idx) }} <span class="ica-rmtag-x">✕</span>
            </button>
          </div>
          <span v-if="applyMsg" class="ica-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</span>
          <span v-if="!jobContext" class="muted text-sm">查看模式 · 在工作流「ICA Apply」节点处打开才能提交</span>
          <button v-else class="btn btn--primary" :disabled="!canApply" @click="applyDecision">
            <AppIcon name="check" :size="16" />
            {{ applying ? '提交中…' : `应用去除 ${removeList.length} 个成分并继续` }}
          </button>
        </div>
      </template>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, dataApi } from '@/api/client'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import { useIcaComparison } from '@/composables/observe/useIcaComparison'

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
interface IcaDetail {
  index: number
  label: string
  explained_variance: number | null
  sfreq: number
  timecourse: { times: number[]; values: number[] }
  spectrum: { frequencies: number[]; power_db: number[]; fmax: number }
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

const detailMaxSeconds = 10 // 详情时域 / 频谱的时窗（与中心预览的 cmpSeconds 独立）
const isLive = computed(() => Boolean(studyId && outputId))
const jobContext = computed(() => Boolean(isLive.value && executionId && jobId && decisionVersion > 0))

const loading = ref(false)
const error = ref('')
const overview = ref<IcaComponentsResponse | null>(null)
const components = ref<IcaComponent[]>([])

const selectedIndex = ref<number | null>(null)
const detail = ref<IcaDetail | null>(null)
const detailLoading = ref(false)
let detailSeq = 0

const applying = ref(false)
const applyMsg = ref('')
const applyError = ref(false)

// 中心「整体去除前后对比」编排：剔除集是唯一事实源，墙/清单/应用都从这里派生。
const studyIdRef = ref(studyId)
const outputIdRef = ref(outputId)
const {
  excludedSet,
  preview,
  previewLoading,
  channel: cmpChannel,
  maxSeconds: cmpSeconds,
  toggle: toggleExcluded,
  setExcluded,
} = useIcaComparison(studyIdRef, outputIdRef, () => isLive.value)

const activeComp = computed(() => components.value.find((c) => c.index === selectedIndex.value) || null)
const keepCount = computed(() => components.value.length - excludedSet.value.size)
const removeList = computed(() => [...excludedSet.value].sort((a, b) => a - b))
const canApply = computed(() => jobContext.value && !applying.value)

function isRemoved(index: number): boolean {
  return excludedSet.value.has(index)
}
function toggleRemove(index: number) {
  toggleExcluded(index)
}
function labelOf(idx: number): string {
  return components.value.find((c) => c.index === idx)?.label || `IC${String(idx).padStart(3, '0')}`
}

// 单成分权重 → TopoStrip 电极点：除以该成分自身 vmax 归一到 [-1,1]，配合 TopoStrip vmax=1 实现"每成分独立归一"。
function cellPoints(c: IcaComponent): TopoCell['points'] {
  if (!c.has_positions) return null
  const m = c.vmax > 0 ? c.vmax : 1
  return c.topography.map((p) => ({ name: p.name, x: p.x, y: p.y, value: p.weight / m }))
}

// 成分墙排序：默认按方差↓先看影响最大的成分（ICA 审阅常规起手式）；可切回编号。
const sortMode = ref<'index' | 'variance'>('variance')
const sortedComponents = computed(() => {
  const list = [...components.value]
  if (sortMode.value === 'variance') {
    list.sort((a, b) => (b.explained_variance ?? -Infinity) - (a.explained_variance ?? -Infinity))
  }
  return list
})

// 成分墙：每成分一格插值地形图，颜色/标记态由剔除集驱动，sub 显解释方差%。
const componentCells = computed<TopoCell[]>(() =>
  sortedComponents.value.map((c) => {
    const removed = excludedSet.value.has(c.index)
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
      color: excludedSet.value.has(c.index) ? DANGER : PRIMARY,
      marked: excludedSet.value.has(c.index),
      points: cellPoints(c),
    },
  ]
})

// 详情两小图数据（喂 TimeCourseCanvas：data=[x, ...ys]）
const tcSeries = [{ name: '激活', color: PRIMARY }]
const specSeries = [{ name: '功率', color: ACCENT }]
const tcData = computed<number[][]>(() => (detail.value ? [detail.value.timecourse.times, detail.value.timecourse.values] : [[], []]))
const specData = computed<number[][]>(() => (detail.value ? [detail.value.spectrum.frequencies, detail.value.spectrum.power_db] : [[], []]))

// 中心整体对比：原始（灰） vs 去除后（蓝），同轴叠加；后端给 Volts，×1e6 换 µV。
const cmpSeries = [
  { name: '原始', color: GRAY },
  { name: '去除后', color: PRIMARY },
]
const previewData = computed<number[][]>(() => {
  const p = preview.value
  if (!p || !p.has_comparison || !p.times || !p.original || !p.filtered) return [[], []]
  return [p.times, p.original.map((v) => v * 1e6), p.filtered.map((v) => v * 1e6)]
})

async function load() {
  if (!isLive.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await dataApi.get<IcaComponentsResponse>(`/studies/${studyId}/outputs/${outputId}/ica-components`)
    overview.value = res.data
    components.value = res.data.components || []
    // 通道下拉默认首通道
    if (res.data.ch_names?.length && !cmpChannel.value) cmpChannel.value = res.data.ch_names[0]
    // 服务端已保存的剔除决策 → 灌进剔除集（顺带触发中心预览）
    setExcluded(new Set(res.data.exclude || []))
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

// 单击成分 → 拉详情（时域 + 频谱；去除前后对比交给中心视图，这里不再重复算，更快）
async function selectComponent(index: number) {
  selectedIndex.value = index
  const myId = ++detailSeq
  detailLoading.value = true
  try {
    const res = await dataApi.get<IcaDetail>(`/studies/${studyId}/outputs/${outputId}/ica-components/${index}`, {
      params: { max_seconds: detailMaxSeconds },
    })
    if (myId !== detailSeq) return
    detail.value = res.data
  } catch {
    if (myId === detailSeq) detail.value = null
  } finally {
    if (myId === detailSeq) detailLoading.value = false
  }
}

function onCellClick(index: number) {
  selectComponent(index)
}

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
    // 提交决策后顺势恢复运行——消除旧版"已提交但实际没续跑"的割裂（职责合一：本页既能选也能续跑）。
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
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - var(--header-h));
  max-height: calc(100vh - var(--header-h));
}
.ica-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 0 var(--s-5);
  height: 56px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}
.ica-title { display: flex; align-items: center; gap: 8px; }
.ica-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.ica-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.ica-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }

.ica-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.ica-empty--full { flex: 1; }
.ica-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.ica-empty.is-error .ica-empty-title { color: var(--c-danger); }

/* ── 三区主体 ── */
.ica-main { flex: 1; display: flex; min-height: 0; overflow: hidden; }

/* 左：成分墙 */
.ica-wall {
  width: 256px; min-width: 256px;
  border-right: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.ica-wall-head { padding: 10px 12px 4px; }
.ica-wall-title { font-weight: 600; font-size: 13px; color: var(--c-text); }
.ica-wall-sub { font-size: 11px; color: var(--c-text-3); margin-top: 2px; }
.ica-wall-tools { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 4px 12px 8px; border-bottom: 1px solid var(--c-border); }
.ic-sort { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: var(--c-text-3); white-space: nowrap; }
.ic-sort-sel { font-size: 12px; padding: 2px 6px; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; }
.ica-wall-body { flex: 1; overflow-y: auto; padding: 8px; min-height: 0; }

/* 中：整体去除前后对比（主视图） */
.ica-center { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.ica-center-head { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.ica-center-title { font-weight: 600; font-size: 14px; color: var(--c-text); }
.ica-center-controls { display: inline-flex; align-items: center; gap: 14px; font-size: 12px; color: var(--c-text-3); }
.ica-center-controls label { display: inline-flex; align-items: center; gap: 5px; }
.ica-live { color: var(--c-primary); font-size: 12px; }
.ica-vr { color: var(--c-success); font-size: 12px; font-weight: 600; }
.ica-center-body { flex: 1; min-height: 0; padding: 14px 16px; display: flex; }
.ica-cmp-host { flex: 1; min-height: 0; position: relative; }
.ica-cmp-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; color: var(--c-text-3); padding: 24px; max-width: 420px; margin: 0 auto; }

/* 右：选中成分详情 */
.ica-detail {
  width: 224px; min-width: 224px;
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  display: flex; flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 12px;
}
.ica-detail--empty { align-items: center; justify-content: center; text-align: center; color: var(--c-text-3); }
.ica-detail-head { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
.ica-detail-title { font-weight: 600; font-size: 13px; color: var(--c-text); }
.ica-detail-sec { display: flex; flex-direction: column; gap: 5px; }
.ica-detail-cap { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; color: var(--c-text-3); }
.ica-detail-chans { font-size: 11px; }
.ica-mini-host { height: 76px; position: relative; }

/* 底部操作条 */
.ica-bottom {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}
.ica-removelist { flex: 1; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
.ica-rmtag { display: inline-flex; align-items: center; gap: 4px; background: rgba(239, 68, 68, .1); color: var(--c-danger); border: 1px solid rgba(239, 68, 68, .25); border-radius: var(--r-sm); padding: 2px 8px; font-size: 12px; cursor: pointer; }
.ica-rmtag:hover { background: rgba(239, 68, 68, .16); }
.ica-rmtag-x { opacity: .55; }
.ica-applymsg { font-size: 12px; color: var(--c-success); }
.ica-applymsg.is-error { color: var(--c-danger); }
</style>
