<template>
  <WorkbenchShell active-key="pipeline" active-top-key="analysis">
    <div class="am-shell">
      <div class="am-toolbar">
        <h1 class="page__title am-title" style="font-size: 22px; margin: 0">
          <IconLine name="activity" :size="24" /> 伪迹审核 · 标坏段 / 坏道
        </h1>
        <span v-if="isLive && ts" class="muted text-sm">
          {{ chNames.length }} 通道 · {{ totalDuration.toFixed(1) }} s · {{ ts.sfreq }} Hz
        </span>
        <span class="am-source" :class="isLive ? 'is-real' : 'is-demo'">{{ isLive ? '真实数据' : '查看模式' }}</span>
        <div style="flex: 1"></div>
        <button v-if="isLive" class="btn btn--sm" :disabled="loading" @click="load">刷新</button>
      </div>

      <!-- 左栏：通道列表（点选标坏道） -->
      <aside class="am-left" v-if="isLive && ts">
        <div class="panel__title">通道 · 点选标坏道</div>
        <ul class="am-chanlist">
          <li
            v-for="name in chNames"
            :key="name"
            class="am-chan"
            :class="{ 'is-bad': badChannels.has(name) }"
            @click="toggleChannel(name)"
          >
            <span class="am-chan-dot" :style="{ background: badChannels.has(name) ? GRAY : PRIMARY }"></span>
            <span class="am-chan-name">{{ name }}</span>
            <span v-if="badChannels.has(name)" class="am-chan-tag">坏</span>
          </li>
        </ul>
      </aside>

      <!-- 中栏：波形 -->
      <div class="am-center">
        <div v-if="!isLive" class="am-empty">
          <AppIcon name="activity" :size="40" />
          <p class="am-empty-title">在工作流的「Artifact Mark」节点处打开本页</p>
          <p class="muted text-sm">
            在流水线里双击处于「等待人工」状态的去伪迹节点，即可在真实波形上框选坏段、点选坏道，
            确认后流水线自动继续。
          </p>
        </div>
        <div v-else-if="error" class="am-empty is-error">
          <AppIcon name="warning" :size="32" />
          <p class="am-empty-title">{{ error }}</p>
          <button class="btn btn--sm" :disabled="loading" @click="load">重试</button>
        </div>
        <div v-else-if="loading && !ts" class="am-empty">
          <p class="muted">加载波形中…</p>
        </div>
        <template v-else-if="ts">
          <div class="am-hint">
            在波形上<strong>横向拖拽</strong>框选一段标为坏段（红块）；点<strong>左栏通道名</strong>把该通道标为坏道。
          </div>
          <div class="am-chart">
            <TimeCourseCanvas
              :data="chartData"
              :series="chartSeries"
              display-mode="spread"
              x-label="时间 (s)"
              y-label=""
              :y-max="null"
              :bands="segmentBands"
              :show-legend="false"
              @select="onSelect"
            />
          </div>
        </template>
      </div>

      <!-- 右栏：标记清单 + 操作 -->
      <aside class="am-right" v-if="isLive">
        <div class="panel__title">坏段 · {{ badSegments.length }} 段（{{ totalBadSeconds.toFixed(2) }} s）</div>
        <ul class="am-marklist">
          <li v-if="!badSegments.length" class="muted text-sm">拖拽波形框选标记坏段</li>
          <li v-for="(seg, i) in badSegments" :key="i">
            <span class="dot" style="background: var(--c-danger)"></span>
            {{ seg.onset.toFixed(2) }}–{{ (seg.onset + seg.duration).toFixed(2) }} s
            <button class="am-x" @click="removeSegment(i)">✕</button>
          </li>
        </ul>

        <div class="panel__title">坏道 · {{ badChannelList.length }}</div>
        <div class="am-chips">
          <span v-if="!badChannelList.length" class="muted text-sm">点左栏通道名标坏道</span>
          <span v-for="name in badChannelList" :key="name" class="am-chip">
            {{ name }}<button class="am-x" @click="toggleChannel(name)">✕</button>
          </span>
        </div>

        <div class="panel__title">坏道处理方式</div>
        <select v-model="channelAction" class="am-select">
          <option value="mark">仅标记（默认，不改数据）</option>
          <option value="interpolate">球面样条插值修复（改数据，需电极坐标）</option>
        </select>
        <p v-if="channelAction === 'interpolate'" class="muted text-sm mt-1">
          插值会用周围好电极重建坏道，需本节点前已接 Ch Loc Assign 指派坐标。
        </p>

        <div class="panel__title">操作</div>
        <button class="btn btn--block" disabled title="自动检测异常（即将支持）">
          <AppIcon name="sparkles" :size="16" /> 自动检测异常（即将支持）
        </button>
        <button class="btn btn--block btn--primary mt-2" :disabled="!canApply || applying" @click="applyDecision">
          <AppIcon name="check" :size="16" />
          {{ applying ? '提交中…' : applyLabel }}
        </button>
        <p v-if="!jobContext" class="muted text-sm mt-2">
          查看模式：在工作流的「Artifact Mark」节点（等待人工）处打开本页才能提交。
        </p>
        <p v-if="applyMsg" class="am-applymsg" :class="{ 'is-error': applyError }">{{ applyMsg }}</p>
      </aside>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconLine from '@/components/IconLine.vue'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import { fetchTimeseries } from '@/composables/observe/plotCache'
import type { PipelineInteraction, StudyOutputTimeseries } from '@/types'

// 坏段（秒）：本页自包含，不依赖 @/types（避开与并行会话共改 types/index.ts 的提交纠缠）
interface ArtifactBadSegment {
  onset: number
  duration: number
  source?: string
}

// 画布内硬编码配色（与观察页一致；受众非工程师，避免刺眼硬红）
const PRIMARY = '#3F5E8F'
const GRAY = '#79859A' // 坏道置灰
const SEGMENT_FILL = 'rgba(217, 119, 111, 0.20)' // 坏段红块（柔和 danger）
const PALETTE = ['#3F5E8F', '#2E8B9A', '#8A6FB0', '#B0794F', '#5E8F6B', '#9A6B6B']

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
const ts = ref<StudyOutputTimeseries | null>(null)

const badSegments = ref<ArtifactBadSegment[]>([])
const badChannels = ref<Set<string>>(new Set())
const channelAction = ref<'mark' | 'interpolate'>('mark')

const applying = ref(false)
const applyMsg = ref('')
const applyError = ref(false)

const chNames = computed<string[]>(() => (ts.value ? ts.value.channels.map((c) => c.name) : []))
const totalDuration = computed(() => {
  const times = ts.value?.times
  return times && times.length ? times[times.length - 1] : 0
})
const totalBadSeconds = computed(() => badSegments.value.reduce((sum, s) => sum + s.duration, 0))
const badChannelList = computed(() => [...badChannels.value])

// data=[x, ...ys]；坏道线条置灰
const chartData = computed<number[][]>(() => {
  if (!ts.value) return [[], []]
  return [ts.value.times, ...ts.value.channels.map((c) => c.values)]
})
const chartSeries = computed(() =>
  (ts.value?.channels || []).map((c, i) => ({
    name: c.name,
    color: badChannels.value.has(c.name) ? GRAY : PALETTE[i % PALETTE.length],
  })),
)
// 坏段红块复用 TimeCourseCanvas 的 bands（x 区间填充）
const segmentBands = computed(() =>
  badSegments.value.map((s) => ({ lo: s.onset, hi: s.onset + s.duration, color: SEGMENT_FILL, active: true })),
)

const canApply = computed(() => jobContext.value && !applying.value)
const applyLabel = computed(
  () => `应用（${badSegments.value.length} 段 / ${badChannelList.value.length} 道）并继续`,
)

function toggleChannel(name: string) {
  const next = new Set(badChannels.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  badChannels.value = next
}

function removeSegment(index: number) {
  badSegments.value = badSegments.value.filter((_, i) => i !== index)
}

// 框选 → 加坏段，排序后合并相邻/重叠段（贴边即合，抄 niantong mergeBadSegments 思路）
function onSelect(region: { x0: number; x1: number } | null) {
  if (!region) return
  const onset = Math.min(region.x0, region.x1)
  const stop = Math.max(region.x0, region.x1)
  if (!(stop > onset)) return
  const next = [...badSegments.value, { onset, duration: stop - onset, source: 'manual' }]
  next.sort((a, b) => a.onset - b.onset)
  const merged: ArtifactBadSegment[] = []
  for (const seg of next) {
    const prev = merged[merged.length - 1]
    if (prev && seg.onset <= prev.onset + prev.duration) {
      const newStop = Math.max(prev.onset + prev.duration, seg.onset + seg.duration)
      prev.duration = newStop - prev.onset
    } else {
      merged.push({ ...seg })
    }
  }
  badSegments.value = merged
}

function parseInitialSegments(value: unknown): ArtifactBadSegment[] {
  let arr: unknown = value
  if (typeof value === 'string' && value.trim()) {
    try {
      arr = JSON.parse(value)
    } catch {
      return []
    }
  }
  if (!Array.isArray(arr)) return []
  const out: ArtifactBadSegment[] = []
  for (const item of arr) {
    const obj = item as { onset?: unknown; duration?: unknown; source?: unknown }
    const onset = Number(obj?.onset)
    const duration = Number(obj?.duration)
    if (Number.isFinite(onset) && Number.isFinite(duration) && duration > 0) {
      out.push({ onset, duration, source: typeof obj?.source === 'string' ? obj.source : 'manual' })
    }
  }
  return out
}

function parseInitialChannels(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  if (typeof value === 'string' && value.trim()) {
    const text = value.trim()
    if (text.startsWith('[')) {
      try {
        const arr = JSON.parse(text)
        if (Array.isArray(arr)) return arr.map((v) => String(v).trim()).filter(Boolean)
      } catch {
        return []
      }
    }
    return text
      .replace(/;/g, ',')
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean)
  }
  return []
}

async function load() {
  if (!isLive.value) return
  loading.value = true
  error.value = ''
  try {
    // 取交互态：拿上游 raw 的 output_id、decision_version、草稿初始标记
    const res = await api.get<PipelineInteraction>(
      `/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/interaction`,
    )
    const interaction = res.data
    decisionVersion.value = Number(interaction.decision_version || 0)
    const preview = (interaction.preview_json || {}) as {
      datasets?: Array<{ output_id?: string | null }>
      channel_action?: string
      initial?: { bad_segments?: unknown; bad_channels?: unknown }
    }
    const datasets = Array.isArray(preview.datasets) ? preview.datasets : []
    outputId.value = String(datasets.find((d) => d && d.output_id)?.output_id || '')
    if (preview.channel_action === 'interpolate' || preview.channel_action === 'mark') {
      channelAction.value = preview.channel_action
    }
    badSegments.value = parseInitialSegments(preview.initial?.bad_segments)
    badChannels.value = new Set(parseInitialChannels(preview.initial?.bad_channels))

    if (!outputId.value) {
      error.value = '该节点的输入未保存为可视产物，无法加载波形（请在其前接一个会保存输出的步骤）。'
      return
    }
    // 全程降采样取数（v1：先看全程；窗口分段 + 二进制分块见 P3）
    // 后端约束：max_points∈[50,8000]、max_channels∈[1,256]
    const { ts: data } = await fetchTimeseries(studyId, outputId.value, {
      maxPoints: 8000,
      maxChannels: 256,
    })
    ts.value = data
    document.title = `伪迹审核 · ${data.channels.length} 通道 — 念析`
  } catch (err: unknown) {
    error.value = describeError(err)
    ts.value = null
  } finally {
    loading.value = false
  }
}

async function applyDecision() {
  if (!jobContext.value) return
  applying.value = true
  applyMsg.value = ''
  applyError.value = false
  try {
    await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/decision`, {
      bad_segments: badSegments.value,
      bad_channels: badChannelList.value,
      channel_action: channelAction.value,
      decision_version: decisionVersion.value,
    })
    // 提交即续跑（职责合一：本页既能标也能续跑）
    try {
      await api.post(`/studies/${studyId}/pipeline-executions/${executionId}/jobs/${jobId}/resume`, {})
      applyMsg.value = `已提交 ${badSegments.value.length} 段坏段 / ${badChannelList.value.length} 个坏道，流水线已继续运行。`
    } catch {
      applyMsg.value = `已提交标记；自动继续未成功，请回工作流点「继续运行」。`
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
.am-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 300px;
  grid-template-rows: 56px 1fr;
  min-height: calc(100vh - var(--header-h));
}
.am-toolbar {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 0 var(--s-5);
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  flex-wrap: wrap;
}
.am-title { display: flex; align-items: center; gap: 8px; }
.am-source { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.am-source.is-real { background: rgba(46, 107, 255, .12); color: var(--c-primary); }
.am-source.is-demo { background: var(--c-bg-soft, #eef1f5); color: var(--c-text-3); }

.am-left {
  grid-column: 1;
  border-right: 1px solid var(--c-border);
  background: var(--c-surface);
  padding: var(--s-4);
  overflow-y: auto;
}
.am-chanlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.am-chan { display: flex; align-items: center; gap: 6px; padding: 3px 6px; border-radius: 6px; font-size: 12px; cursor: pointer; }
.am-chan:hover { background: var(--c-bg-soft, #eef1f5); }
.am-chan.is-bad { color: var(--c-text-3); text-decoration: line-through; }
.am-chan-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.am-chan-name { flex: 1; }
.am-chan-tag { font-size: 10px; padding: 0 5px; border-radius: 999px; background: rgba(217, 119, 111, .18); color: var(--c-danger); }

.am-center { grid-column: 2; padding: var(--s-4); min-width: 0; display: flex; flex-direction: column; gap: var(--s-3); overflow: hidden; }
.am-hint { font-size: 12px; color: var(--c-text-2); }
.am-chart { flex: 1; min-height: 360px; position: relative; }

.am-right {
  grid-column: 3;
  border-left: 1px solid var(--c-border);
  background: var(--c-surface);
  padding: var(--s-4);
  overflow-y: auto;
}
.am-marklist { list-style: none; margin: 0 0 8px; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.am-marklist li { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.am-marklist .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.am-x { margin-left: auto; border: none; background: none; color: var(--c-text-3); cursor: pointer; }
.am-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.am-chip { display: inline-flex; align-items: center; gap: 2px; font-size: 12px; padding: 2px 6px; border-radius: 999px; background: var(--c-bg-soft, #eef1f5); }
.am-chip .am-x { margin-left: 2px; }
.am-select { width: 100%; padding: 5px 8px; font-size: 12px; border: 1px solid var(--c-border); border-radius: 6px; background: var(--c-surface); }

.am-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; text-align: center; padding: 64px 24px; color: var(--c-text-3); }
.am-empty-title { font-size: 15px; font-weight: 600; color: var(--c-text-2); margin: 4px 0 0; }
.am-empty.is-error .am-empty-title { color: var(--c-danger); }
.am-applymsg { font-size: 12px; margin-top: 8px; color: var(--c-success); }
.am-applymsg.is-error { color: var(--c-danger); }
</style>
