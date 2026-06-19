<template>
  <WorkbenchShell active-key="pipeline" active-top-key="analysis">
    <div class="am-shell">
      <div class="am-toolbar">
        <h1 class="page__title am-title" style="font-size: 22px; margin: 0">
          <AppIcon name="pulse" :size="22" /> 伪迹审核 · 标坏段 / 坏道
        </h1>
        <span v-if="isLive && ts" class="muted text-sm">
          {{ chNames.length }} 通道 · {{ totalDuration.toFixed(1) }} s · {{ sfreq }} Hz
        </span>
        <span class="am-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实数据' : '查看模式' }}</span>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="reload">刷新</button>
      </div>

      <!-- 左栏：地形图 + 通道 + 滤波 + 信息 + 自动/清空 -->
      <aside class="am-left" v-if="isLive">
        <div class="am-card" v-if="topoCells.length">
          <div class="am-card-h">实时地形图 · 跟随游标</div>
          <TopoStrip :cells="topoCells" :vmax="topoVmax" subtitle="" unit="µV" />
        </div>

        <div class="am-card" v-if="ts">
          <div class="am-card-h">通道 · 点名标坏道</div>
          <ul class="am-chanlist">
            <li
              v-for="name in chNames"
              :key="name"
              class="am-chan"
              :class="{ 'is-bad': badChannels.has(name) }"
              @click="toggleChannel(name)"
            >
              <span class="am-chan-dot" :style="{ background: badChannels.has(name) ? GRAY : colorOf(name) }"></span>
              <span class="am-chan-name">{{ name }}</span>
              <span v-if="badChannels.has(name)" class="am-chan-tag">坏</span>
            </li>
          </ul>
        </div>

        <div class="am-card">
          <div class="am-card-h">
            <span>在线滤波</span>
            <span class="am-tag-soft">仅看</span>
            <label class="am-switch"><input type="checkbox" v-model="filterEnabled" /> {{ filterEnabled ? '开' : '关' }}</label>
          </div>
          <div v-if="filterEnabled" class="am-filter">
            <label>高通 <input type="number" v-model.number="lFreq" step="0.1" min="0" /> Hz</label>
            <label>低通 <input type="number" v-model.number="hFreq" step="1" min="0" /> Hz</label>
            <label>陷波 <input type="number" v-model.number="notch" step="1" min="0" /> Hz</label>
            <p class="muted text-sm">仅用于观察，不写入、不影响计算。</p>
          </div>
        </div>

        <div class="am-card">
          <div class="am-card-h">EEG 信息</div>
          <div class="am-info">
            <span>采样率</span><strong>{{ sfreq }} Hz</strong>
            <span>通道</span><strong>{{ chNames.length }}</strong>
            <span>坏段</span><strong :class="{ 'is-danger': badSegments.length }">{{ badSegments.length }}</strong>
            <span>坏道</span><strong :class="{ 'is-danger': badChannelList.length }">{{ badChannelList.length }}</strong>
          </div>
        </div>

        <button class="btn btn--block am-auto" :disabled="autoRunning || !outputId" @click="autoDetect">
          <AppIcon name="sparkles" :size="15" /> {{ autoRunning ? '自动检测中…' : '自动检测异常' }}
        </button>
        <button class="btn btn--block" :disabled="!badSegments.length && !badChannels.size" @click="clearAll">
          <AppIcon name="eraser" :size="15" /> 清空
        </button>
        <p v-if="autoMsg" class="muted text-sm">{{ autoMsg }}</p>
      </aside>

      <!-- 中栏：工具条 + 波形 + 全览带 -->
      <div class="am-center">
        <div v-if="!isLive" class="am-empty">
          <AppIcon name="activity" :size="40" />
          <p class="am-empty-title">在工作流的「Artifact Mark」节点处打开本页</p>
          <p class="muted text-sm">在流水线里双击处于「等待人工」状态的去伪迹节点，即可框选坏段、点选坏道，确认后流水线自动继续。</p>
        </div>
        <div v-else-if="error" class="am-empty is-error">
          <AppIcon name="warning" :size="32" />
          <p class="am-empty-title">{{ error }}</p>
          <button class="btn btn--sm" :disabled="loading" @click="reload">重试</button>
        </div>
        <div v-else-if="loading && !ts" class="am-empty"><p class="muted">加载波形中…</p></div>

        <template v-else-if="ts">
          <div class="am-ctoolbar">
            <button class="btn btn--xs" :disabled="winStart <= rangeMin" title="上一窗" @click="shiftWindow(-1)"><AppIcon name="chevrons-left" :size="14" /></button>
            <button class="btn btn--xs" :disabled="winStart <= rangeMin" title="后退" @click="stepWindow(-1)"><AppIcon name="chevron-left" :size="14" /></button>
            <span class="am-time">{{ winStart.toFixed(1) }} s</span>
            <button class="btn btn--xs" :disabled="winStart >= rangeMax - winLen" title="前进" @click="stepWindow(1)"><AppIcon name="chevron-right" :size="14" /></button>
            <button class="btn btn--xs" :disabled="winStart >= rangeMax - winLen" title="下一窗" @click="shiftWindow(1)"><AppIcon name="chevrons-right" :size="14" /></button>
            <label class="am-num">窗长 <input type="number" v-model.number="winLen" min="1" step="1" /> s</label>
            <label class="am-num">幅度 <input type="number" v-model.number="ampUv" min="1" step="10" /> µV</label>
            <span class="am-modeswitch">
              <button :class="{ on: displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
              <button :class="{ on: displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            </span>
          </div>

          <div class="am-chart">
            <TimeCourseCanvas
              :data="chartData"
              :series="chartSeries"
              :display-mode="displayMode"
              x-label="时间 (s)"
              y-label=""
              :y-max="ampUv"
              :bad-segments="badSegments"
              :marked-channels="badChannelList"
              channel-pickable
              :show-legend="false"
              @select="onSelect"
              @channel-pick="toggleChannel"
              @cursor="onCursor"
            />
          </div>

          <div class="am-overview" v-if="overviewEnv.length" @click="seekOverview">
            <div class="am-ov-cap">全程概览 · 点击跳窗</div>
            <svg :viewBox="`0 0 ${OV_W} 34`" preserveAspectRatio="none" class="am-ov-svg">
              <rect :x="ovWinX" y="2" :width="ovWinW" height="30" fill="rgba(55,138,221,0.16)" />
              <polyline :points="ovPolyline" fill="none" stroke="#E24B4A" stroke-width="1.2" />
            </svg>
          </div>
        </template>
      </div>

      <!-- 右栏：坏段 / 坏道 / 处理方式 / 应用 -->
      <aside class="am-right" v-if="isLive">
        <div class="am-card">
          <div class="am-card-h">坏段 · {{ badSegments.length }} 段（{{ totalBadSeconds.toFixed(2) }} s）</div>
          <ul class="am-marklist">
            <li v-if="!badSegments.length" class="muted text-sm">拖拽波形框选标记坏段</li>
            <li v-for="(seg, i) in badSegments" :key="i" @click="seekToSegment(seg)">
              <span class="dot dot--danger"></span>
              {{ seg.onset.toFixed(2) }}–{{ (seg.onset + seg.duration).toFixed(2) }} s
              <button class="am-x" title="删除" @click.stop="removeSegment(i)"><AppIcon name="x" :size="13" /></button>
            </li>
          </ul>
        </div>
        <div class="am-card">
          <div class="am-card-h">坏道 · {{ badChannelList.length }}</div>
          <div class="am-chips">
            <span v-if="!badChannelList.length" class="muted text-sm">点波形或左栏通道名标坏道</span>
            <span v-for="name in badChannelList" :key="name" class="am-chip">{{ name }}<button class="am-x" @click="toggleChannel(name)"><AppIcon name="x" :size="12" /></button></span>
          </div>
        </div>
        <div class="am-card">
          <div class="am-card-h">坏道处理方式</div>
          <select v-model="channelAction" class="am-select">
            <option value="mark">仅标记（默认，不改数据）</option>
            <option value="interpolate">球面样条插值修复（改数据，需坐标）</option>
          </select>
        </div>
        <button class="btn btn--block btn--primary" :disabled="!canApply || applying" @click="applyDecision">
          <AppIcon name="check" :size="16" /> {{ applying ? '提交中…' : applyLabel }}
        </button>
        <p v-if="!jobContext" class="muted text-sm mt-2">查看模式：在工作流的「Artifact Mark」节点（等待人工）处打开本页才能提交。</p>
        <p v-if="applyMsg" class="am-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</p>
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
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { fetchTimeseries } from '@/composables/observe/plotCache'
import type { PipelineInteraction, StudyOutputTimeseries } from '@/types'

interface ArtifactBadSegment { onset: number; duration: number; source?: string }
interface TopoCell { seg: number; label: string; color: string; points: { name: string; x: number; y: number; value: number }[] | null }

const GRAY = '#79859A'
const PALETTE = ['#3F5E8F', '#2E8B9A', '#8A6FB0', '#B0794F', '#5E8F6B', '#9A6B6B']
const PRIMARY = '#3F5E8F'
const OV_W = 470

const route = useRoute()
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return (raw as string | null) ?? fallback
}

const studyId = qstr('studyId') || qstr('study')
const executionId = qstr('executionId') || qstr('execution_id')
const jobId = qstr('jobId') || qstr('job_id')

const isLive = computed(() => Boolean(studyId && executionId && jobId))
const jobContext = computed(() => Boolean(isLive.value && decisionVersion.value > 0 && outputId.value))

const loading = ref(false)
const error = ref('')
const outputId = ref('')
const decisionVersion = ref(0)

const overview = ref<StudyOutputTimeseries | null>(null) // 粗全程（包络 + 总时长 + 坐标）
const ts = ref<StudyOutputTimeseries | null>(null) // 当前窗口细节

const winStart = ref(0)
const winLen = ref(10)
const ampUv = ref(80)
const displayMode = ref<'spread' | 'overlay'>('spread')

const filterEnabled = ref(false)
const lFreq = ref(1)
const hFreq = ref(40)
const notch = ref(50)

const badSegments = ref<ArtifactBadSegment[]>([])
const badChannels = ref<Set<string>>(new Set())
const channelAction = ref<'mark' | 'interpolate'>('mark')
const topoValues = ref<Record<string, number>>({})

const applying = ref(false)
const applyMsg = ref('')
const applyError = ref(false)
const autoRunning = ref(false)
const autoMsg = ref('')

const sfreq = computed(() => (ts.value?.sfreq ?? overview.value?.sfreq ?? 0))
const totalDuration = computed(() => overview.value?.total_duration ?? (overview.value?.times.length ? overview.value.times[overview.value.times.length - 1] : 0))
const rangeMin = computed(() => overview.value?.available_tmin ?? 0)
const rangeMax = computed(() => Math.max(rangeMin.value + winLen.value, overview.value?.available_tmax ?? totalDuration.value ?? rangeMin.value + winLen.value))
const chNames = computed<string[]>(() => (ts.value ? ts.value.channels.map((c) => c.name) : []))
const badChannelList = computed(() => [...badChannels.value])
const totalBadSeconds = computed(() => badSegments.value.reduce((s, g) => s + g.duration, 0))

function colorOf(name: string): string {
  const i = chNames.value.indexOf(name)
  return PALETTE[(i < 0 ? 0 : i) % PALETTE.length]
}

const chartData = computed<number[][]>(() => {
  if (!ts.value) return [[], []]
  return [ts.value.times, ...ts.value.channels.map((c) => c.values)]
})
const chartSeries = computed(() =>
  (ts.value?.channels || []).map((c, i) => ({ name: c.name, color: badChannels.value.has(c.name) ? GRAY : PALETTE[i % PALETTE.length] })),
)

// 地形图：电极 2D 坐标 + 游标时刻各通道值（无游标用窗口均值）；单 cell 喂 TopoStrip
const topoCells = computed<TopoCell[]>(() => {
  const pos = overview.value?.ch_pos
  if (!pos) return []
  const pts = Object.keys(pos)
    .filter((name) => pos[name])
    .map((name) => ({ name, x: pos[name]![0], y: pos[name]![1], value: topoValues.value[name] ?? 0 }))
  if (pts.length < 3) return []
  return [{ seg: 0, label: '当前时刻', color: PRIMARY, points: pts }]
})
const topoVmax = computed(() => {
  let m = 0
  for (const v of Object.values(topoValues.value)) m = Math.max(m, Math.abs(v))
  return Math.max(1, Math.round(m))
})

// 底部全览带：粗全程逐时刻跨通道最大绝对值包络
const overviewEnv = computed<number[]>(() => {
  const o = overview.value
  if (!o || !o.times.length) return []
  const n = o.times.length
  const env = new Array(n).fill(0)
  for (const ch of o.channels) {
    for (let i = 0; i < n; i++) { const a = Math.abs(ch.values[i] || 0); if (a > env[i]) env[i] = a }
  }
  return env
})
const ovPolyline = computed(() => {
  const o = overview.value
  const env = overviewEnv.value
  if (!o || !env.length) return ''
  const t0 = o.times[0]; const t1 = o.times[o.times.length - 1]
  const span = Math.max(1e-6, t1 - t0)
  const maxAbs = Math.max(1e-9, ...env)
  return env.map((v, i) => `${((o.times[i] - t0) / span * OV_W).toFixed(1)},${(31 - (v / maxAbs) * 28).toFixed(1)}`).join(' ')
})
const ovWinX = computed(() => ((winStart.value - rangeMin.value) / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)
const ovWinW = computed(() => (winLen.value / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)

const canApply = computed(() => jobContext.value && !applying.value)
const applyLabel = computed(() => `应用（${badSegments.value.length} 段 / ${badChannelList.value.length} 道）并继续`)

function toggleChannel(name: string) {
  if (!name) return
  const next = new Set(badChannels.value)
  if (next.has(name)) next.delete(name); else next.add(name)
  badChannels.value = next
}
function removeSegment(index: number) { badSegments.value = badSegments.value.filter((_, i) => i !== index) }
function clearAll() { badSegments.value = []; badChannels.value = new Set() }

function onSelect(region: { x0: number; x1: number } | null) {
  if (!region) return
  const onset = Math.min(region.x0, region.x1)
  const stop = Math.max(region.x0, region.x1)
  if (!(stop > onset)) return
  mergeInSegment({ onset, duration: stop - onset, source: 'manual' })
}
function mergeInSegment(seg: ArtifactBadSegment) {
  const next = [...badSegments.value, seg].sort((a, b) => a.onset - b.onset)
  const merged: ArtifactBadSegment[] = []
  for (const s of next) {
    const prev = merged[merged.length - 1]
    if (prev && s.onset <= prev.onset + prev.duration) {
      const stop = Math.max(prev.onset + prev.duration, s.onset + s.duration)
      prev.duration = stop - prev.onset
    } else merged.push({ ...s })
  }
  badSegments.value = merged
}
function onCursor(payload: { x: number; items: { name: string; uv: number }[] } | null) {
  if (!payload) return
  const next: Record<string, number> = {}
  for (const it of payload.items) next[it.name] = it.uv
  topoValues.value = next
}

function stepWindow(dir: number) { setWinStart(winStart.value + dir * winLen.value * 0.25) }
function shiftWindow(dir: number) { setWinStart(winStart.value + dir * winLen.value) }
function setWinStart(v: number) {
  const clamped = Math.max(rangeMin.value, Math.min(rangeMax.value - winLen.value, v))
  winStart.value = Math.round(clamped * 1000) / 1000
}
function seekOverview(ev: MouseEvent) {
  const el = ev.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const ratio = (ev.clientX - rect.left) / Math.max(1, rect.width)
  const target = rangeMin.value + ratio * (rangeMax.value - rangeMin.value)
  setWinStart(target - winLen.value / 2)
}
function seekToSegment(seg: ArtifactBadSegment) { setWinStart(seg.onset - winLen.value / 2) }

async function loadInteraction(): Promise<boolean> {
  const res = await api.get<PipelineInteraction>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/interaction`)
  const it = res.data
  decisionVersion.value = Number(it.decision_version || 0)
  const preview = (it.preview_json || {}) as { datasets?: Array<{ output_id?: string | null }>; channel_action?: string; initial?: { bad_segments?: unknown; bad_channels?: unknown } }
  const datasets = Array.isArray(preview.datasets) ? preview.datasets : []
  outputId.value = String(datasets.find((d) => d && d.output_id)?.output_id || '')
  if (preview.channel_action === 'interpolate' || preview.channel_action === 'mark') channelAction.value = preview.channel_action
  badSegments.value = parseInitSegments(preview.initial?.bad_segments)
  badChannels.value = new Set(parseInitChannels(preview.initial?.bad_channels))
  return Boolean(outputId.value)
}

async function loadOverview() {
  const { ts: data } = await fetchTimeseries(studyId, outputId.value, { maxPoints: 1500, maxChannels: 16 })
  overview.value = data
}
async function loadWindow() {
  if (!outputId.value) return
  const params: { tmin: number; tmax: number; maxPoints: number; maxChannels: number; lFreq?: number; hFreq?: number; notch?: number } = {
    tmin: winStart.value, tmax: winStart.value + winLen.value, maxPoints: 5000, maxChannels: 256,
  }
  if (filterEnabled.value) {
    if (lFreq.value > 0) params.lFreq = lFreq.value
    if (hFreq.value > 0) params.hFreq = hFreq.value
    if (notch.value > 0) params.notch = notch.value
  }
  const { ts: data } = await fetchTimeseries(studyId, outputId.value, params)
  ts.value = data
  // 无游标时地形图用窗口均值
  if (!Object.keys(topoValues.value).length) {
    const mean: Record<string, number> = {}
    for (const ch of data.channels) { let s = 0; for (const v of ch.values) s += v; mean[ch.name] = ch.values.length ? s / ch.values.length : 0 }
    topoValues.value = mean
  }
}

async function reload() {
  if (!isLive.value) return
  loading.value = true
  error.value = ''
  try {
    if (!(await loadInteraction())) { error.value = '该节点的输入未保存为可视产物，无法加载波形（请在其前接一个会保存输出的步骤）。'; return }
    await loadOverview()
    await loadWindow()
    document.title = `伪迹审核 · ${ts.value?.channels.length ?? 0} 通道 — 念析`
  } catch (err: unknown) { error.value = describeError(err); ts.value = null } finally { loading.value = false }
}

// 窗口 / 滤波变 → 重取细节窗（粗全程不变）
let winSeq = 0
watch([winStart, winLen, filterEnabled, lFreq, hFreq, notch], async () => {
  if (!outputId.value || !overview.value) return
  const my = ++winSeq
  try { await loadWindow() } catch { /* 保留旧窗 */ }
  void my
})

async function autoDetect() {
  if (!outputId.value) return
  autoRunning.value = true
  autoMsg.value = ''
  try {
    const res = await dataApi.post<{ bad_channels: string[]; bad_segments: ArtifactBadSegment[]; n_bad_channels?: number; n_bad_segments?: number }>(
      `/studies/${studyId}/outputs/${outputId.value}/auto-artifacts`, {},
    )
    const sugCh = Array.isArray(res.data.bad_channels) ? res.data.bad_channels : []
    const sugSeg = Array.isArray(res.data.bad_segments) ? res.data.bad_segments : []
    const ch = new Set(badChannels.value)
    sugCh.forEach((n) => ch.add(String(n)))
    badChannels.value = ch
    sugSeg.forEach((s) => mergeInSegment({ onset: Number(s.onset), duration: Number(s.duration), source: 'auto' }))
    autoMsg.value = `自动检测：建议 ${sugCh.length} 坏道 / ${sugSeg.length} 坏段，已并入（可再手动增删）。`
  } catch (err: unknown) { autoMsg.value = '自动检测失败：' + describeError(err) } finally { autoRunning.value = false }
}

async function applyDecision() {
  if (!jobContext.value) return
  applying.value = true
  applyMsg.value = ''
  applyError.value = false
  try {
    await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/decision`, {
      bad_segments: badSegments.value, bad_channels: badChannelList.value, channel_action: channelAction.value, decision_version: decisionVersion.value,
    })
    try {
      await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/resume`, {})
      applyMsg.value = `已提交 ${badSegments.value.length} 段坏段 / ${badChannelList.value.length} 个坏道，流水线已继续运行。`
    } catch { applyMsg.value = '已提交标记；自动继续未成功，请回工作流点「继续运行」。' }
  } catch (err: unknown) { applyError.value = true; applyMsg.value = describeError(err) } finally { applying.value = false }
}

function parseInitSegments(value: unknown): ArtifactBadSegment[] {
  let arr: unknown = value
  if (typeof value === 'string' && value.trim()) { try { arr = JSON.parse(value) } catch { return [] } }
  if (!Array.isArray(arr)) return []
  const out: ArtifactBadSegment[] = []
  for (const item of arr) {
    const o = item as { onset?: unknown; duration?: unknown; source?: unknown }
    const onset = Number(o?.onset); const duration = Number(o?.duration)
    if (Number.isFinite(onset) && Number.isFinite(duration) && duration > 0) out.push({ onset, duration, source: typeof o?.source === 'string' ? o.source : 'manual' })
  }
  return out
}
function parseInitChannels(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) {
    const text = value.trim()
    if (text.startsWith('[')) { try { const arr = JSON.parse(text); if (Array.isArray(arr)) return arr.map((v) => String(v).trim()).filter(Boolean) } catch { return [] } }
    return text.replace(/;/g, ',').split(',').map((v) => v.trim()).filter(Boolean)
  }
  return []
}
function describeError(err: unknown): string {
  const e = err as { response?: { data?: { detail?: { message?: string } | string } }; message?: string }
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d?.message) return d.message
  return e?.message || '加载失败'
}

onMounted(reload)
</script>

<style scoped>
:deep(.page) { padding: 0; }
.am-shell { display: grid; grid-template-columns: 210px minmax(0, 1fr) 232px; grid-template-rows: 56px 1fr; min-height: calc(100vh - var(--header-h)); }
.am-toolbar { grid-column: 1 / -1; display: flex; align-items: center; gap: var(--s-3); padding: 0 var(--s-5); background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.am-title { display: flex; align-items: center; gap: 8px; }
.am-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.am-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }

.am-left { grid-column: 1; border-right: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.am-card { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 6px 7px; }
.am-card-h { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--c-text-2); margin-bottom: 5px; }
.am-tag-soft { font-size: 10px; padding: 0 5px; border-radius: 999px; background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.am-switch { margin-left: auto; font-size: 11px; color: var(--c-text-2); display: inline-flex; align-items: center; gap: 3px; cursor: pointer; }
.am-chanlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; max-height: 220px; overflow-y: auto; }
.am-chan { display: flex; align-items: center; gap: 6px; padding: 2px 5px; border-radius: 5px; font-size: 12px; cursor: pointer; }
.am-chan:hover { background: var(--c-bg-soft, #eef1f5); }
.am-chan.is-bad { color: var(--c-text-3); text-decoration: line-through; }
.am-chan-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.am-chan-name { flex: 1; }
.am-chan-tag { font-size: 10px; padding: 0 5px; border-radius: 999px; background: rgba(217, 119, 111, .18); color: var(--c-danger); }
.am-filter { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--c-text-2); }
.am-filter input { width: 54px; padding: 2px 5px; font-size: 11px; border: 1px solid var(--c-border); border-radius: 5px; }
.am-info { display: grid; grid-template-columns: 1fr auto; gap: 3px 8px; font-size: 12px; color: var(--c-text-3); }
.am-info strong { color: var(--c-text); text-align: right; }
.am-info strong.is-danger { color: var(--c-danger); }
.am-auto { border-color: var(--c-primary); color: var(--c-primary); justify-content: center; gap: 6px; }

.am-center { grid-column: 2; padding: var(--s-3); min-width: 0; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.am-ctoolbar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 4px 6px; font-size: 12px; }
.am-time { font-variant-numeric: tabular-nums; padding: 0 4px; min-width: 48px; text-align: center; }
.am-num { display: inline-flex; align-items: center; gap: 3px; color: var(--c-text-2); margin-left: 6px; }
.am-num input { width: 46px; padding: 2px 4px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 5px; }
.am-modeswitch { margin-left: auto; display: inline-flex; border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.am-modeswitch button { padding: 2px 9px; font-size: 12px; border: none; background: transparent; color: var(--c-text-2); cursor: pointer; }
.am-modeswitch button.on { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-chart { flex: 1; min-height: 380px; position: relative; }
.am-overview { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 3px 5px; cursor: pointer; }
.am-ov-cap { font-size: 10px; color: var(--c-text-3); margin-bottom: 1px; }
.am-ov-svg { width: 100%; height: 34px; display: block; }

.am-right { grid-column: 3; border-left: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.am-marklist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 3px; }
.am-marklist li { display: flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; padding: 2px 4px; border-radius: 5px; }
.am-marklist li:hover { background: var(--c-bg-soft, #eef1f5); }
.dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dot--danger { background: var(--c-danger); }
.am-x { margin-left: auto; border: none; background: none; color: var(--c-text-3); cursor: pointer; display: inline-flex; }
.am-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.am-chip { display: inline-flex; align-items: center; gap: 2px; font-size: 12px; padding: 2px 6px; border-radius: 999px; background: var(--c-bg-soft, #eef1f5); }
.am-select { width: 100%; padding: 5px 8px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 6px; background: var(--c-surface); }
.am-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.am-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.am-empty.is-error .am-empty-title { color: var(--c-danger); }
.am-applymsg { font-size: 12px; margin-top: 8px; color: var(--c-success); }
.am-applymsg.is-error { color: var(--c-danger); }
</style>
