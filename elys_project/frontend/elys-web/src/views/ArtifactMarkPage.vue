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
        <span v-if="isLive && perf.firstPaint != null" class="am-perf" title="首屏分阶段耗时（诊断用，定位后会移除）">
          <AppIcon name="clock" :size="13" />
          初始化 {{ perf.mount ?? '·' }} · 拿交互 {{ perf.interaction ?? '·' }} · 取首窗 {{ perf.window ?? '·' }} · 渲染 {{ perf.render ?? '·' }} · 概览 {{ perf.overview ?? '…' }}<span class="am-perf-u"> ms</span>
        </span>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="reload">刷新</button>
      </div>

      <!-- 左栏：地形图 + 通道 + 滤波 + 信息（检测 / 清空已移到右栏） -->
      <aside class="am-left" v-if="isLive">
        <div class="am-card" v-if="topoCells.length">
          <div class="am-card-h">实时地形图 · 跟随游标</div>
          <TopoStrip :cells="topoCells" :vmax="topoVmax" subtitle="" unit="µV" />
        </div>

        <div class="am-card am-card--grow" v-if="ts">
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
          <div style="display: flex; gap: 8px;">
            <button class="btn btn--sm" :disabled="loading" @click="reload">重试</button>
            <button class="btn btn--sm" @click="returnToPipeline">返回工作流</button>
          </div>
        </div>
        <div v-else-if="loading && !ts" class="am-empty"><p class="muted">加载波形中…</p></div>

        <template v-else-if="ts">
          <div class="am-ctoolbar">
            <label class="am-num">窗长 <input type="number" v-model.number="visibleWinLen" min="1" step="1" /> s</label>
            <span class="am-presets">
              <button v-for="p in winPresets" :key="p.label" :class="{ on: isWinPreset(p.v) }" @click="setWinLen(p.v)">{{ p.label }}</button>
            </span>
            <label class="am-num">幅度 <input type="number" v-model.number="visibleAmp" min="1" step="10" /> µV</label>
            <span class="am-hint">← → 移窗 · 滚轮缩放 · Ctrl+滚轮调幅 · 拖动框选坏段 · 右键删段 · 下方全程概览拖动定位</span>
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
              :amp-scale="ampScale"
              :view-min="viewMin"
              :view-max="viewMax"
              :locked="cursorLockedX != null"
              :locked-x="cursorLockedX"
              :bad-segments="badSegments"
              :marked-channels="badChannelList"
              channel-pickable
              select-shadow
              :show-legend="false"
              @select="onSelect"
              @channel-pick="toggleChannel"
              @context-x="removeSegmentAt"
              @cursor="onCursor"
              @amp="ampScale = $event"
              @zoom="onZoom"
              @lock="onLock"
              @unlock="onUnlock"
            />
          </div>

          <div
            class="am-overview"
            v-if="overviewEnv.length"
            @pointerdown="ovPointerDown"
            @pointermove="ovPointerMove"
            @pointerup="ovPointerUp"
            @pointercancel="ovPointerUp"
          >
            <div class="am-ov-cap">全程概览 · 拖动定位窗口</div>
            <svg :viewBox="`0 0 ${OV_W} 34`" preserveAspectRatio="none" class="am-ov-svg">
              <rect :x="ovWinX" y="2" :width="ovWinW" height="30" fill="rgba(55,138,221,0.18)" stroke="rgba(55,138,221,0.65)" stroke-width="0.8" />
              <polyline :points="ovPolyline" fill="none" stroke="#E24B4A" stroke-width="1.2" />
            </svg>
            <div class="am-ov-axis">
              <span
                v-for="(tk, i) in ovTicks"
                :key="i"
                :style="{ left: tk.pct + '%', transform: i === 0 ? 'none' : i === ovTicks.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)' }"
              >{{ tk.label }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- 右栏：检测工具 / 坏段 / 坏道 / 处理方式 / 应用 -->
      <aside class="am-right" v-if="isLive">
        <div class="am-detect-group">
          <button class="am-detect" :disabled="autoRunning || !jobContext" @click="autoDetect">
            <AppIcon name="sparkles" :size="18" /> {{ autoRunning ? '自动检测中…' : '自动检测异常' }}
          </button>
          <button class="am-clear" :disabled="!badSegments.length && !badChannels.size" @click="clearAll">
            <AppIcon name="eraser" :size="14" /> 清空标记
          </button>
          <p v-if="autoMsg" class="am-automsg">{{ autoMsg }}</p>
        </div>
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
            <option value="interpolate">修复（改数据，需坐标）</option>
          </select>
        </div>
        <button class="btn btn--block btn--primary" :disabled="!canApply || applying" @click="submitAndReturn">
          <AppIcon name="check" :size="16" /> {{ applying ? '提交中…' : applyLabel }}
        </button>
        <button v-if="jobContext" class="btn btn--block mt-2" :disabled="applying" @click="returnToPipeline">
          <AppIcon name="chevron-left" :size="15" /> 取消 · 返回工作流
        </button>
        <p v-if="!jobContext" class="muted text-sm mt-2">查看模式：在工作流的「Artifact Mark」节点（等待人工）处打开本页才能提交。</p>
        <p v-if="applyMsg" class="am-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</p>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, dataApi } from '@/api/client'
import { decodeBinary } from '@/composables/observe/plotCache'
import { idbGet, idbSet } from '@/composables/observe/idbCache'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import TopoStrip from '@/components/observe/TopoStrip.vue'
import { useReviewerHandoff } from '@/composables/pipeline/useReviewerHandoff'
import type { PipelineInteraction, StudyOutputTimeseries } from '@/types'

interface ArtifactBadSegment { onset: number; duration: number; source?: string }
interface TopoCell { seg: number; label: string; color: string; points: { name: string; x: number; y: number; value: number }[] | null }

const GRAY = '#79859A'
const PALETTE = ['#3F5E8F', '#2E8B9A', '#8A6FB0', '#B0794F', '#5E8F6B', '#9A6B6B']
const PRIMARY = '#3F5E8F'
const OV_W = 470

// 首屏诊断探针：分阶段计时，定位「打开页面卡在取数还是初始化」。定位清楚后整套(perf/tSetup/计时点/计时条)可删。
const tSetup = performance.now()
const perf = ref<{ mount?: number; interaction?: number; window?: number; render?: number; firstPaint?: number; overview?: number }>({})

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
const jobContext = computed(() => Boolean(isLive.value && decisionVersion.value > 0))

const loading = ref(false)
const error = ref('')
const decisionVersion = ref(0)
// 按「节点输入」取波形/自动检测（不依赖 StudyOutput，LoadData 直连也能看），走数据服务器
const inputTsUrl = `/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/input-timeseries`
const autoArtifactsUrl = `/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/auto-artifacts`

const overview = ref<StudyOutputTimeseries | null>(null) // 粗全程（包络 + 总时长 + 坐标）
const ts = ref<StudyOutputTimeseries | null>(null) // 当前窗口细节

const winStart = ref(0)
const winLen = ref(10)
const ampUv = ref(80)
const ampScale = ref(1) // Ctrl+滚轮微调波幅（在 ampUv 基准上再缩放，spread 改泳道波高）
const viewMin = ref<number | null>(null) // 滚轮缩放时间轴的受控视窗（null=全窗）
const viewMax = ref<number | null>(null)
const cursorLockedX = ref<number | null>(null) // 双击锁定游标 → 冻结地形图到该时刻
const displayMode = ref<'spread' | 'overlay'>('spread')

const filterEnabled = ref(false)
const lFreq = ref(1)
const hFreq = ref(40)
const notch = ref(50)

const badSegments = ref<ArtifactBadSegment[]>([])
const badChannels = ref<Set<string>>(new Set())
const channelAction = ref<'mark' | 'interpolate'>('mark')
const topoValues = ref<Record<string, number>>({})

const autoRunning = ref(false)
const autoMsg = ref('')

// 「应用并返回」收尾（提交 decision→续跑→router.back 回工作流），与 ICA 共用同一套
const { applying, applyMsg, applyError, submitAndReturn, returnToPipeline } = useReviewerHandoff({
  studyId, executionId, jobId,
  decisionVersion: () => decisionVersion.value,
  buildBody: () => ({ bad_segments: badSegments.value, bad_channels: [...badChannels.value], channel_action: channelAction.value }),
  summary: () => `${badSegments.value.length} 段坏段 / ${badChannels.value.size} 个坏道`,
})

const sfreq = computed(() => (ts.value?.sfreq ?? overview.value?.sfreq ?? 0))
// 时长 / 范围优先用全程概览，没回来前回退到当前窗（让导航不必等概览加载）
const meta = computed(() => overview.value ?? ts.value)
const totalDuration = computed(() => meta.value?.total_duration ?? (meta.value?.times.length ? meta.value.times[meta.value.times.length - 1] : 0))
const rangeMin = computed(() => meta.value?.available_tmin ?? 0)
const rangeMax = computed(() => Math.max(rangeMin.value + winLen.value, meta.value?.available_tmax ?? totalDuration.value ?? rangeMin.value + winLen.value))
// 工具条「窗长 / 幅度」始终显示实际可见尺度（被滚轮 / Ctrl+滚轮缩放后随动）；编辑则设新基准并清缩放——根治「数字与画面对不上、没联动」
const visibleWinLen = computed<number>({
  get: () => (viewMin.value != null && viewMax.value != null) ? Math.round((viewMax.value - viewMin.value) * 10) / 10 : winLen.value,
  set: (v) => { const n = Math.max(1, Number(v) || winLen.value); viewMin.value = null; viewMax.value = null; winLen.value = n },
})
const visibleAmp = computed<number>({
  get: () => Math.round(ampUv.value / (ampScale.value > 0 ? ampScale.value : 1)),
  set: (v) => { const n = Math.max(1, Number(v) || ampUv.value); ampScale.value = 1; ampUv.value = n },
})
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
  // 用窗口(ts)的坐标——它取全部通道；概览(overview)只取 16 通道(算包络用)，坐标也只有 16，不能用来画地形图
  const pos = ts.value?.ch_pos
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
const ovDragStart = ref<number | null>(null) // 全览带拖动中的预览窗口起点：拖动时只移指示块、不发请求，松手才取数
const ovWinX = computed(() => (((ovDragStart.value ?? winStart.value) - rangeMin.value) / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)
const ovWinW = computed(() => (winLen.value / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)
// 全览带时间刻度：等分 5 段，标出对应秒数（否则看不出当前窗在整段记录的哪个时间）
const ovTicks = computed(() => {
  const lo = rangeMin.value, hi = rangeMax.value, span = hi - lo
  if (!(span > 0)) return [] as { pct: number; label: string }[]
  const N = 5
  return Array.from({ length: N + 1 }, (_, i) => {
    const t = lo + (i / N) * span
    return { pct: (i / N) * 100, label: `${t.toFixed(t < 10 ? 1 : 0)}s` }
  })
})

const canApply = computed(() => jobContext.value && !applying.value)
const applyLabel = computed(() => {
  const ns = badSegments.value.length
  const nc = badChannelList.value.length
  // 0 段 0 道 = 「看过了、这段干净」→ 合法的「确认放行」，文案讲清，避免看着像不能点
  if (ns === 0 && nc === 0) return '确认无伪迹 · 继续'
  return `应用（${ns} 段 / ${nc} 道）并继续`
})

function toggleChannel(name: string) {
  if (!name) return
  const next = new Set(badChannels.value)
  if (next.has(name)) next.delete(name); else next.add(name)
  badChannels.value = next
}
function removeSegment(index: number) { badSegments.value = badSegments.value.filter((_, i) => i !== index) }
// 右键波形落点处的坏段 → 删除（TimeCourseCanvas 右键 emit context-x）
function removeSegmentAt(x: number | null) {
  if (x == null) return
  const idx = badSegments.value.findIndex((s) => x >= s.onset && x <= s.onset + s.duration)
  if (idx >= 0) badSegments.value = badSegments.value.filter((_, i) => i !== idx)
}
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
// 窗长档位：10s 是默认而非上限（参考 EEGLAB「Time range to display」/ MNE raw.plot 的 duration——两者都能任意拉长到整段记录）。
// 滚轮只在已加载窗口内做精细缩放；要看更长一段直接点档位（一档=一次取数，契合「按窗取数」架构，不像内存里的 EEGLAB 能无限滚）。
const winPresets = [
  { v: 5, label: '5s' },
  { v: 10, label: '10s' },
  { v: 30, label: '30s' },
  { v: 0, label: '全程' }, // 0 = 整段记录
]
function setWinLen(v: number) {
  viewMin.value = null // 清掉滚轮缩放，回到整窗
  viewMax.value = null
  if (v <= 0) {
    winLen.value = Math.max(1, Math.ceil(totalDuration.value || winLen.value))
    winStart.value = rangeMin.value
    return
  }
  winLen.value = Math.max(1, v)
  setWinStart(winStart.value) // 用新窗长重新夹取起点
}
function isWinPreset(v: number): boolean {
  if (viewMin.value != null) return false // 正在滚轮缩放，不高亮任何档位
  if (v <= 0) return winLen.value >= (totalDuration.value || 0) - 0.5
  return Math.abs(winLen.value - v) < 0.5
}
// 全览带：按光标 x 算出「窗口起点」（光标落点居中），拖动定位
function ovStartFromClientX(clientX: number, el: HTMLElement): number {
  const rect = el.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width)))
  const target = rangeMin.value + ratio * (rangeMax.value - rangeMin.value) - winLen.value / 2
  return Math.max(rangeMin.value, Math.min(rangeMax.value - winLen.value, target))
}
function ovPointerDown(e: PointerEvent) {
  ;(e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId)
  ovDragStart.value = ovStartFromClientX(e.clientX, e.currentTarget as HTMLElement)
}
function ovPointerMove(e: PointerEvent) {
  if (ovDragStart.value == null) return // 仅按下后才跟随，悬停不动
  ovDragStart.value = ovStartFromClientX(e.clientX, e.currentTarget as HTMLElement)
}
function ovPointerUp() {
  if (ovDragStart.value == null) return
  setWinStart(ovDragStart.value) // 松手才真正取数（拖动途中只移指示块，避免每帧打后端）
  ovDragStart.value = null
}
function seekToSegment(seg: ArtifactBadSegment) { setWinStart(seg.onset - winLen.value / 2) }
function onZoom(view: { min: number; max: number } | null) {
  viewMin.value = view ? view.min : null
  viewMax.value = view ? view.max : null
}
function onLock(payload: { x: number; items: { name: string; uv: number }[] }) {
  cursorLockedX.value = payload.x
  const next: Record<string, number> = {}
  for (const it of payload.items) next[it.name] = it.uv
  topoValues.value = next // 冻结地形图到锁定时刻
}
function onUnlock() { cursorLockedX.value = null }

async function loadInteraction(): Promise<void> {
  const res = await api.get<PipelineInteraction>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/interaction`)
  const it = res.data
  decisionVersion.value = Number(it.decision_version || 0)
  const preview = (it.preview_json || {}) as { channel_action?: string; initial?: { bad_segments?: unknown; bad_channels?: unknown } }
  if (preview.channel_action === 'interpolate' || preview.channel_action === 'mark') channelAction.value = preview.channel_action
  badSegments.value = parseInitSegments(preview.initial?.bad_segments)
  badChannels.value = new Set(parseInitChannels(preview.initial?.bad_channels))
}

const tsCache = new Map<string, StudyOutputTimeseries>()
// IndexedDB / 内存 共用的全局唯一键：含 study/execution/job（execution 是不可变快照 → 天然版本指纹，
// 上游重跑=新 execution=新键，杜绝陈旧命中）+ 取数参数（窗口/采样/滤波）。
function inputTsKey(params: Record<string, number | undefined>): string {
  return `artifact::${studyId}::${executionId}::${jobId}::${JSON.stringify(params)}`
}
// 仅回源（二进制优先 / JSON 回退），供三级缓存未命中时调用
async function fetchInputNetwork(params: Record<string, number | undefined>): Promise<StudyOutputTimeseries> {
  try {
    // 二进制端点(EEGBIN01)：体积小 3–5 倍、免 JSON 序列化/解析、且已是 µV（省 V→µV 那 18 万次循环）。失败回退 JSON。
    const res = await dataApi.get(inputTsUrl, { params: { ...params, format: 'binary' }, responseType: 'arraybuffer' })
    const buf = res.data as ArrayBuffer
    if (!buf || buf.byteLength < 12) throw new Error('empty binary')
    const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 8))
    if (magic !== 'EEGBIN01') throw new Error('bad magic')
    return decodeBinary(buf) // 已是 µV，无需再换算
  } catch {
    const res = await dataApi.get<StudyOutputTimeseries>(inputTsUrl, { params })
    const data = res.data
    // JSON 通道值是伏特(V)；TimeCourseCanvas 期望 µV，统一 V→µV。
    if (data && data.unit !== 'uV' && Array.isArray(data.channels)) {
      for (const ch of data.channels) ch.values = ch.values.map((v) => v * 1e6)
      data.unit = 'uV'
    }
    return data
  }
}
// 三级取数：内存 → IndexedDB（跨刷新/重开页面仍命中）→ 网络；命中即回填更近层。
async function fetchInputTs(params: Record<string, number | undefined>): Promise<StudyOutputTimeseries> {
  const key = inputTsKey(params)
  const mem = tsCache.get(key)
  if (mem) return mem
  const idb = await idbGet<StudyOutputTimeseries>(key)
  if (idb) { tsCache.set(key, idb); return idb }
  const data = await fetchInputNetwork(params)
  tsCache.set(key, data)
  void idbSet(key, data) // best-effort 回填，失败静默
  return data
}
async function loadOverview() {
  overview.value = await fetchInputTs({ max_points: 1500, max_channels: 16 })
}
async function loadWindow() {
  viewMin.value = null // 换窗 → 回到整窗视图（清掉上一窗的滚轮缩放）
  viewMax.value = null
  const params: Record<string, number | undefined> = {
    // 10s 窗在屏宽下 3000 点已超像素、视觉无损；比 5000 省约 4 成 JSON 体积（提速）
    tmin: winStart.value, tmax: winStart.value + winLen.value, max_points: 3000, max_channels: 256,
  }
  if (filterEnabled.value) {
    if (lFreq.value > 0) params.l_freq = lFreq.value
    if (hFreq.value > 0) params.h_freq = hFreq.value
    if (notch.value > 0) params.notch = notch.value
  }
  const data = await fetchInputTs(params)
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
  const t0 = performance.now() // 诊断探针
  try {
    const tA = performance.now()
    await loadInteraction()
    const tB = performance.now()
    await loadWindow() // 先画当前窗（快）→ 波形立即可见
    const tC = performance.now()
    // 各阶段耗时：拿交互(入口) / 取首窗(计算·可能读整文件) / 首屏可见(两者串行总和)
    perf.value = { ...perf.value, interaction: Math.round(tB - tA), window: Math.round(tC - tB), firstPaint: Math.round(tC - t0) }
    // 渲染：首窗数据 → 下一帧（含 Vue patch + TimeCourseCanvas/uPlot 首次绘制 63 通道）
    requestAnimationFrame(() => { perf.value = { ...perf.value, render: Math.round(performance.now() - tC) } })
    document.title = `伪迹审核 · ${ts.value?.channels.length ?? 0} 通道 — 念析`
    const tD = performance.now()
    void loadOverview()
      .then(() => {
        perf.value = { ...perf.value, overview: Math.round(performance.now() - tD) }
        console.log('[artifact 首屏耗时 ms]', { ...perf.value }) // 诊断探针，定位后可删
      })
      .catch(() => { /* 全程概览较重，后台加载，失败不影响主图 */ })
  } catch (err: unknown) {
    // 节点已不在「等待人工」态（已处理/已续跑）→ /interaction 404 → 友好提示而非裸错误
    const msg = describeError(err)
    error.value = /interaction not found|interaction 不存在|找不到/i.test(msg)
      ? '该节点已处理完成或不在「等待人工」状态，无需在此标记——可返回工作流查看结果。'
      : msg
    ts.value = null
  } finally { loading.value = false }
}

// 窗口 / 滤波变 → 重取细节窗（粗全程不变）
let winSeq = 0
watch([winStart, winLen, filterEnabled, lFreq, hFreq, notch], async () => {
  if (!overview.value) return
  const my = ++winSeq
  try { await loadWindow() } catch { /* 保留旧窗 */ }
  void my
})

async function autoDetect() {
  if (!jobContext.value) return
  autoRunning.value = true
  autoMsg.value = ''
  try {
    const res = await dataApi.post<{ bad_channels: string[]; bad_segments: ArtifactBadSegment[]; n_bad_channels?: number; n_bad_segments?: number; segments_suppressed?: boolean }>(
      autoArtifactsUrl, {},
    )
    const sugCh = Array.isArray(res.data.bad_channels) ? res.data.bad_channels : []
    const sugSeg = Array.isArray(res.data.bad_segments) ? res.data.bad_segments : []
    const ch = new Set(badChannels.value)
    sugCh.forEach((n) => ch.add(String(n)))
    badChannels.value = ch
    sugSeg.forEach((s) => mergeInSegment({ onset: Number(s.onset), duration: Number(s.duration), source: 'auto' }))
    autoMsg.value = res.data.segments_suppressed
      ? `自动检测：建议 ${sugCh.length} 坏道；坏段疑似整体性误检（覆盖过广）已自动略过，请手动框选。`
      : `自动检测：建议 ${sugCh.length} 坏道 / ${sugSeg.length} 坏段，已并入（可再手动增删）。`
  } catch (err: unknown) { autoMsg.value = '自动检测失败：' + describeError(err) } finally { autoRunning.value = false }
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

onMounted(() => {
  perf.value = { ...perf.value, mount: Math.round(performance.now() - tSetup) } // 诊断探针：setup→挂载(组件初始化，不含取数)
  void reload()
})

// 键盘左右移窗（顶部箭头已撤；← →=步进 1/4 窗，Shift+← →=整窗翻页）
function onKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
  if (e.key === 'ArrowLeft') { e.preventDefault(); (e.shiftKey ? shiftWindow : stepWindow)(-1) }
  else if (e.key === 'ArrowRight') { e.preventDefault(); (e.shiftKey ? shiftWindow : stepWindow)(1) }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
:deep(.page) { padding: 0; }
.am-shell { display: grid; grid-template-columns: 210px minmax(0, 1fr) 232px; grid-template-rows: 56px 1fr; height: calc(100vh - var(--header-h)); overflow: hidden; }
.am-toolbar { grid-column: 1 / -1; display: flex; align-items: center; gap: var(--s-3); padding: 0 var(--s-5); background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.am-title { display: flex; align-items: center; gap: 8px; }
.am-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.am-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.am-perf { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--c-text-3); font-variant-numeric: tabular-nums; }
.am-perf-u { opacity: 0.7; }

.am-left { grid-column: 1; border-right: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow: hidden; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.am-card { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 6px 7px; }
/* 通道卡吃掉左栏剩余高度，让「整列滚动条」消失——只在通道列表内部滚 */
.am-card--grow { flex: 1 1 auto; min-height: 90px; display: flex; flex-direction: column; }
.am-card-h { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--c-text-2); margin-bottom: 5px; }
.am-tag-soft { font-size: 10px; padding: 0 5px; border-radius: 999px; background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.am-switch { margin-left: auto; font-size: 11px; color: var(--c-text-2); display: inline-flex; align-items: center; gap: 3px; cursor: pointer; }
.am-chanlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; flex: 1; min-height: 0; overflow-y: auto; }
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
/* 右栏检测工具：自动检测放大成主 CTA，清空作次级，成对置顶 */
.am-detect-group { display: flex; flex-direction: column; gap: 6px; }
.am-detect { display: flex; align-items: center; justify-content: center; gap: 7px; width: 100%; padding: 11px 12px; font-size: 14px; font-weight: 600; color: var(--c-primary); background: rgba(46, 107, 255, .06); border: 1.5px solid var(--c-primary); border-radius: var(--r-sm, 7px); cursor: pointer; transition: background .12s; }
.am-detect:hover:not(:disabled) { background: rgba(46, 107, 255, .12); }
.am-detect:disabled { opacity: .5; cursor: not-allowed; }
.am-clear { display: flex; align-items: center; justify-content: center; gap: 6px; width: 100%; padding: 6px 10px; font-size: 12px; color: var(--c-text-2); background: transparent; border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); cursor: pointer; }
.am-clear:hover:not(:disabled) { background: var(--c-bg-soft, #eef1f5); }
.am-clear:disabled { opacity: .45; cursor: not-allowed; }
.am-automsg { font-size: 11px; color: var(--c-text-3); margin: 0; line-height: 1.5; }

.am-center { grid-column: 2; padding: var(--s-3); min-width: 0; min-height: 0; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.am-ctoolbar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 4px 6px; font-size: 12px; }
.am-time { font-variant-numeric: tabular-nums; padding: 0 4px; min-width: 48px; text-align: center; }
.am-num { display: inline-flex; align-items: center; gap: 3px; color: var(--c-text-2); margin-left: 6px; }
.am-num input { width: 46px; padding: 2px 4px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 5px; }
.am-presets { display: inline-flex; border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; margin-left: 2px; }
.am-presets button { padding: 2px 8px; font-size: 11px; border: none; border-left: 1px solid var(--c-border); background: transparent; color: var(--c-text-2); cursor: pointer; }
.am-presets button:first-child { border-left: none; }
.am-presets button.on { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-hint { font-size: 11px; color: var(--c-text-3); margin-left: 8px; }
.am-modeswitch { margin-left: auto; display: inline-flex; border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.am-modeswitch button { padding: 2px 9px; font-size: 12px; border: none; background: transparent; color: var(--c-text-2); cursor: pointer; }
.am-modeswitch button.on { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-chart { flex: 1; min-height: 380px; position: relative; }
.am-overview { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 3px 5px; cursor: grab; touch-action: none; user-select: none; }
.am-overview:active { cursor: grabbing; }
.am-ov-cap { font-size: 10px; color: var(--c-text-3); margin-bottom: 1px; }
.am-ov-svg { width: 100%; height: 34px; display: block; }
.am-ov-axis { position: relative; height: 12px; margin-top: 1px; }
.am-ov-axis span { position: absolute; top: 0; font-size: 9px; color: var(--c-text-3); font-variant-numeric: tabular-nums; white-space: nowrap; }

.am-right { grid-column: 3; border-left: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow-y: auto; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.am-marklist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 3px; max-height: 240px; overflow-y: auto; }
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
