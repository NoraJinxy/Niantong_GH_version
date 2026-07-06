<template>
  <WorkbenchShell active-key="pipeline" active-top-key="analysis">
    <div class="ev-shell">
      <HotkeyHelp v-if="helpOpen" :groups="helpGroups" :mouse-hints="mouseHints" @close="helpOpen = false" />
      <div class="ev-toolbar">
        <h1 class="page__title ev-title" style="font-size: 22px; margin: 0">
          <AppIcon name="bookmark" :size="22" /> 事件管理器 · 标记梳理
        </h1>
        <span v-if="isLive && ts" class="muted text-sm">
          {{ events.length }} 事件 · {{ distinctLabels.length }} 类 · {{ totalDuration.toFixed(1) }} s
        </span>
        <span class="ev-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实数据' : '查看模式' }}</span>
        <label v-if="datasets.length > 1" class="ev-dssel">
          数据集
          <select :value="activeDsIndex" @change="onDatasetSelect">
            <option v-for="(d, i) in datasets" :key="i" :value="i">{{ d.label }}</option>
          </select>
        </label>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="reload">刷新</button>
      </div>

      <!-- 左栏：事件类型图层 + 批量 + 滤波 + 信息 -->
      <aside class="ev-left" v-if="isLive">
        <div class="ev-card ev-card--grow" v-if="ts">
          <div class="ev-card-h">事件类型 · 点名选中 · 勾选批量</div>
          <ul class="ev-typelist">
            <li v-if="!labelTypes.length" class="muted text-sm" style="padding: 6px 2px">暂无事件，切「新增」模式点波形添加</li>
            <li
              v-for="t in labelTypes"
              :key="t.label"
              class="ev-type"
              :class="{ 'is-sel': selectedType === t.label, 'is-hidden': !visibleTypes.has(t.label) }"
              @click="selectType(t.label)"
            >
              <input type="checkbox" class="ev-check" :checked="checkedTypes.has(t.label)" @change="toggleCheck(t.label)" @click.stop />
              <span class="ev-type-dot" :style="{ background: visibleTypes.has(t.label) ? t.color : GRAY }"></span>
              <span class="ev-type-name">{{ t.label }}</span>
              <span class="ev-type-cnt">{{ t.count }}</span>
              <button class="ev-eye" :title="visibleTypes.has(t.label) ? '隐藏' : '显示'" @click.stop="toggleVisible(t.label)">
                <AppIcon :name="visibleTypes.has(t.label) ? 'eye' : 'eye-off'" :size="14" />
              </button>
            </li>
          </ul>
        </div>

        <div class="ev-card" v-if="checkedTypes.size">
          <div class="ev-card-h">批量 · 已选 {{ checkedTypes.size }} 类</div>
          <input v-model.trim="bulkTarget" class="ev-input" placeholder="目标名（改成 / 合并到）" @keyup.enter="applyBulkRename" />
          <div class="ev-bulk-btns">
            <button class="btn btn--sm" :disabled="!bulkTarget" @click="applyBulkRename">{{ checkedTypes.size > 1 ? '合并' : '改名' }}</button>
            <button class="btn btn--sm ev-btn-danger" @click="applyBulkDelete">删除</button>
          </div>
        </div>

        <div class="ev-card">
          <div class="ev-card-h">
            <span>在线滤波</span>
            <span class="ev-tag-soft">仅看</span>
            <label class="ev-switch"><input type="checkbox" v-model="filterEnabled" /> {{ filterEnabled ? '开' : '关' }}</label>
          </div>
          <div v-if="filterEnabled" class="ev-filter">
            <label>高通 <input type="number" v-model.number="lFreq" step="0.1" min="0" /> Hz</label>
            <label>低通 <input type="number" v-model.number="hFreq" step="1" min="0" /> Hz</label>
            <label>陷波 <input type="number" v-model.number="notch" step="1" min="0" /> Hz</label>
            <p class="muted text-sm">仅用于观察，不写入、不影响计算。</p>
          </div>
        </div>

        <div class="ev-card">
          <div class="ev-card-h">EEG 信息</div>
          <div class="ev-info">
            <span>事件</span><strong>{{ events.length }}</strong>
            <span>类型</span><strong>{{ distinctLabels.length }}</strong>
            <span>坏段</span><strong>{{ badSegments.length }}</strong>
            <span>采样率</span><strong>{{ sfreq }} Hz</strong>
            <span>通道</span><strong>{{ totalCh }}</strong>
          </div>
        </div>
      </aside>

      <!-- 中栏：工具条 + 波形（叠 marker） + 全览带 -->
      <div class="ev-center">
        <div v-if="!isLive" class="ev-empty">
          <AppIcon name="bookmark" :size="40" />
          <p class="ev-empty-title">在工作流的「Event Manager」节点处打开本页</p>
          <p class="muted text-sm">在流水线里双击处于「等待人工」状态的事件管理节点，即可全局梳理 marker、添删改，确认后流水线自动继续。</p>
        </div>
        <div v-else-if="error" class="ev-empty is-error">
          <AppIcon name="warning" :size="32" />
          <p class="ev-empty-title">{{ error }}</p>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn--sm" :disabled="loading" @click="reload">重试</button>
            <button class="btn btn--sm" @click="returnToPipeline">返回工作流</button>
          </div>
        </div>
        <div v-else-if="loading && !ts" class="ev-empty"><p class="muted">加载波形中…</p></div>

        <template v-else-if="ts">
          <div class="ev-ctoolbar">
            <span class="ev-modeswitch">
              <button :class="{ on: mode === 'select' }" @click="mode = 'select'" title="选择 / 编辑事件（v）"><AppIcon name="pointer" :size="13" /> 选择</button>
              <button :class="{ on: mode === 'add' }" @click="mode = 'add'" title="点击波形新增事件（n）"><AppIcon name="plus" :size="13" /> 新增</button>
            </span>
            <label v-if="mode === 'add'" class="ev-num">标签 <input v-model.trim="activeNewLabel" class="ev-input ev-input--inline" placeholder="新事件名" /></label>
            <label class="ev-num">窗长 <input type="number" v-model.number="visibleWinLen" min="1" step="1" /> s</label>
            <span class="ev-presets">
              <button v-for="p in winPresets" :key="p.label" :class="{ on: isWinPreset(p.v) }" @click="setWinLen(p.v)">{{ p.label }}</button>
            </span>
            <label class="ev-num">幅度 <input type="number" v-model.number="visibleAmp" min="1" step="10" /> µV</label>
            <span class="ev-chanpager" v-if="totalCh">
              <button class="ev-pgbtn" :disabled="chanStart <= 0" @click="chanPageBy(-1)" title="上一页通道">▲</button>
              <span class="ev-chanrange">通道 {{ chanStart + 1 }}–{{ chanEnd }} / {{ totalCh }}</span>
              <button class="ev-pgbtn" :disabled="chanEnd >= totalCh" @click="chanPageBy(1)" title="下一页通道">▼</button>
              <span class="ev-presets">
                <button v-for="p in chanPresets" :key="p.label" :class="{ on: isChanPreset(p.v) }" @click="setChanPerPage(p.v)">{{ p.label }}</button>
              </span>
            </span>
            <button type="button" class="btn btn--sm" @click="helpOpen = true" title="操作与快捷键（?）">🖱 操作提示</button>
            <span class="ev-modeswitch ev-modeswitch--right">
              <button :class="{ on: displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
              <button :class="{ on: displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            </span>
          </div>

          <div class="ev-chart">
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
              :markers="visibleMarkers"
              :bad-segments="showBad ? badSegments : []"
              select-shadow
              :show-legend="false"
              @select="onSelect"
              @context-x="onContextX"
              @cursor="onCursor"
              @amp="ampScale = $event"
              @zoom="onZoom"
              @lock="onLock"
              @unlock="onUnlock"
            />
          </div>

          <div
            class="ev-overview"
            v-if="overviewEnv.length"
            @pointerdown="ovPointerDown"
            @pointermove="ovPointerMove"
            @pointerup="ovPointerUp"
            @pointercancel="ovPointerUp"
          >
            <div class="ev-ov-cap">全程概览 · 拖动定位窗口 · <span class="ev-ov-cap-mark">竖线＝事件（{{ events.length }}）</span></div>
            <svg :viewBox="`0 0 ${OV_W} 34`" preserveAspectRatio="none" class="ev-ov-svg">
              <polyline :points="ovPolyline" fill="none" stroke="#8593A6" stroke-width="1.1" />
              <rect :x="ovWinX" y="2" :width="ovWinW" height="30" fill="rgba(63,127,191,0.18)" stroke="rgba(63,127,191,0.65)" stroke-width="0.8" />
              <line v-for="(m, i) in ovEventMarks" :key="i" :x1="m.x" y1="2" :x2="m.x" y2="32" :stroke="m.color" stroke-width="0.8" />
            </svg>
            <div class="ev-ov-axis">
              <span
                v-for="(tk, i) in ovTicks"
                :key="i"
                :style="{ left: tk.pct + '%', transform: i === 0 ? 'none' : i === ovTicks.length - 1 ? 'translateX(-100%)' : 'translateX(-50%)' }"
              >{{ tk.label }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- 右栏：明细表 + 检查器 + 暂存 + 应用 -->
      <aside class="ev-right" v-if="isLive">
        <div class="ev-right-top">
          <div class="ev-card">
          <div class="ev-card-h">
            <span>{{ selectedType ? selectedType + ' · 明细' : '明细（选左侧类型）' }}</span>
            <span v-if="selectedType" class="ev-card-cnt">{{ occurrences.length }}</span>
          </div>
          <ul class="ev-occlist">
            <li v-if="selectedType && !occurrences.length" class="muted text-sm">此类型无事件</li>
            <li v-if="!selectedType" class="muted text-sm">点左侧某个事件类型查看每一次出现</li>
            <li
              v-for="e in occurrences"
              :key="e.id"
              class="ev-occ"
              :class="{ 'is-sel': selectedEventId === e.id }"
              @click="selectEvent(e)"
            >
              <span class="ev-occ-dot" :style="{ background: colorForLabel(e.description) }"></span>
              <span class="ev-occ-t">{{ fmtTime(e.onset) }}</span>
              <span class="ev-occ-d">{{ e.duration > 0 ? e.duration.toFixed(2) + 's' : '·' }}</span>
              <button class="ev-x" title="删除" @click.stop="deleteEvent(e.id)"><AppIcon name="x" :size="12" /></button>
            </li>
          </ul>
        </div>

        <div class="ev-card" v-if="selectedEvent">
          <div class="ev-card-h">选中事件 #{{ selectedEvent.id }}</div>
          <div class="ev-insp">
            <label>标签 <input v-model.trim="inspLabel" class="ev-input" /></label>
            <label>起始 <input type="number" v-model.number="inspOnset" step="0.01" min="0" /> s</label>
            <label>时长 <input type="number" v-model.number="inspDuration" step="0.01" min="0" /> s</label>
            <button class="btn btn--sm ev-seek" @click="seekTo(selectedEvent.onset)">定位到此事件</button>
          </div>
        </div>

        <div class="ev-card ev-draft">
          <div class="ev-card-h">暂存改动</div>
          <div class="ev-chips">
            <span class="ev-chip ev-chip--add" v-if="diff.added">+{{ diff.added }} 新增</span>
            <span class="ev-chip ev-chip--del" v-if="diff.removed">−{{ diff.removed }} 删除</span>
            <span class="ev-chip ev-chip--chg" v-if="diff.changed">{{ diff.changed }} 改</span>
            <span class="ev-chip" v-if="groupOps.length">{{ groupOps.length }} 规则</span>
            <span v-if="!dirty" class="muted text-sm">尚无改动</span>
          </div>
          <p class="muted text-sm" v-if="dirty" style="margin: 6px 0 0">{{ originalCount }} → {{ events.length }} 事件</p>
          <label class="ev-promote" v-if="groupOps.length">
            <input type="checkbox" v-model="promoteRules" />
            把分组改名固化成规则，套用到本节点全部数据集
          </label>
        </div>

        <button class="btn btn--block btn--primary" :disabled="!canApply || applying" @click="submitAndReturn" title="确认梳理并续跑工作流（Ctrl+Enter）">
          <AppIcon name="check" :size="16" /> {{ applying ? '提交中…' : applyLabel }}
        </button>
        <button v-if="jobContext" class="btn btn--block mt-2" :disabled="applying" @click="returnToPipeline">
          <AppIcon name="chevron-left" :size="15" /> 取消 · 返回工作流
        </button>
        <p v-if="!jobContext" class="muted text-sm mt-2">查看模式：在工作流的「Event Manager」节点（等待人工）处打开本页才能提交。</p>
          <p v-if="applyMsg" class="ev-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</p>
        </div>

        <div class="ev-card ev-dataset-card" v-if="datasets.length">
          <div class="ev-card-h">
            <span>数据集</span>
            <span class="ev-card-cnt">{{ activeDsIndex + 1 }}/{{ datasets.length }}</span>
          </div>
          <ul class="ev-dataset-list">
            <li
              v-for="(d, i) in datasets"
              :key="d.output_id || d.label || i"
              class="ev-dataset"
              :class="{ 'is-active': i === activeDsIndex }"
              @click="selectDataset(i)"
            >
              <span class="ev-dataset-dot"></span>
              <span class="ev-dataset-name" :title="d.label">{{ d.label }}</span>
              <span class="ev-dataset-count">{{ datasetEventCount(d, i) }} 事件</span>
            </li>
          </ul>
        </div>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, dataApi } from '@/api/client'
import { decodeBinary } from '@/composables/observe/plotCache'
import { idbGet, idbSet } from '@/composables/observe/idbCache'
import { useObserveHotkeys, type HotkeyDef } from '@/composables/observe/useObserveHotkeys'
import HotkeyHelp from '@/components/observe/HotkeyHelp.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import { useReviewerHandoff } from '@/composables/pipeline/useReviewerHandoff'
import type { PipelineInteraction, StudyOutputTimeseries } from '@/types'

interface EventItem { id: number; onset: number; duration: number; description: string }
interface GroupOp { op: 'rename' | 'merge' | 'delete'; sources: string[]; target?: string }
interface DatasetMeta { label: string; output_id?: string; events: EventItem[]; bad_segments: { onset: number; duration: number }[] }

const GRAY = '#79859A'
// 通道线用低饱和中性色，把鲜艳留给事件 marker（colorForLabel）→ 事件在波形上一眼可辨
const CHAN_PALETTE = ['#6E7B91', '#5E7C8F', '#7A7290', '#8A8470', '#6B8478', '#80727A']
// 事件类型配色（与观察家族同调的钢蓝系起手，分类用、非渐变）
const EVENT_PALETTE = ['#378ADD', '#1D9E75', '#BA7517', '#8A6FB0', '#D4537E', '#5E8F6B', '#B0794F', '#2E8B9A', '#9A6B6B', '#637FA5']
const OV_W = 470
const CHAN_ALL = 9999
let uid = 1

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
const inputTsUrl = `/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/input-timeseries`

const datasets = ref<DatasetMeta[]>([])
const activeDsIndex = ref(0)
const events = ref<EventItem[]>([])
const originalEvents = ref<EventItem[]>([]) // 快照，算暂存改动 diff
const badSegments = ref<{ onset: number; duration: number }[]>([]) // 只读 BAD_ 上下文层

const overview = ref<StudyOutputTimeseries | null>(null)
const ts = ref<StudyOutputTimeseries | null>(null)

const winStart = ref(0)
const winLen = ref(10)
const ampUv = ref(80)
const ampScale = ref(1)
const viewMin = ref<number | null>(null)
const viewMax = ref<number | null>(null)
const cursorLockedX = ref<number | null>(null)
const cursorX = ref<number | null>(null)
const displayMode = ref<'spread' | 'overlay'>('spread')
// 通道分页（高密度脑电 64/128/256 道不全塞一屏；同 ArtifactMarkPage）：一屏 chanPerPage 道、纵向翻页。
const chanPerPage = ref(32)
const chanStart = ref(0)

const filterEnabled = ref(false)
const lFreq = ref(1)
const hFreq = ref(40)
const notch = ref(50)

// 编辑态
const mode = ref<'select' | 'add'>('select')
const activeNewLabel = ref('事件')
const selectedType = ref<string | null>(null)
const selectedEventId = ref<number | null>(null)
const visibleTypes = ref<Set<string>>(new Set())
const checkedTypes = ref<Set<string>>(new Set())
const bulkTarget = ref('')
const groupOps = ref<GroupOp[]>([])
const promoteRules = ref(true)
const showBad = ref(true)

const { applying, applyMsg, applyError, submitAndReturn, returnToPipeline, describeError } = useReviewerHandoff({
  studyId, executionId, jobId,
  decisionVersion: () => decisionVersion.value,
  buildBody: () => {
    snapshotCurrentDatasetEvents()
    return {
      type: 'event_editing',
      events: events.value.map((e) => ({ onset: e.onset, duration: e.duration, description: e.description })),
      group_operations: promoteRules.value ? groupOps.value : [],
      operations: operationsSummary(),
    }
  },
  summary: () => {
    snapshotCurrentDatasetEvents()
    const totals = eventManagerTotals()
    return `${totals.events} 事件 / ${totals.labels} 类 / ${datasets.value.length || 1} 个数据集`
  },
})

const sfreq = computed(() => (ts.value?.sfreq ?? overview.value?.sfreq ?? 0))
const meta = computed(() => overview.value ?? ts.value)
const totalDuration = computed(() => meta.value?.total_duration ?? (meta.value?.times.length ? meta.value.times[meta.value.times.length - 1] : 0))
const rangeMin = computed(() => meta.value?.available_tmin ?? 0)
const rangeMax = computed(() => Math.max(rangeMin.value + winLen.value, meta.value?.available_tmax ?? totalDuration.value ?? rangeMin.value + winLen.value))
const visibleWinLen = computed<number>({
  get: () => (viewMin.value != null && viewMax.value != null) ? Math.round((viewMax.value - viewMin.value) * 10) / 10 : winLen.value,
  set: (v) => { const n = Math.max(1, Number(v) || winLen.value); viewMin.value = null; viewMax.value = null; winLen.value = n },
})
const visibleAmp = computed<number>({
  get: () => Math.round(ampUv.value / (ampScale.value > 0 ? ampScale.value : 1)),
  set: (v) => { const n = Math.max(1, Number(v) || ampUv.value); ampScale.value = 1; ampUv.value = n },
})

// —— 事件类型派生 ——
const distinctLabels = computed(() => [...new Set(events.value.map((e) => e.description))].sort((a, b) => a.localeCompare(b)))
const labelIndex = computed(() => { const m = new Map<string, number>(); distinctLabels.value.forEach((l, i) => m.set(l, i)); return m })
function colorForLabel(label: string): string { return EVENT_PALETTE[(labelIndex.value.get(label) ?? 0) % EVENT_PALETTE.length] }
const labelTypes = computed(() => {
  const m = new Map<string, number>()
  for (const e of events.value) m.set(e.description, (m.get(e.description) || 0) + 1)
  return distinctLabels.value.map((label) => ({ label, count: m.get(label) || 0, color: colorForLabel(label) }))
})

const occurrences = computed(() => events.value.filter((e) => e.description === selectedType.value).sort((a, b) => a.onset - b.onset))
const selectedEvent = computed(() => events.value.find((e) => e.id === selectedEventId.value) || null)
const inspLabel = computed<string>({ get: () => selectedEvent.value?.description ?? '', set: (v) => { if (selectedEvent.value && v.trim()) relabelEvent(selectedEvent.value.id, v.trim()) } })
const inspOnset = computed<number>({ get: () => selectedEvent.value ? Math.round(selectedEvent.value.onset * 1000) / 1000 : 0, set: (v) => { if (selectedEvent.value) retimeEvent(selectedEvent.value.id, Math.max(0, Number(v) || 0)) } })
const inspDuration = computed<number>({ get: () => selectedEvent.value ? Math.round(selectedEvent.value.duration * 1000) / 1000 : 0, set: (v) => { if (selectedEvent.value) setDuration(selectedEvent.value.id, Math.max(0, Number(v) || 0)) } })

// 主图 marker：只画当前窗内、类型可见的事件（防上百 marker 标签糊屏）
const winLo = computed(() => (viewMin.value ?? winStart.value))
const winHi = computed(() => (viewMax.value ?? winStart.value + winLen.value))
const visibleMarkers = computed(() =>
  events.value
    .filter((e) => visibleTypes.value.has(e.description) && e.onset >= winLo.value - 1e-6 && e.onset <= winHi.value + 1e-6)
    .map((e) => ({ x: e.onset, label: e.description, color: e.id === selectedEventId.value ? '#11457e' : colorForLabel(e.description) })),
)

// —— 通道分页（同 ArtifactMarkPage：全通道随窗加载，分页只切「画布画哪几道」）——
const totalCh = computed(() => ts.value?.channels.length ?? 0)
const effChanPerPage = computed(() => Math.min(chanPerPage.value, Math.max(1, totalCh.value)))
const maxChanStart = computed(() => Math.max(0, totalCh.value - effChanPerPage.value))
const chanEnd = computed(() => Math.min(chanStart.value + effChanPerPage.value, totalCh.value))
const visibleChannels = computed(() => (ts.value ? ts.value.channels.slice(chanStart.value, chanEnd.value) : []))
function chanColorOf(name: string): string {
  const i = ts.value ? ts.value.channels.findIndex((c) => c.name === name) : -1
  return CHAN_PALETTE[(i < 0 ? 0 : i) % CHAN_PALETTE.length]
}
const chartData = computed<number[][]>(() => { if (!ts.value) return [[], []]; return [ts.value.times, ...visibleChannels.value.map((c) => c.values)] })
const chartSeries = computed(() => visibleChannels.value.map((c) => ({ name: c.name, color: chanColorOf(c.name) })))

const diff = computed(() => {
  const origById = new Map(originalEvents.value.map((e) => [e.id, e]))
  const curById = new Map(events.value.map((e) => [e.id, e]))
  let added = 0, removed = 0, changed = 0
  for (const e of events.value) if (!origById.has(e.id)) added++
  for (const e of originalEvents.value) if (!curById.has(e.id)) removed++
  for (const e of events.value) { const o = origById.get(e.id); if (o && (o.onset !== e.onset || o.description !== e.description || o.duration !== e.duration)) changed++ }
  return { added, removed, changed }
})
const originalCount = computed(() => originalEvents.value.length)
const dirty = computed(() => diff.value.added || diff.value.removed || diff.value.changed || groupOps.value.length > 0)
const canApply = computed(() => jobContext.value && !applying.value)
const applyLabel = computed(() => (dirty.value ? '应用梳理并继续' : '确认无改动 · 继续'))

function fmtTime(t: number): string {
  if (!Number.isFinite(t)) return ''
  const mm = Math.floor(t / 60); const ss = t - mm * 60
  return `${String(mm).padStart(2, '0')}:${ss.toFixed(2).padStart(5, '0')}`
}
function operationsSummary(): string[] {
  const out = groupOps.value.map((g) => g.op === 'delete' ? `删除类型 ${g.sources.join('+')}` : `${g.op === 'merge' ? '合并' : '改名'} ${g.sources.join('+')} → ${g.target}`)
  const d = diff.value
  if (d.added) out.push(`新增 ${d.added}`)
  if (d.removed) out.push(`删除 ${d.removed}`)
  if (d.changed) out.push(`改动 ${d.changed}`)
  return out
}

// —— 类型选择 / 可见 / 勾选 ——
function selectType(label: string) {
  selectedType.value = label
  selectedEventId.value = null
  checkedTypes.value = new Set([label])
}
function toggleVisible(label: string) { const s = new Set(visibleTypes.value); if (s.has(label)) s.delete(label); else s.add(label); visibleTypes.value = s }
function toggleCheck(label: string) { const s = new Set(checkedTypes.value); if (s.has(label)) s.delete(label); else s.add(label); checkedTypes.value = s }
function selectEvent(e: EventItem) { selectedEventId.value = e.id }

// —— 逐事件编辑 ——
function ensureVisible(label: string) { if (!visibleTypes.value.has(label)) { const s = new Set(visibleTypes.value); s.add(label); visibleTypes.value = s } }
function addEventAt(x: number, duration = 0) {
  const label = activeNewLabel.value.trim() || selectedType.value || distinctLabels.value[0] || '事件'
  const e: EventItem = { id: uid++, onset: Math.max(0, Math.round(x * 1000) / 1000), duration: Math.round(duration * 1000) / 1000, description: label }
  events.value = [...events.value, e]
  ensureVisible(label); selectedType.value = label; selectedEventId.value = e.id
}
function deleteEvent(id: number) { events.value = events.value.filter((e) => e.id !== id); if (selectedEventId.value === id) selectedEventId.value = null }
function retimeEvent(id: number, onset: number) { events.value = events.value.map((e) => e.id === id ? { ...e, onset } : e) }
function setDuration(id: number, duration: number) { events.value = events.value.map((e) => e.id === id ? { ...e, duration } : e) }
function relabelEvent(id: number, label: string) { events.value = events.value.map((e) => e.id === id ? { ...e, description: label } : e); ensureVisible(label) }

// —— 类型级批量（改 events 落 literal 清单，记 groupOps 套全部 / 溯源）——
function applyBulkRename() {
  const target = bulkTarget.value.trim()
  if (!target || !checkedTypes.value.size) return
  const sources = [...checkedTypes.value]
  events.value = events.value.map((e) => sources.includes(e.description) ? { ...e, description: target } : e)
  groupOps.value = [...groupOps.value, { op: sources.length > 1 ? 'merge' : 'rename', sources, target }]
  ensureVisible(target); selectedType.value = target; checkedTypes.value = new Set(); bulkTarget.value = ''
}
function applyBulkDelete() {
  if (!checkedTypes.value.size) return
  const sources = [...checkedTypes.value]
  events.value = events.value.filter((e) => !sources.includes(e.description))
  groupOps.value = [...groupOps.value, { op: 'delete', sources }]
  if (selectedType.value && sources.includes(selectedType.value)) selectedType.value = null
  checkedTypes.value = new Set()
}

// —— 画布交互 ——
function nearestEvent(x: number): EventItem | null {
  let best: EventItem | null = null; let bd = Infinity
  for (const e of events.value) { if (!visibleTypes.value.has(e.description)) continue; const d = Math.abs(e.onset - x); if (d < bd) { bd = d; best = e } }
  const tol = Math.max(0.05, winLen.value * 0.02)
  return best && bd <= tol ? best : null
}
function onLock(payload: { x: number }) {
  if (mode.value === 'add') { addEventAt(payload.x); return }
  cursorLockedX.value = payload.x
  const e = nearestEvent(payload.x)
  if (e) { selectedEventId.value = e.id; selectedType.value = e.description }
}
function onUnlock() { cursorLockedX.value = null }
function onSelect(region: { x0: number; x1: number } | null) {
  if (!region || mode.value !== 'add') return
  const a = Math.min(region.x0, region.x1); const b = Math.max(region.x0, region.x1)
  if (b > a) addEventAt(a, b - a)
}
function onContextX(x: number | null) { if (x == null) return; const e = nearestEvent(x); if (e) deleteEvent(e.id) }
function onCursor(payload: { x: number } | null) { if (payload) cursorX.value = payload.x }
function onZoom(view: { min: number; max: number } | null) { viewMin.value = view ? view.min : null; viewMax.value = view ? view.max : null }

// —— 窗口导航 ——
function stepWindow(dir: number) { setWinStart(winStart.value + dir * winLen.value * 0.25) }
function shiftWindow(dir: number) { setWinStart(winStart.value + dir * winLen.value) }
function setWinStart(v: number) { winStart.value = Math.round(Math.max(rangeMin.value, Math.min(rangeMax.value - winLen.value, v)) * 1000) / 1000 }
function seekTo(t: number) { setWinStart(t - winLen.value / 2) }
const winPresets = [{ v: 5, label: '5s' }, { v: 10, label: '10s' }, { v: 30, label: '30s' }, { v: 0, label: '全程' }]
function setWinLen(v: number) {
  viewMin.value = null; viewMax.value = null
  if (v <= 0) { winLen.value = Math.max(1, Math.ceil(totalDuration.value || winLen.value)); winStart.value = rangeMin.value; return }
  winLen.value = Math.max(1, v); setWinStart(winStart.value)
}
function isWinPreset(v: number): boolean {
  if (viewMin.value != null) return false
  if (v <= 0) return winLen.value >= (totalDuration.value || 0) - 0.5
  return Math.abs(winLen.value - v) < 0.5
}
// 通道分页档位
const chanPresets = [{ v: 16, label: '16' }, { v: 32, label: '32' }, { v: 64, label: '64' }, { v: CHAN_ALL, label: '全部' }]
function setChanPerPage(v: number) { chanPerPage.value = v }
function isChanPreset(v: number): boolean { return v >= CHAN_ALL ? chanPerPage.value >= totalCh.value : chanPerPage.value === v }
function chanPageBy(dir: number) { chanStart.value = Math.max(0, Math.min(maxChanStart.value, chanStart.value + dir * effChanPerPage.value)) }
watch([totalCh, chanPerPage], () => { if (chanStart.value > maxChanStart.value) chanStart.value = maxChanStart.value })

// —— 全程概览带 ——
const overviewEnv = computed<number[]>(() => {
  const o = overview.value
  if (!o || !o.times.length) return []
  const n = o.times.length; const env = new Array(n).fill(0)
  for (const ch of o.channels) for (let i = 0; i < n; i++) { const a = Math.abs(ch.values[i] || 0); if (a > env[i]) env[i] = a }
  return env
})
const ovPolyline = computed(() => {
  const o = overview.value; const env = overviewEnv.value
  if (!o || !env.length) return ''
  const t0 = o.times[0]; const t1 = o.times[o.times.length - 1]; const span = Math.max(1e-6, t1 - t0)
  const sorted = [...env].sort((a, b) => a - b)
  const norm = Math.max(1e-9, sorted[Math.floor(0.99 * (sorted.length - 1))])
  return env.map((v, i) => `${((o.times[i] - t0) / span * OV_W).toFixed(1)},${(31 - Math.min(1, v / norm) * 28).toFixed(1)}`).join(' ')
})
const ovDragStart = ref<number | null>(null)
const ovWinX = computed(() => (((ovDragStart.value ?? winStart.value) - rangeMin.value) / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)
const ovWinW = computed(() => (winLen.value / Math.max(1e-6, rangeMax.value - rangeMin.value)) * OV_W)
const ovEventMarks = computed(() => {
  const lo = rangeMin.value; const span = Math.max(1e-6, rangeMax.value - lo)
  return events.value.filter((e) => visibleTypes.value.has(e.description)).map((e) => ({ x: Math.max(0, Math.min(OV_W, ((e.onset - lo) / span) * OV_W)), color: colorForLabel(e.description) }))
})
const ovTicks = computed(() => {
  const lo = rangeMin.value, hi = rangeMax.value, span = hi - lo
  if (!(span > 0)) return [] as { pct: number; label: string }[]
  const N = 5
  return Array.from({ length: N + 1 }, (_, i) => { const t = lo + (i / N) * span; return { pct: (i / N) * 100, label: `${t.toFixed(t < 10 ? 1 : 0)}s` } })
})
function ovStartFromClientX(clientX: number, el: HTMLElement): number {
  const rect = el.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width)))
  return Math.max(rangeMin.value, Math.min(rangeMax.value - winLen.value, rangeMin.value + ratio * (rangeMax.value - rangeMin.value) - winLen.value / 2))
}
function ovPointerDown(e: PointerEvent) { (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId); ovDragStart.value = ovStartFromClientX(e.clientX, e.currentTarget as HTMLElement) }
function ovPointerMove(e: PointerEvent) { if (ovDragStart.value == null) return; ovDragStart.value = ovStartFromClientX(e.clientX, e.currentTarget as HTMLElement) }
function ovPointerUp() { if (ovDragStart.value == null) return; setWinStart(ovDragStart.value); ovDragStart.value = null }

// —— 数据加载（交互 payload + 三级取数窗口，与 ArtifactMarkPage 同款）——
function loadActiveDataset(resetGroupOps = true) {
  const d = datasets.value[activeDsIndex.value]
  const evs = (d?.events || []).map((e) => ({ id: uid++, onset: Number(e.onset) || 0, duration: Number(e.duration) || 0, description: String(e.description || '') })).filter((e) => e.description)
  events.value = evs
  originalEvents.value = evs.map((e) => ({ ...e }))
  badSegments.value = (d?.bad_segments || []).map((s) => ({ onset: Number(s.onset) || 0, duration: Number(s.duration) || 0 })).filter((s) => s.duration > 0)
  visibleTypes.value = new Set(evs.map((e) => e.description))
  checkedTypes.value = new Set()
  if (resetGroupOps) groupOps.value = []
  selectedEventId.value = null
  selectedType.value = [...new Set(evs.map((e) => e.description))].sort((a, b) => a.localeCompare(b))[0] || null
}
function snapshotCurrentDatasetEvents() {
  const index = activeDsIndex.value
  const d = datasets.value[index]
  if (!d) return
  const next = [...datasets.value]
  next[index] = {
    ...d,
    events: events.value.map((e) => ({ ...e })),
  }
  datasets.value = next
}
function eventManagerTotals() {
  const source = datasets.value.length ? datasets.value : [{ label: '数据集 1', events: events.value, bad_segments: badSegments.value }]
  const labels = new Set<string>()
  let count = 0
  source.forEach((d, index) => {
    const evs = index === activeDsIndex.value ? events.value : d.events
    count += evs.length
    evs.forEach((e) => labels.add(e.description))
  })
  return { events: count, labels: labels.size }
}
function datasetEventCount(d: DatasetMeta, index: number): number {
  return index === activeDsIndex.value ? events.value.length : d.events.length
}
function resetViewForDatasetSwitch() {
  overview.value = null
  ts.value = null
  winStart.value = 0
  viewMin.value = null
  viewMax.value = null
  cursorX.value = null
  cursorLockedX.value = null
  chanStart.value = 0
  ovDragStart.value = null
}
function selectDataset(index: number) {
  if (!Number.isInteger(index) || index < 0 || index >= datasets.value.length || index === activeDsIndex.value) return
  snapshotCurrentDatasetEvents()
  activeDsIndex.value = index
}
function onDatasetSelect(event: Event) {
  const value = Number((event.target as HTMLSelectElement | null)?.value)
  selectDataset(value)
}
async function loadInteraction(): Promise<void> {
  const res = await api.get<PipelineInteraction>(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/interaction`)
  const it = res.data
  decisionVersion.value = Number(it.decision_version || 0)
  const preview = (it.preview_json || {}) as { datasets?: Array<{ dataset_id?: string; source_dataset_id?: string; output_id?: string; data_info?: { display_name?: string; subject?: string }; events?: EventItem[]; bad_segments?: { onset: number; duration: number }[] }> }
  const ds = Array.isArray(preview.datasets) ? preview.datasets : []
  datasets.value = ds.map((d, i) => ({
    label: d.data_info?.display_name || d.data_info?.subject || d.source_dataset_id || `数据集 ${i + 1}`,
    output_id: d.output_id,
    events: Array.isArray(d.events) ? d.events : [],
    bad_segments: Array.isArray(d.bad_segments) ? d.bad_segments : [],
  }))
  if (activeDsIndex.value >= datasets.value.length) activeDsIndex.value = 0
  loadActiveDataset()
}

const TS_CACHE_MAX = 64
const tsCache = new Map<string, StudyOutputTimeseries>()
// 有界 LRU 写入（镜像 ArtifactMarkPage）：命中即提到队尾，超量从队首逐出，避免每个窗口/数据集/滤波组合
// 都缓存且永不淘汰导致内存无限增长（键含 activeDsIndex + 取数参数，长会话多数据集切换尤甚）。
function tsCacheSet(key: string, v: StudyOutputTimeseries) {
  if (tsCache.has(key)) tsCache.delete(key)
  tsCache.set(key, v)
  while (tsCache.size > TS_CACHE_MAX) {
    const k = tsCache.keys().next().value
    if (k === undefined) break
    tsCache.delete(k)
  }
}
function inputTsKey(params: Record<string, number | undefined>): string { return `evtman::${studyId}::${executionId}::${jobId}::${activeDsIndex.value}::${JSON.stringify(params)}` }
async function fetchInputNetwork(params: Record<string, number | undefined>): Promise<StudyOutputTimeseries> {
  try {
    // 二进制端点(EEGBIN01)：体积小 3–5 倍、免 JSON 序列化、已是 µV。失败回退 JSON。
    const res = await dataApi.get(inputTsUrl, { params: { ...params, format: 'binary' }, responseType: 'arraybuffer' })
    const buf = res.data as ArrayBuffer
    if (!buf || buf.byteLength < 12) throw new Error('empty binary')
    const magic = new TextDecoder().decode(new Uint8Array(buf, 0, 8))
    if (magic !== 'EEGBIN01') throw new Error('bad magic')
    return decodeBinary(buf)
  } catch {
    const res = await dataApi.get<StudyOutputTimeseries>(inputTsUrl, { params })
    const data = res.data
    if (data && data.unit !== 'uV' && Array.isArray(data.channels)) {
      for (const ch of data.channels) ch.values = ch.values.map((v) => v * 1e6)
      data.unit = 'uV'
    }
    return data
  }
}
async function fetchInputTs(params: Record<string, number | undefined>): Promise<StudyOutputTimeseries> {
  const key = inputTsKey(params)
  const mem = tsCache.get(key); if (mem) return mem
  const idb = await idbGet<StudyOutputTimeseries>(key); if (idb) { tsCacheSet(key, idb); return idb }
  const data = await fetchInputNetwork(params)
  tsCacheSet(key, data); void idbSet(key, data); return data
}
async function loadOverview() {
  const span = totalDuration.value
  if (!(span > 0)) return
  overview.value = await fetchInputTs({ tmin: 0, tmax: span, max_points: 1500, max_channels: 256, l_freq: 1, index: activeDsIndex.value })
}
let winSeq = 0 // 窗口取数竞态序号：取数前自增抢号，await 回来若被更新窗口请求超车则丢弃，防陈旧数据覆盖新窗（画面回跳）
async function loadWindow() {
  const my = ++winSeq
  viewMin.value = null; viewMax.value = null
  const params: Record<string, number | undefined> = { tmin: winStart.value, tmax: winStart.value + winLen.value, max_points: 3000, max_channels: 256, index: activeDsIndex.value }
  if (filterEnabled.value) {
    if (lFreq.value > 0) params.l_freq = lFreq.value
    if (hFreq.value > 0) params.h_freq = hFreq.value
    if (notch.value > 0) params.notch = notch.value
  }
  const data = await fetchInputTs(params)
  if (my !== winSeq) return // 已有更新的窗口请求 → 本次结果作废，不写回 state
  ts.value = data
}

async function reload() {
  if (!isLive.value) return
  loading.value = true; error.value = ''
  try {
    await loadInteraction()
    await loadWindow()
    document.title = `事件管理器 · ${events.value.length} 事件 — 念析`
    void loadOverview().catch(() => { /* 概览较重，后台加载，失败不影响主图 */ })
  } catch (err: unknown) {
    const msg = describeError(err)
    error.value = /interaction not found|interaction 不存在|找不到/i.test(msg)
      ? '该节点已处理完成或不在「等待人工」状态，无需在此梳理——可返回工作流查看结果。'
      : msg
    ts.value = null
  } finally { loading.value = false }
}

// 依赖含 overview：概览异步到达前改窗会被下面 `!overview.value` 短路丢弃，故 overview 由 null→有值时
// 补跑一次，保证那一窗波形最终能加载（竞态序号在 loadWindow 内部维护，#151）。notch 在内也一并触发重取。
watch([winStart, winLen, filterEnabled, lFreq, hFreq, notch, overview], async () => {
  if (!overview.value) return
  try { await loadWindow() } catch { /* 保留旧窗 */ }
})
watch(activeDsIndex, async () => {
  loadActiveDataset(false)
  resetViewForDatasetSwitch()
  try { await loadWindow() } catch { /* 保留旧窗 */ }
  void loadOverview().catch(() => {})
})

onMounted(reload)

// —— 快捷键 ——
const mouseHints = [
  { keys: ['点击'], label: '选择最近事件' },
  { keys: ['新增态点击'], label: '落点新增事件' },
  { keys: ['新增态拖动'], label: '新增时段事件' },
  { keys: ['右键'], label: '删除最近事件' },
  { keys: ['滚轮'], label: '缩放时间' },
  { keys: ['Ctrl', '滚轮'], label: '调幅度' },
  { keys: ['概览拖动'], label: '定位窗口' },
]
function buildHotkeys(): HotkeyDef[] {
  return [
    { key: 'n', label: '新增模式', group: 'mark', when: () => isLive.value, run: () => { mode.value = 'add' } },
    { key: 'v', label: '选择模式', group: 'mark', when: () => isLive.value, run: () => { mode.value = 'select' } },
    { key: 'Delete', label: '删选中事件', group: 'mark', when: () => selectedEventId.value != null, run: () => { if (selectedEventId.value != null) deleteEvent(selectedEventId.value) } },
    { key: 'Backspace', label: '删选中事件', group: 'mark', when: () => selectedEventId.value != null, run: () => { if (selectedEventId.value != null) deleteEvent(selectedEventId.value) } },
    { key: 'ArrowLeft', label: '左移窗 1/4', group: 'nav', when: () => isLive.value, run: () => stepWindow(-1) },
    { key: 'ArrowRight', label: '右移窗 1/4', group: 'nav', when: () => isLive.value, run: () => stepWindow(1) },
    { key: 'Shift+ArrowLeft', label: '上一整窗', group: 'nav', when: () => isLive.value, run: () => shiftWindow(-1) },
    { key: 'Shift+ArrowRight', label: '下一整窗', group: 'nav', when: () => isLive.value, run: () => shiftWindow(1) },
    { key: '1', label: '窗长 5s', group: 'zoom', when: () => isLive.value, run: () => setWinLen(5) },
    { key: '2', label: '窗长 10s', group: 'zoom', when: () => isLive.value, run: () => setWinLen(10) },
    { key: '3', label: '窗长 30s', group: 'zoom', when: () => isLive.value, run: () => setWinLen(30) },
    { key: '4', label: '窗长 全程', group: 'zoom', when: () => isLive.value, run: () => setWinLen(0) },
    { key: '0', label: '复位缩放', group: 'zoom', when: () => isLive.value, run: () => onZoom(null) },
    { key: 'Ctrl+Enter', label: '确认并续跑', group: 'general', when: () => canApply.value, run: () => submitAndReturn() },
  ]
}
const { helpOpen, helpGroups } = useObserveHotkeys(buildHotkeys, {
  escLayers: [
    () => { if (cursorLockedX.value != null) { onUnlock(); return true } return false },
    () => { if (viewMin.value != null || viewMax.value != null) { onZoom(null); return true } return false },
    () => { if (checkedTypes.value.size) { checkedTypes.value = new Set(); return true } return false },
  ],
})
</script>

<style scoped>
:deep(.page) { padding: 0; }
.ev-shell { display: grid; grid-template-columns: 210px minmax(0, 1fr) 232px; grid-template-rows: 56px 1fr; height: calc(100vh - var(--header-h)); overflow: hidden; }
.ev-toolbar { grid-column: 1 / -1; display: flex; align-items: center; gap: var(--s-3); padding: 0 var(--s-5); background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; }
.ev-title { display: flex; align-items: center; gap: 8px; }
.ev-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.ev-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.ev-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.ev-dssel { font-size: 12px; color: var(--c-text-2); display: inline-flex; align-items: center; gap: 4px; }
.ev-dssel select { font-size: 12px; padding: 2px 6px; border: 1px solid var(--c-border); border-radius: 5px; }

.ev-left { grid-column: 1; border-right: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow: hidden; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.ev-card { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 6px 7px; }
.ev-card--grow { flex: 1 1 auto; min-height: 110px; display: flex; flex-direction: column; }
.ev-card-h { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--c-text-2); margin-bottom: 5px; }
.ev-card-cnt { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--c-text-3); }
.ev-tag-soft { font-size: 10px; padding: 0 5px; border-radius: 999px; background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }
.ev-switch { margin-left: auto; font-size: 11px; color: var(--c-text-2); display: inline-flex; align-items: center; gap: 3px; cursor: pointer; }
.ev-typelist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; flex: 1; min-height: 0; overflow-y: auto; }
.ev-type { display: flex; align-items: center; gap: 6px; padding: 3px 5px; border-radius: 5px; font-size: 12px; }
.ev-type:hover { background: var(--c-bg-soft, #eef1f5); }
.ev-type.is-sel { background: rgba(63, 127, 191, .12); }
.ev-type.is-hidden .ev-type-name { color: var(--c-text-3); text-decoration: line-through; }
.ev-check { flex-shrink: 0; }
.ev-type-dot { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
.ev-type-name { flex: 1; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ev-type-cnt { font-variant-numeric: tabular-nums; color: var(--c-text-3); font-size: 11px; }
.ev-eye { border: none; background: none; color: var(--c-text-3); cursor: pointer; display: inline-flex; padding: 0; }
.ev-input { width: 100%; padding: 4px 7px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 6px; background: var(--c-surface); }
.ev-input--inline { width: 92px; }
.ev-bulk-btns { display: flex; gap: 6px; margin-top: 6px; }
.ev-btn-danger { color: var(--c-danger); }
.ev-filter { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: var(--c-text-2); }
.ev-filter input { width: 54px; padding: 2px 5px; font-size: 11px; border: 1px solid var(--c-border); border-radius: 5px; }
.ev-info { display: grid; grid-template-columns: 1fr auto; gap: 3px 8px; font-size: 12px; color: var(--c-text-3); }
.ev-info strong { color: var(--c-text); text-align: right; }

.ev-center { grid-column: 2; padding: var(--s-3); min-width: 0; min-height: 0; display: flex; flex-direction: column; gap: 8px; overflow: hidden; }
.ev-ctoolbar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 4px 6px; font-size: 12px; }
.ev-num { display: inline-flex; align-items: center; gap: 3px; color: var(--c-text-2); margin-left: 6px; }
.ev-num input[type=number] { width: 46px; padding: 2px 4px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 5px; }
.ev-presets { display: inline-flex; border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; margin-left: 2px; }
.ev-presets button { padding: 2px 8px; font-size: 11px; border: none; border-left: 1px solid var(--c-border); background: transparent; color: var(--c-text-2); cursor: pointer; }
.ev-presets button:first-child { border-left: none; }
.ev-presets button.on { background: rgba(63, 127, 191, .14); color: var(--c-primary); }
.ev-modeswitch { display: inline-flex; border: 1px solid var(--c-border); border-radius: 6px; overflow: hidden; }
.ev-modeswitch--right { margin-left: auto; }
.ev-modeswitch button { display: inline-flex; align-items: center; gap: 3px; padding: 2px 9px; font-size: 12px; border: none; background: transparent; color: var(--c-text-2); cursor: pointer; }
.ev-modeswitch button.on { background: rgba(63, 127, 191, .14); color: var(--c-primary); }
.ev-chanpager { display: inline-flex; align-items: center; gap: 3px; margin-left: 8px; color: var(--c-text-2); }
.ev-pgbtn { padding: 1px 5px; font-size: 11px; line-height: 1.2; border: 1px solid var(--c-border); border-radius: 5px; background: transparent; color: var(--c-text-2); cursor: pointer; }
.ev-pgbtn:disabled { opacity: .4; cursor: default; }
.ev-chanrange { font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; min-width: 96px; text-align: center; }
.ev-chart { flex: 1; min-height: 380px; position: relative; }
.ev-overview { border: 1px solid var(--c-border); border-radius: var(--r-sm, 7px); padding: 3px 5px; cursor: grab; touch-action: none; user-select: none; }
.ev-overview:active { cursor: grabbing; }
.ev-ov-cap { font-size: 10px; color: var(--c-text-3); margin-bottom: 1px; }
.ev-ov-cap-mark { color: var(--c-primary); }
.ev-ov-svg { width: 100%; height: 34px; display: block; }
.ev-ov-axis { position: relative; height: 12px; margin-top: 1px; }
.ev-ov-axis span { position: absolute; top: 0; font-size: 9px; color: var(--c-text-3); font-variant-numeric: tabular-nums; white-space: nowrap; }

.ev-right { grid-column: 3; border-left: 1px solid var(--c-border); background: var(--c-surface); padding: var(--s-3); overflow: hidden; min-height: 0; display: flex; flex-direction: column; gap: 8px; }
.ev-right-top { flex: 0 0 66%; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 2px; }
.ev-occlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; max-height: 280px; overflow-y: auto; }
.ev-occ { display: flex; align-items: center; gap: 7px; font-size: 12px; cursor: pointer; padding: 3px 5px; border-radius: 5px; }
.ev-occ:hover { background: var(--c-bg-soft, #eef1f5); }
.ev-occ.is-sel { background: rgba(63, 127, 191, .12); }
.ev-occ-dot { width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0; }
.ev-occ-t { font-variant-numeric: tabular-nums; flex: 1; }
.ev-occ-d { font-variant-numeric: tabular-nums; color: var(--c-text-3); }
.ev-x { border: none; background: none; color: var(--c-text-3); cursor: pointer; display: inline-flex; }
.ev-insp { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--c-text-2); }
.ev-insp label { display: flex; align-items: center; gap: 6px; }
.ev-insp input[type=number] { width: 80px; margin-left: auto; padding: 3px 5px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 5px; }
.ev-insp label > input.ev-input { margin-left: auto; width: 120px; }
.ev-seek { margin-top: 2px; }
.ev-draft .ev-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.ev-chip { font-size: 11px; padding: 2px 8px; border-radius: 6px; background: var(--c-bg-soft, #eef1f5); color: var(--c-text-2); }
.ev-chip--add { background: rgba(29, 158, 117, .14); color: #0F6E56; }
.ev-chip--del { background: rgba(226, 75, 74, .14); color: #A32D2D; }
.ev-chip--chg { background: rgba(63, 127, 191, .14); color: #185FA5; }
.ev-promote { display: flex; align-items: flex-start; gap: 6px; font-size: 11px; color: var(--c-text-2); margin-top: 8px; line-height: 1.4; cursor: pointer; }
.ev-dataset-card { flex: 1 1 34%; min-height: 0; display: flex; flex-direction: column; }
.ev-dataset-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; flex: 1; min-height: 0; overflow-y: auto; }
.ev-dataset { display: flex; align-items: center; gap: 6px; padding: 4px 5px; border-radius: 5px; font-size: 12px; cursor: pointer; }
.ev-dataset:hover { background: var(--c-bg-soft, #eef1f5); }
.ev-dataset.is-active { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.ev-dataset-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: #C2CBD8; }
.ev-dataset.is-active .ev-dataset-dot { background: var(--c-primary); }
.ev-dataset-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ev-dataset-count { color: var(--c-text-3); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ev-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.ev-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.ev-empty.is-error .ev-empty-title { color: var(--c-danger); }
.ev-applymsg { font-size: 12px; margin-top: 8px; color: var(--c-success); }
.ev-applymsg.is-error { color: var(--c-danger); }
</style>
