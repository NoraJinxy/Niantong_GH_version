<template>
  <div class="wf-page">
    <!-- 顶部信息条 -->
    <header class="wf-head">
      <div class="wf-id">
        <span class="wf-badge" :style="{ background: typeColor }">{{ typeShort }}</span>
        <div class="wf-id-text">
          <div class="wf-title">{{ displayName }}<span class="wf-region">{{ dataTypeLabel }}</span></div>
          <div class="wf-sub">
            <span class="text-mono">{{ shortId(datasetId) }}</span>
            <span v-if="isMultiOutput" class="wf-dot">·</span>
            <span v-if="isMultiOutput" class="wf-cond">{{ outputIds.length }} 个数据集对比</span>
          </div>
        </div>
      </div>
      <div class="wf-head-right">
        <span class="wf-source is-real">真实时域数据</span>
        <button class="wf-btn wf-btn--ghost" @click="load" :disabled="loading">刷新</button>
      </div>
    </header>

    <ObserveTabs active="erp" />

    <div class="wf-main">
      <!-- ============ 左栏：选择器 ============ -->
      <aside class="wf-left">
        <div class="wf-left-scroll">
          <!-- 数据集 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('dataset')">
              数据集
              <span class="wf-sec-cnt" v-if="isMultiOutput">{{ selectedSegs.size }}/{{ outputIds.length }}</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.dataset }">▾</span>
            </div>
            <div v-show="!collapsed.dataset" class="wf-sec-body">
              <template v-if="isMultiOutput">
                <label v-for="(oid, i) in outputIds" :key="oid" class="wf-li">
                  <input type="checkbox" :checked="selectedSegs.has(i)" @change="toggleSeg(i)" />
                  <span class="wf-li-dot" :style="{ background: segColor(i) }"></span>
                  <span class="wf-li-name">{{ segOptions?.[i] ?? ('数据集 ' + (i + 1)) }}</span>
                </label>
              </template>
              <div v-else class="wf-li is-static">
                <span class="wf-li-dot" :style="{ background: typeColor }"></span>
                <span class="wf-li-name text-mono">{{ shortId(datasetId) }}</span>
                <span class="wf-li-tag">{{ ts?.n_channels_total ?? '–' }}ch</span>
              </div>
            </div>
          </section>

          <!-- 条件 / 段（单产物多段时） -->
          <section v-if="!isMultiOutput && segCount > 1" class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('segment')">
              {{ segKindLabel }}
              <span class="wf-sec-cnt">{{ selectedSegs.size }}/{{ segCount }}</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.segment }">▾</span>
            </div>
            <div v-show="!collapsed.segment" class="wf-sec-body">
              <label v-for="i in segCheckboxes" :key="i" class="wf-li">
                <input type="checkbox" :checked="selectedSegs.has(i)" @change="toggleSeg(i)" />
                <span class="wf-li-dot" :style="{ background: segColor(i) }"></span>
                <span class="wf-li-name">{{ segOptions?.[i] ?? ('#' + (i + 1)) }}</span>
              </label>
              <div v-if="segCount > segCheckboxes.length" class="wf-sec-hint">
                仅列前 {{ segCheckboxes.length }} / {{ segCount }} 段（上一/下一切换主段）
                <div class="wf-seg-stepper">
                  <button class="wf-step" :disabled="loading || primarySeg <= 0" @click="stepSeg(-1)">‹</button>
                  <span class="wf-seg-idx text-mono">{{ primarySeg + 1 }} / {{ segCount }}</span>
                  <button class="wf-step" :disabled="loading || primarySeg >= segCount - 1" @click="stepSeg(1)">›</button>
                </div>
              </div>
            </div>
          </section>

          <!-- 通道 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('channel')">
              通道
              <span class="wf-sec-cnt">{{ selected.size }}/{{ allChanNames.length }}</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.channel }">▾</span>
            </div>
            <div v-show="!collapsed.channel" class="wf-sec-body">
              <div class="wf-sec-actions">
                <button v-if="selected.size < allChanNames.length" type="button" class="wf-link" @click="selectAll">全选</button>
                <button v-if="selected.size > 0" type="button" class="wf-link" @click="selectNone">清空</button>
              </div>
              <div class="wf-chanlist">
                <label v-for="(name, i) in allChanNames" :key="name" class="wf-li">
                  <input type="checkbox" :checked="selected.has(name)" @change="toggleChannel(name)" />
                  <span class="wf-li-dot" :style="{ background: channelColor(i) }"></span>
                  <span class="wf-li-name text-mono">{{ name }}</span>
                  <MiniSparkline class="wf-li-spark" :values="chanValues(name)" :color="channelColor(i)" />
                </label>
              </div>
              <p v-if="ts && ts.n_channels_total > allChanNames.length" class="wf-sec-hint">
                仅列出前 {{ allChanNames.length }} / {{ ts.n_channels_total }} 通道
              </p>
            </div>
          </section>

          <!-- 统计范围 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('range')">
              统计范围
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.range }">▾</span>
            </div>
            <div v-show="!collapsed.range" class="wf-sec-body">
              <div class="wf-row">
                <span class="wf-row-lbl">起始</span>
                <input v-model="statLoInput" class="wf-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" />
                <span class="wf-sep">~</span>
                <span class="wf-row-lbl">结束</span>
                <input v-model="statHiInput" class="wf-inp" type="number" :step="xStep" @keydown.enter="applyStatsRange" />
              </div>
              <div class="wf-row-end">
                <span class="wf-unit-tag">{{ xUnit }}</span>
                <button class="wf-link" @click="applyStatsRange">应用</button>
                <button class="wf-link" @click="resetStatsRange">跟随窗口</button>
              </div>
              <p class="wf-sec-hint">右栏统计基于此区间；也可在子图上横向拖拽框选。</p>
            </div>
          </section>

          <!-- 滤波设置（view-only） -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('filter')">
              滤波设置<span class="wf-view-tag">仅看</span>
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.filter }">▾</span>
            </div>
            <div v-show="!collapsed.filter" class="wf-sec-body">
              <label class="wf-chk"><input type="checkbox" v-model="filterOn" /> 启用滤波</label>
              <div class="wf-grid2" :class="{ 'is-off': !filterOn }">
                <div><div class="wf-grid2-lbl">高通 Hz</div><input v-model="hpInput" class="wf-inp" type="number" step="0.1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="wf-grid2-lbl">低通 Hz</div><input v-model="lpInput" class="wf-inp" type="number" step="1" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
                <div><div class="wf-grid2-lbl">陷波 Hz</div><input v-model="notchInput" class="wf-inp" type="number" step="1" placeholder="如 50" :disabled="!filterOn" @keydown.enter="applyFilter" /></div>
              </div>
              <button class="wf-apply" :disabled="!filterOn" @click="applyFilter">应用滤波</button>
              <p class="wf-sec-hint">仅用于观察滤波对结果的影响，不写入、不影响计算。</p>
            </div>
          </section>

          <!-- 绘图布局：行/列维度分配 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('layout')">
              绘图布局
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.layout }">▾</span>
            </div>
            <div v-show="!collapsed.layout" class="wf-sec-body">
              <div class="wf-grid2">
                <div>
                  <div class="wf-grid2-lbl">行</div>
                  <select class="wf-inp" :value="rowFactor" @change="onRowFactor">
                    <option v-for="o in factorOptions" :key="o.v" :value="o.v">{{ o.l }}</option>
                  </select>
                </div>
                <div>
                  <div class="wf-grid2-lbl">列</div>
                  <select class="wf-inp" :value="colFactor" @change="onColFactor">
                    <option v-for="o in factorOptions" :key="o.v" :value="o.v">{{ o.l }}</option>
                  </select>
                </div>
              </div>
              <p class="wf-sec-hint">行/列留「—」的因素将在每张子图内叠加显示。</p>
            </div>
          </section>

          <!-- 显示模块 -->
          <section class="wf-sec">
            <div class="wf-sec-head" @click="toggleSec('modules')">
              显示模块
              <span class="wf-sec-arr" :class="{ 'is-collapsed': collapsed.modules }">▾</span>
            </div>
            <div v-show="!collapsed.modules" class="wf-sec-body">
              <label class="wf-chk"><input type="checkbox" v-model="showStats" /> 统计结果（右栏）</label>
              <label class="wf-chk"><input type="checkbox" v-model="showGrid" /> 网格线</label>
              <label class="wf-chk is-disabled" title="地形图条 / sparkline 后续接入"><input type="checkbox" disabled /> 地形图（后续）</label>
            </div>
          </section>
        </div>
      </aside>

      <!-- ============ 中栏：工具条 + 绘图 + 状态条 ============ -->
      <div class="wf-center">
        <div class="wf-ctoolbar">
          <div class="wf-tg">
            <span class="wf-lbl">时间窗 ({{ xUnit }})</span>
            <button v-if="isContinuous" class="wf-step" :disabled="loading || !ts || ts.tmin <= ts.available_tmin + 1e-9" @click="pageWindow(-1)" title="上一段">«</button>
            <input v-model="winLoInput" class="wf-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <span class="wf-dash">–</span>
            <input v-model="winHiInput" class="wf-cin" type="number" :step="xStep" :disabled="loading" @keydown.enter="applyWindow" />
            <button v-if="isContinuous" class="wf-step" :disabled="loading || !ts || ts.tmax >= ts.available_tmax - 1e-9" @click="pageWindow(1)" title="下一段">»</button>
            <button class="wf-ctb" :disabled="loading" @click="applyWindow">应用</button>
            <button class="wf-ctb" :disabled="loading" @click="resetWindow">重置</button>
          </div>
          <div class="wf-tg">
            <span class="wf-lbl">Y(μV)</span>
            <select v-model.number="yScaleIdx" class="wf-csel">
              <option v-for="(y, i) in Y_SCALES" :key="i" :value="i">{{ y.label }}</option>
            </select>
          </div>
          <div class="wf-tg">
            <button class="wf-ctb" :class="{ 'is-on': displayMode === 'overlay' }" @click="displayMode = 'overlay'">叠加</button>
            <button class="wf-ctb" :class="{ 'is-on': displayMode === 'spread' }" @click="displayMode = 'spread'">排列</button>
          </div>
          <div class="wf-tg wf-tg--hint">
            <span class="wf-lbl">每张子图右上 ⬇ 可导出 PNG</span>
          </div>
        </div>

        <div class="wf-chart-wrap">
          <div v-if="loading && !ts" class="wf-state">正在读取时域数据…</div>

          <div v-else-if="error" class="wf-state wf-state--err">
            <div class="wf-err-title">无法加载该节点的时域数据</div>
            <div class="wf-err-msg">{{ error }}</div>
            <button class="wf-btn" @click="load">重试</button>
          </div>

          <template v-else-if="hasCurves">
            <div v-if="partialNote" class="wf-partial">{{ partialNote }}</div>
            <div v-if="!selected.size" class="wf-state">未选择通道 —— 在左侧「通道」里勾选要绘制的通道。</div>
            <div v-else class="wf-facet" :class="{ 'is-single': cells.length <= 1 }" :style="facetStyle">
              <section v-for="cell in cells" :key="cell.key" class="wf-cell" :style="{ borderTopColor: cellAccent(cell), borderTopWidth: '2px' }">
                <div class="wf-cell-hd">
                  <span class="wf-cell-tag" :style="{ background: cellAccent(cell) }"></span>
                  <span class="wf-cell-name">{{ cell.title || (dataType === 'evoked' ? 'ERP' : '波形') }}</span>
                  <span class="wf-cell-meta text-mono">{{ cell.series.length }}线 · {{ ts ? ts.sfreq.toFixed(0) : '–' }}Hz</span>
                  <button class="wf-cell-dl" title="导出 PNG" @click="exportCell($event, cell.title)">⬇</button>
                </div>
                <div class="wf-cell-plot">
                  <TimeCourseCanvas
                    :data="cell.data"
                    :series="cell.series"
                    :x-label="`时间 (${xUnit})`"
                    y-label="μV"
                    :y-max="yMaxValue"
                    :display-mode="displayMode"
                    :show-grid="showGrid"
                    :loading="loading"
                    :region="region"
                    :ref-lines="refLinesOn"
                    :sync-key="SYNC_KEY"
                    @cursor="onCursor"
                    @select="onSelect"
                  />
                </div>
              </section>
            </div>
          </template>

          <div v-else class="wf-state">该数据没有可绘制的通道曲线。</div>
        </div>

        <!-- 状态条 -->
        <div class="wf-sbar" v-if="ts && !error">
          <span class="wf-sbar-dot"></span>
          <span>{{ dataType || '—' }}</span><span class="wf-sbar-sep">|</span>
          <span>{{ ts.sfreq.toFixed(0) }}Hz</span><span class="wf-sbar-sep">|</span>
          <span>{{ selected.size }}/{{ ts.n_channels_total }}ch</span><span class="wf-sbar-sep">|</span>
          <span>窗 {{ fmtX(ts.tmin * xFactor) }}~{{ fmtX(ts.tmax * xFactor) }}{{ xUnit }}</span>
          <span class="wf-sbar-sep">|</span>
          <span :class="{ 'wf-sbar-filter': filterOn }">{{ filterDesc }}</span>
          <div style="flex: 1"></div>
          <span v-if="cursorReadout" class="wf-readout">
            <span class="text-mono">{{ fmtX(cursorReadout.x) }}{{ xUnit }}</span>
            <span v-for="it in cursorReadout.items.slice(0, 5)" :key="it.name" class="wf-readout-v" :style="{ color: it.color }">{{ it.name }} {{ it.uv.toFixed(2) }}</span>
            <span v-if="cursorReadout.items.length > 5" class="wf-readout-more">+{{ cursorReadout.items.length - 5 }}</span>
            <span class="wf-readout-unit">μV</span>
          </span>
        </div>
      </div>

      <!-- ============ 右栏：统计结果 ============ -->
      <aside v-if="showStats" class="wf-right">
        <div class="wf-right-head">
          <strong><span class="wf-right-dot"></span>统计结果</strong>
          <div class="wf-right-btns">
            <button class="wf-rbtn" @click="copyStats">{{ copied ? '✓ 已复制' : '📋 复制' }}</button>
            <button class="wf-rbtn" @click="exportCsv">⬇ CSV</button>
          </div>
        </div>
        <div class="wf-right-scroll">
          <div v-if="!statsRows.length" class="wf-right-empty">
            <template v-if="regionUserSet && region && hasCurves">
              统计区间（{{ fmtX(region.x0) }}–{{ fmtX(region.x1) }} {{ xUnit }}）不在当前时间窗内。<button class="wf-link" @click="resetStatsRange">跟随窗口</button>
            </template>
            <template v-else>设定统计范围或框选区间后，这里显示峰/谷/均值与潜伏期。</template>
          </div>
          <template v-else>
            <div class="wf-hl-row">
              <div class="wf-hl-card hc-peak"><div class="wf-hl-val">{{ highlightStats!.peak.toFixed(2) }}</div><div class="wf-hl-lbl">峰值 µV</div><div class="wf-hl-sub">{{ highlightStats!.peakAt }}</div></div>
              <div class="wf-hl-card hc-trough"><div class="wf-hl-val">{{ highlightStats!.trough.toFixed(2) }}</div><div class="wf-hl-lbl">谷值 µV</div><div class="wf-hl-sub">{{ highlightStats!.troughAt }}</div></div>
              <div class="wf-hl-card hc-mean"><div class="wf-hl-val">{{ highlightStats!.mean.toFixed(2) }}</div><div class="wf-hl-lbl">均值 µV</div><div class="wf-hl-sub">{{ highlightStats!.count }} 序列</div></div>
              <div class="wf-hl-card hc-lat"><div class="wf-hl-val">{{ fmtX(highlightStats!.peakLat) }}</div><div class="wf-hl-lbl">峰潜伏 {{ xUnit }}</div><div class="wf-hl-sub">{{ highlightStats!.peakAt }}</div></div>
            </div>
            <div class="wf-stats-range text-mono">区间 {{ fmtX(region!.x0) }}–{{ fmtX(region!.x1) }} {{ xUnit }}</div>
            <table class="wf-dtable">
              <thead>
                <tr><th>{{ segKindLabel }}</th><th>通道</th><th>峰值</th><th>谷值</th><th>均值</th><th>峰潜伏</th><th>谷潜伏</th></tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in statsRows" :key="i">
                  <td class="wf-dt-seg">{{ r.segName }}</td>
                  <td class="wf-dt-ch"><span class="wf-li-dot" :style="{ background: r.color }"></span>{{ r.chan }}</td>
                  <td class="wf-dt-peak">{{ r.peak.toFixed(2) }}</td>
                  <td class="wf-dt-trough">{{ r.trough.toFixed(2) }}</td>
                  <td>{{ r.mean.toFixed(2) }}</td>
                  <td class="wf-dt-lat">{{ fmtX(r.peakLat) }}</td>
                  <td class="wf-dt-lat">{{ fmtX(r.troughLat) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>
      </aside>
    </div>

    <CacheDebugOverlay />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { StudyOutputTimeseries } from '@/types'
import TimeCourseCanvas from '@/components/observe/TimeCourseCanvas.vue'
import CacheDebugOverlay from '@/components/observe/CacheDebugOverlay.vue'
import MiniSparkline from '@/components/observe/MiniSparkline.vue'
import ObserveTabs from '@/components/ObserveTabs.vue'
import { channelColor } from '@/composables/observe/channelColor'
import { fetchTimeseries } from '@/composables/observe/plotCache'

const route = useRoute()

// ---------- 常量 ----------
const MAX_CHANNELS = 64
const MAX_POINTS = 2000 // uPlot Canvas 比 SVG 可承载更多点；仍由后端按窗下采样（上限 8000）
const CONTINUOUS = ['raw', 'filtered_raw', 'ica_cleaned']
const MAX_SEG_BOXES = 40 // 段勾选框最多列这么多（epochs 可能上百，超出用翻页切主段）
const Y_SCALES = [
  { label: '自动', max: 0 },
  { label: '±5', max: 5 },
  { label: '±10', max: 10 },
  { label: '±20', max: 20 },
  { label: '±50', max: 50 },
  { label: '±100', max: 100 },
  { label: '±200', max: 200 },
]
const DATA_TYPE_LABELS: Record<string, string> = {
  raw: '连续原始 (raw)',
  filtered_raw: '滤波后 (filtered_raw)',
  ica_cleaned: 'ICA 清理 (ica_cleaned)',
  epochs: '分段 (epochs)',
  evoked: '平均 (evoked / ERP)',
}
const DEFAULT_SELECT = 8
const SYNC_KEY = 'wf-cursor' // 多子图游标联动同步键

// ---------- 查询参数 ----------
function qstr(key: string, fallback = ''): string {
  const raw = route.query[key]
  if (Array.isArray(raw)) return raw[0] ?? fallback
  return raw ?? fallback
}
// 参数统一为 studyId / study_output_id（与 PSD/TFR 一致）；兼容旧 study / dd 命名
const studyId = qstr('studyId') || qstr('study')
// study_output_id 支持逗号分隔的多产物（多数据集对比，如 ERP 各条件分别落成独立 evoked 产物）
const outputIds = (qstr('study_output_id') || qstr('dd')).split(',').map((s) => s.trim()).filter(Boolean)
const datasetId = outputIds[0] || ''
const isMultiOutput = outputIds.length > 1
const nameHint = qstr('name')
const typeHint = qstr('type')

// ---------- 因素类型（行/列/叠加）----------
type Factor = 'seg' | 'chan' | 'none'

// ---------- 状态 ----------
const tsMap = ref<Map<number, StudyOutputTimeseries>>(new Map()) // segIndex(或产物序号) -> 时域数据
const loading = ref(true)
const error = ref('')
// 多产物模式：默认全选 + 把"数据集"摆到列维度（一进来同屏看到各条件叠加）
const selectedSegs = ref<Set<number>>(new Set(isMultiOutput ? outputIds.map((_, i) => i) : [0]))
// 绘图布局：行/列因素分配；未分配（none）的因素在格内叠加
// 默认沿用已验证的观感：单产物=单格全通道叠加（行列都—）；多产物=每通道一子图、数据集格内叠加（行=通道）
const rowFactor = ref<Factor>(isMultiOutput ? 'chan' : 'none')
const colFactor = ref<Factor>('none')
const reqTmin = ref<number | null>(null) // 秒
const reqTmax = ref<number | null>(null)
// view-only 瞬时滤波（仅观察、不存储、不影响 pipeline）
const filterOn = ref(false)
const hpInput = ref<number | string>('0.5')
const lpInput = ref<number | string>('30')
const notchInput = ref<number | string>('')
const reqFilter = ref<{ lFreq: number | null; hFreq: number | null; notch: number | null }>({ lFreq: null, hFreq: null, notch: null })
const winLoInput = ref<number | string>('') // 显示单位
const winHiInput = ref<number | string>('')
const yScaleIdx = ref(0)
const showGrid = ref(true)
const showStats = ref(true)
const displayMode = ref<'overlay' | 'spread'>('overlay')
const selected = ref<Set<string>>(new Set())
const cursorReadout = ref<{ x: number; items: { name: string; color: string; uv: number }[] } | null>(null)
// 统计区间（显示单位）；默认跟随时间窗，用户拖拽/输入后固定
const region = ref<{ x0: number; x1: number } | null>(null)
const regionUserSet = ref(false)
const statLoInput = ref<number | string>('')
const statHiInput = ref<number | string>('')
const copied = ref(false)
const partialNote = ref('') // 部分产物加载失败时的非致命提示
// 左栏分区折叠
const collapsed = reactive<Record<string, boolean>>({
  dataset: false, segment: false, channel: false, range: false, filter: true, layout: false, modules: false,
})

// ---------- 主 / 段 ----------
const sortedSegs = computed(() => [...selectedSegs.value].sort((a, b) => a - b))
const primarySeg = computed(() => (sortedSegs.value.length ? sortedSegs.value[0] : 0))
const ts = computed<StudyOutputTimeseries | null>(
  () => tsMap.value.get(primarySeg.value) ?? tsMap.value.values().next().value ?? null,
)

// ---------- 类型 / 单位 ----------
const dataType = computed(() => String(ts.value?.data_type ?? typeHint ?? '').toLowerCase())
const isContinuous = computed(() => CONTINUOUS.includes(dataType.value))
// 参考线（t=0 竖线 + 0µV 基线）：相对时间的 evoked/epochs 才有意义；raw 是绝对时间不画
const refLinesOn = computed(() => dataType.value === 'evoked' || dataType.value === 'epochs')
const xUnit = computed(() => (isContinuous.value ? 's' : 'ms'))
const xFactor = computed(() => (isContinuous.value ? 1 : 1000))
const xStep = computed(() => (isContinuous.value ? 0.5 : 50))
const xPrec = computed(() => (isContinuous.value ? 3 : 0))

const dataTypeLabel = computed(() => DATA_TYPE_LABELS[dataType.value] ?? (dataType.value || '结果'))
const typeShort = computed(() => (dataType.value === 'evoked' ? 'ERP' : dataType.value.slice(0, 3).toUpperCase() || 'DD'))
const typeColor = computed(() => (dataType.value === 'evoked' ? '#2E6BFF' : isContinuous.value ? '#0891B2' : '#8B5CF6'))
const displayName = computed(() => nameHint || dataTypeLabel.value)

// 段数：单产物=该产物 n_segments；多产物=产物个数（把"数据集"映射到段维度，复用对比/网格机制）
const segCount = computed(() => (isMultiOutput ? outputIds.length : ts.value?.n_segments || 0))
const segKindLabel = computed(() => (isMultiOutput ? '数据集' : ts.value?.segment_kind === 'condition' ? '条件' : 'Epoch'))
const segOptions = computed(() =>
  isMultiOutput
    ? outputIds.map((_, i) => tsMap.value.get(i)?.segment_label || `数据集 ${i + 1}`)
    : ts.value?.segment_options ?? null,
)
const segCheckboxes = computed(() => Array.from({ length: Math.min(segCount.value, MAX_SEG_BOXES) }, (_, k) => k))

// 行/列因素下拉项（label 随段类型变化）
const factorOptions = computed<{ v: Factor; l: string }[]>(() => [
  { v: 'chan', l: '通道' },
  { v: 'seg', l: segKindLabel.value },
  { v: 'none', l: '—' },
])

// ---------- 工具 ----------
function shortId(value?: string | null) {
  if (!value) return ''
  return value.length > 10 ? value.slice(0, 8) + '…' : value
}
function round(n: number, p: number) {
  const f = Math.pow(10, p)
  return Math.round(n * f) / f
}
function fmtX(v: number) {
  return Number(v.toFixed(xPrec.value))
}
function toNum(v: number | string): number | null {
  if (v === '' || v === null || v === undefined) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
function clampInt(v: number, lo: number, hi: number) {
  return v < lo ? lo : v > hi ? hi : v
}
function segLabel(seg: number) {
  const t = tsMap.value.get(seg)
  if (t?.segment_label) return t.segment_label
  if (isMultiOutput) return `数据集 ${seg + 1}`
  return ts.value?.segment_options?.[seg] ?? `#${seg + 1}`
}
function segColor(seg: number) {
  // 按段的稳定身份（绝对序号）着色，避免勾选增删时已显示曲线/图例变色
  return channelColor(seg)
}

// ---------- 单位缩放（V → µV，逐产物判定）----------
// 二进制端点 meta.unit="uV"（已是 µV）；旧 JSON 路径无 unit → 用幅值启发式（峰值 < 0.01 视为伏特）兜底。
// 逐 t 判定而非全局，避免多产物混用不同单位时被一个尺度带偏。
function scaleFor(t: StudyOutputTimeseries): number {
  const u = (t.unit ?? '').toLowerCase()
  if (u === 'uv' || u === 'µv') return 1
  if (u === 'v') return 1e6
  let maxAbs = 0
  for (const c of t.channels) for (const v of c.values) maxAbs = Math.max(maxAbs, Math.abs(v))
  return maxAbs > 0 && maxAbs < 0.01 ? 1e6 : 1
}

const allChanNames = computed(() => (ts.value?.channels ?? []).map((c) => c.name))
const orderedSel = computed(() => allChanNames.value.filter((n) => selected.value.has(n)))

// 通道 sparkline 取主段原始值（形状由组件内 min/max 归一，不必换算 µV）
function chanValues(name: string): number[] {
  const ch = ts.value?.channels.find((c) => c.name === name)
  return ch ? ch.values : []
}
// 子图强调色 = 该格首条曲线色（按通道一图→通道色；按条件叠加→条件色）
function cellAccent(cell: Cell): string {
  return cell.series[0]?.color || 'var(--c-border)'
}
// 导出当前子图为 PNG（一期简版）：白底合成 + 顶部标题，抓子图内 uPlot canvas
function exportCell(e: MouseEvent, title: string) {
  const cellEl = (e.target as HTMLElement).closest('.wf-cell')
  const src = cellEl?.querySelector('canvas') as HTMLCanvasElement | null
  if (!src || !src.width) return
  const scale = src.clientWidth ? src.width / src.clientWidth : 2
  const headH = Math.round(20 * scale)
  const out = document.createElement('canvas')
  out.width = src.width
  out.height = src.height + headH
  const ctx = out.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, out.width, out.height)
  if (title) {
    ctx.fillStyle = '#1F2733'
    ctx.font = `${Math.round(11 * scale)}px sans-serif`
    ctx.textBaseline = 'middle'
    ctx.fillText(title, Math.round(8 * scale), headH / 2)
  }
  ctx.drawImage(src, 0, headH)
  const a = document.createElement('a')
  a.href = out.toDataURL('image/png')
  a.download = `waveform_${(title || 'plot').replace(/[^\w-]+/g, '_')}.png`
  a.click()
}

function xsFor(t: StudyOutputTimeseries) {
  return t.times.map((s) => s * xFactor.value)
}

// ---------- facet 单元（行/列因素 + 格内叠加，通用引擎）----------
interface Cell {
  key: string
  title: string
  data: number[][]
  series: { name: string; color: string }[]
}
const cells = computed<Cell[]>(() => {
  const chans = orderedSel.value
  const segs = sortedSegs.value
  if (!chans.length || !segs.length) return []

  const rf = rowFactor.value
  const cf = colFactor.value
  const segIsGrid = rf === 'seg' || cf === 'seg'
  const rowVals: (number | string | null)[] = rf === 'seg' ? segs : rf === 'chan' ? chans : [null]
  const colVals: (number | string | null)[] = cf === 'seg' ? segs : cf === 'chan' ? chans : [null]

  const out: Cell[] = []
  for (const rv of rowVals) {
    for (const cv of colVals) {
      // 解析该格被网格钉死的 seg / channel
      const pinnedSeg = rf === 'seg' ? (rv as number) : cf === 'seg' ? (cv as number) : undefined
      const pinnedChan = rf === 'chan' ? (rv as string) : cf === 'chan' ? (cv as string) : undefined
      const cellSegs: number[] = pinnedSeg != null ? [pinnedSeg] : segs
      const cellChans: string[] = pinnedChan != null ? [pinnedChan] : chans
      const multiSeg = cellSegs.length > 1
      const multiChan = cellChans.length > 1

      let xs: number[] = []
      const cols: number[][] = []
      const series: { name: string; color: string }[] = []
      for (const seg of cellSegs) {
        const t = tsMap.value.get(seg)
        if (!t) continue
        const tx = xsFor(t)
        if (!xs.length) xs = tx
        // uPlot AlignedData 要求每条 y 与 x 等长；叠加的多产物时间向量长度不一致时跳过该段，避免错位/崩溃
        if (tx.length !== xs.length) continue
        const sc = scaleFor(t)
        for (const chan of cellChans) {
          const ch = t.channels.find((c) => c.name === chan)
          if (!ch || ch.values.length !== xs.length) continue
          cols.push(ch.values.map((v) => v * sc))
          const nm = multiSeg && multiChan ? `${segLabel(seg)}·${chan}` : multiSeg ? segLabel(seg) : chan
          // 颜色编码"叠加因素"：段叠加→按段着色；否则按通道
          const color = !segIsGrid && multiSeg ? segColor(seg) : channelColor(allChanNames.value.indexOf(chan))
          series.push({ name: nm, color })
        }
      }
      const titleParts: string[] = []
      if (rf !== 'none') titleParts.push(rf === 'seg' ? segLabel(rv as number) : String(rv))
      if (cf !== 'none') titleParts.push(cf === 'seg' ? segLabel(cv as number) : String(cv))
      out.push({ key: `r:${String(rv)}|c:${String(cv)}`, title: titleParts.join(' · '), data: [xs, ...cols], series })
    }
  }
  return out
})

// facet 网格列模板：行列都指派→严格矩阵（列数=列因素值个数）；只指派一个或都不指派→自适应铺排（画廊式换行）
const facetStyle = computed(() => {
  const rf = rowFactor.value
  const cf = colFactor.value
  if (rf !== 'none' && cf !== 'none') {
    const n = (cf === 'seg' ? sortedSegs.value.length : orderedSel.value.length) || 1
    return { gridTemplateColumns: `repeat(${n}, minmax(220px, 1fr))` }
  }
  return { gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }
})

const hasCurves = computed(() => allChanNames.value.length > 0 && (ts.value?.times.length || 0) > 1)

const autoYMax = computed(() => {
  let m = 0
  for (const cell of cells.value) for (let i = 1; i < cell.data.length; i++) for (const v of cell.data[i]) m = Math.max(m, Math.abs(v))
  return Math.max(2, Math.ceil((m * 1.2) / 2) * 2)
})
const yMaxValue = computed(() => Y_SCALES[yScaleIdx.value].max || autoYMax.value)

// ---------- 区间统计（逐 段×通道，与布局无关）----------
interface StatRow {
  seg: number
  segName: string
  chan: string
  color: string
  peak: number
  trough: number
  mean: number
  peakLat: number
  troughLat: number
}
const statsRows = computed<StatRow[]>(() => {
  const r = region.value
  const chans = orderedSel.value
  const segs = sortedSegs.value
  if (!r || !chans.length) return []
  const out: StatRow[] = []
  for (const seg of segs) {
    const t = tsMap.value.get(seg)
    if (!t) continue
    const sc = scaleFor(t)
    const xs = xsFor(t)
    const idxs: number[] = []
    for (let i = 0; i < xs.length; i++) if (xs[i] >= r.x0 && xs[i] <= r.x1) idxs.push(i)
    if (!idxs.length) continue
    for (const chan of chans) {
      const ch = t.channels.find((c) => c.name === chan)
      if (!ch) continue
      let sum = 0
      let peak = -Infinity
      let trough = Infinity
      let peakLat = xs[idxs[0]]
      let troughLat = xs[idxs[0]]
      for (const i of idxs) {
        const v = (ch.values[i] ?? 0) * sc
        sum += v
        if (v > peak) { peak = v; peakLat = xs[i] }
        if (v < trough) { trough = v; troughLat = xs[i] }
      }
      out.push({
        seg,
        segName: segLabel(seg),
        chan,
        color: channelColor(allChanNames.value.indexOf(chan)),
        peak,
        trough,
        mean: sum / idxs.length,
        peakLat,
        troughLat,
      })
    }
  }
  return out.slice(0, 500)
})

const highlightStats = computed(() => {
  const rows = statsRows.value
  if (!rows.length) return null
  let pk = rows[0]
  let tr = rows[0]
  let sum = 0
  for (const r of rows) {
    if (r.peak > pk.peak) pk = r
    if (r.trough < tr.trough) tr = r
    sum += r.mean
  }
  return {
    peak: pk.peak,
    peakAt: `${pk.chan}·${pk.segName}`,
    peakLat: pk.peakLat,
    trough: tr.trough,
    troughAt: `${tr.chan}·${tr.segName}`,
    mean: sum / rows.length,
    count: rows.length,
  }
})

const filterDesc = computed(() => {
  if (!filterOn.value) return '滤波 关'
  const f = reqFilter.value
  const hp = f.lFreq != null ? f.lFreq : '—'
  const lp = f.hFreq != null ? f.hFreq : '—'
  return `滤波 ${hp}~${lp}Hz${f.notch ? ` ⏚${f.notch}` : ''}`
})

// ---------- 统计导出 ----------
function statsMatrix(): string[][] {
  const head = [segKindLabel.value, '通道', '峰值μV', '谷值μV', '均值μV', `峰潜伏${xUnit.value}`, `谷潜伏${xUnit.value}`]
  const body = statsRows.value.map((r) => [
    r.segName, r.chan, r.peak.toFixed(2), r.trough.toFixed(2), r.mean.toFixed(2), String(fmtX(r.peakLat)), String(fmtX(r.troughLat)),
  ])
  return [head, ...body]
}
function copyStats() {
  const text = statsMatrix().map((r) => r.join('\t')).join('\n')
  navigator.clipboard?.writeText(text).then(() => {
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1200)
  }).catch(() => {})
}
function exportCsv() {
  const csv = '﻿' + statsMatrix().map((r) => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'eeg_stats.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// ---------- 拉取时域数据 ----------
let loadSeq = 0 // 请求令牌：丢弃被后续请求取代的乱序回包
async function load() {
  if (!studyId || !outputIds.length) {
    error.value = '缺少参数：需要 studyId 和 study_output_id（结果 ID）。'
    loading.value = false
    return
  }
  const myId = ++loadSeq
  loading.value = true
  error.value = ''
  try {
    const segs = sortedSegs.value.length ? sortedSegs.value : [0]
    // allSettled：单个段/产物失败（如某结果文件被清理）不连累其它已成功的，部分可用也能看
    const settled = await Promise.allSettled(
      segs.map(async (seg) => {
        if (isMultiOutput) {
          // 多产物对比：键=产物序号(0..N-1)，把"数据集"摆到段维度复用对比/网格机制
          const oid = outputIds[seg] ?? outputIds[0]
          const { ts: data } = await fetchTimeseries(studyId, oid, {
            tmin: reqTmin.value, tmax: reqTmax.value, maxPoints: MAX_POINTS, maxChannels: MAX_CHANNELS, ...reqFilter.value,
          })
          return [seg, data] as const
        }
        const { ts: data } = await fetchTimeseries(studyId, datasetId, {
          index: seg, tmin: reqTmin.value, tmax: reqTmax.value, maxPoints: MAX_POINTS, maxChannels: MAX_CHANNELS, ...reqFilter.value,
        })
        return [data.segment_index ?? seg, data] as const
      }),
    )
    if (myId !== loadSeq) return // 已被更新的请求取代，丢弃这次结果
    const ok = settled.filter(
      (s): s is PromiseFulfilledResult<readonly [number, StudyOutputTimeseries]> => s.status === 'fulfilled',
    )
    if (!ok.length) {
      const firstErr = settled.find((s) => s.status === 'rejected') as PromiseRejectedResult | undefined
      tsMap.value = new Map()
      error.value = describeError(firstErr?.reason)
      return
    }
    const m = new Map<number, StudyOutputTimeseries>()
    for (const s of ok) m.set(s.value[0], s.value[1])
    tsMap.value = m
    const failed = settled.length - ok.length
    partialNote.value = failed > 0 ? `部分结果未能加载（${failed} 个），仅显示可用的 ${ok.length} 个。` : ''
    const prim = m.get(primarySeg.value) ?? ok[0].value[1]
    winLoInput.value = round(prim.tmin * xFactor.value, xPrec.value)
    winHiInput.value = round(prim.tmax * xFactor.value, xPrec.value)
    // 统计区间默认跟随时间窗（用户未手动设定时）；多产物取各窗口的并集，避免非主段被裁掉
    if (!regionUserSet.value) {
      let lo = Infinity
      let hi = -Infinity
      for (const t of m.values()) {
        lo = Math.min(lo, t.tmin * xFactor.value)
        hi = Math.max(hi, t.tmax * xFactor.value)
      }
      if (Number.isFinite(lo) && Number.isFinite(hi)) {
        region.value = { x0: lo, x1: hi }
        statLoInput.value = round(lo, xPrec.value)
        statHiInput.value = round(hi, xPrec.value)
      }
    }
    document.title = `时域 · ${displayName.value} — 念析`
  } catch (err: unknown) {
    if (myId !== loadSeq) return
    tsMap.value = new Map()
    error.value = describeError(err)
  } finally {
    if (myId === loadSeq) loading.value = false
  }
}

function describeError(err: unknown): string {
  const e = err as { response?: { status?: number; data?: { detail?: { message?: string } | string } } }
  const status = e?.response?.status
  const detail = e?.response?.data?.detail
  const serverMsg = typeof detail === 'string' ? detail : detail?.message
  if (status === 404) return '该结果的文件不存在或已被清理（可能是未保留的中间结果）。'
  if (status === 409) return '文件校验和与记录不一致，数据可能已损坏。'
  if (status === 400) return serverMsg || '该数据类型不支持时域曲线。'
  if (status === 422) return serverMsg || '该结果缺少可解析的存储路径或为空。'
  return serverMsg || '读取时域数据失败，请稍后重试。'
}

// ---------- 控制动作（改状态，由 watch 触发 load）----------
function applyWindow() {
  const lo = toNum(winLoInput.value)
  const hi = toNum(winHiInput.value)
  reqTmin.value = lo === null ? null : lo / xFactor.value
  reqTmax.value = hi === null ? null : hi / xFactor.value
}
function resetWindow() {
  reqTmin.value = null
  reqTmax.value = null
}
function pageWindow(dir: number) {
  const t = ts.value
  if (!t) return
  const len = t.tmax - t.tmin
  if (len <= 0) return
  let lo = t.tmin + dir * len
  let hi = t.tmax + dir * len
  if (lo < t.available_tmin) {
    lo = t.available_tmin
    hi = lo + len
  }
  if (hi > t.available_tmax) {
    hi = t.available_tmax
    lo = Math.max(t.available_tmin, hi - len)
  }
  reqTmin.value = lo
  reqTmax.value = hi
}
function setSeg(i: number) {
  selectedSegs.value = new Set([i])
  reqTmin.value = null
  reqTmax.value = null
}
function stepSeg(d: number) {
  const next = clampInt(primarySeg.value + d, 0, segCount.value - 1)
  if (next !== primarySeg.value) setSeg(next)
}
function toggleSeg(i: number) {
  const s = new Set(selectedSegs.value)
  if (s.has(i)) s.delete(i)
  else s.add(i)
  if (!s.size) s.add(i) // 至少留一个
  selectedSegs.value = s
}
function applyFilter() {
  reqFilter.value = filterOn.value
    ? { lFreq: toNum(hpInput.value), hFreq: toNum(lpInput.value), notch: toNum(notchInput.value) }
    : { lFreq: null, hFreq: null, notch: null }
}
watch(filterOn, applyFilter) // 开关切换立即生效；改输入框走「应用滤波」/回车

// 行/列因素互斥（同一因素不能同时占行与列）
function onRowFactor(e: Event) {
  const v = (e.target as HTMLSelectElement).value as Factor
  rowFactor.value = v
  if (v !== 'none' && colFactor.value === v) colFactor.value = 'none'
  maybeAddSecondSeg()
}
function onColFactor(e: Event) {
  const v = (e.target as HTMLSelectElement).value as Factor
  colFactor.value = v
  if (v !== 'none' && rowFactor.value === v) rowFactor.value = 'none'
  maybeAddSecondSeg()
}
// 把段指派到行/列且只选了 1 段时，自动补第 2 段方便直接看对比
function maybeAddSecondSeg() {
  const segUsed = rowFactor.value === 'seg' || colFactor.value === 'seg'
  if (segUsed && selectedSegs.value.size < 2 && segCount.value >= 2) {
    selectedSegs.value = new Set([primarySeg.value, primarySeg.value === 0 ? 1 : 0])
  }
}

// ---------- 统计范围 ----------
function fullWindow(): { x0: number; x1: number } | null {
  const t = ts.value
  if (!t) return null
  return { x0: t.tmin * xFactor.value, x1: t.tmax * xFactor.value }
}
function applyStatsRange() {
  const lo = toNum(statLoInput.value)
  const hi = toNum(statHiInput.value)
  if (lo === null || hi === null) return
  region.value = { x0: Math.min(lo, hi), x1: Math.max(lo, hi) }
  regionUserSet.value = true
}
function resetStatsRange() {
  regionUserSet.value = false
  const fw = fullWindow()
  if (fw) {
    region.value = fw
    statLoInput.value = round(fw.x0, xPrec.value)
    statHiInput.value = round(fw.x1, xPrec.value)
  }
}

// 段集合 / 窗口 / 滤波变化 → 重新取数（通道选择、行列分配是客户端过滤，不触发）
watch([() => sortedSegs.value.join(','), reqTmin, reqTmax, () => JSON.stringify(reqFilter.value)], () => {
  void load()
})

// ---------- 通道选择 ----------
function toggleChannel(name: string) {
  const s = new Set(selected.value)
  if (s.has(name)) s.delete(name)
  else s.add(name)
  selected.value = s
}
function selectAll() {
  selected.value = new Set(allChanNames.value)
}
function selectNone() {
  selected.value = new Set()
}

watch(
  () => allChanNames.value.join(''),
  (key) => {
    if (!key) return
    if (selected.value.size === 0) {
      const init = allChanNames.value.slice(0, Math.min(allChanNames.value.length, DEFAULT_SELECT))
      selected.value = new Set(init)
    }
  },
  { immediate: true },
)

// ---------- 游标 / 选区（来自 TimeCourseCanvas）----------
function onCursor(payload: { x: number; items: { name: string; color: string; uv: number }[] } | null) {
  cursorReadout.value = payload
}
function onSelect(r: { x0: number; x1: number } | null) {
  if (!r) return
  region.value = r
  regionUserSet.value = true
  statLoInput.value = round(r.x0, xPrec.value)
  statHiInput.value = round(r.x1, xPrec.value)
}

// ---------- 左栏分区折叠 ----------
function toggleSec(key: string) {
  collapsed[key] = !collapsed[key]
}

// ---------- Ctrl+A 全选通道 ----------
function onKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
    const tag = document.activeElement?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    e.preventDefault()
    if (hasCurves.value) selectAll()
  }
}

onMounted(() => {
  document.title = '时域 — 念析'
  window.addEventListener('keydown', onKeydown)
  void load()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.wf-page { display: flex; flex-direction: column; height: 100vh; background: var(--c-bg-soft); color: var(--c-text); font-family: var(--ff-sans); }
.text-mono { font-family: var(--ff-mono); }
.wf-page :deep(.obs-tabs) { flex-shrink: 0; }
.wf-tg--hint { border-right: none; opacity: .85; }

/* ===== 顶部信息条 ===== */
.wf-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 16px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-shrink: 0; }
.wf-id { display: flex; align-items: center; gap: 12px; min-width: 0; }
.wf-badge { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: var(--r); color: #fff; font-weight: 700; font-size: 12px; flex-shrink: 0; }
.wf-title { font-size: 14px; font-weight: 600; }
.wf-region { margin-left: 8px; font-size: 12px; font-weight: 400; color: var(--c-text-3); }
.wf-sub { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--c-text-2); margin-top: 2px; flex-wrap: wrap; }
.wf-dot { color: var(--c-text-3); }
.wf-cond { display: inline-flex; align-items: center; gap: 4px; background: var(--c-bg-tint); padding: 1px 7px; border-radius: var(--r-pill); }
.wf-head-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.wf-source { font-size: 11px; padding: 2px 8px; border-radius: var(--r-pill); }
.wf-source.is-real { color: var(--c-success); background: var(--c-success-soft); border: 1px solid rgba(16, 185, 129, .3); }
.wf-btn { height: 28px; padding: 0 12px; border-radius: var(--r-sm); border: 1px solid var(--c-border-2); background: var(--c-surface); color: var(--c-text); font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; }
.wf-btn:hover { background: var(--c-bg-tint); }
.wf-btn:disabled { opacity: .5; cursor: default; }
.wf-btn--ghost { color: var(--c-text-2); }

/* ===== 三栏主体 ===== */
.wf-main { flex: 1; display: flex; min-height: 0; }

/* ===== 左栏：选择器 ===== */
.wf-left { width: 232px; min-width: 232px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--c-surface); border-right: 1px solid var(--c-border); overflow: hidden; }
.wf-left-scroll { flex: 1; overflow-y: auto; }
.wf-sec { border-left: 3px solid transparent; padding: 7px 11px 8px 13px; }
.wf-sec:nth-child(7n+1) { border-left-color: #3F5E8F; }
.wf-sec:nth-child(7n+2) { border-left-color: #7B5EA8; }
.wf-sec:nth-child(7n+3) { border-left-color: #4F8A6B; }
.wf-sec:nth-child(7n+4) { border-left-color: #B07F33; }
.wf-sec:nth-child(7n+5) { border-left-color: #B0544C; }
.wf-sec:nth-child(7n+6) { border-left-color: #5E7BA8; }
.wf-sec:nth-child(7n+7) { border-left-color: #2F8A86; }
.wf-sec + .wf-sec { border-top: 1px solid var(--c-border); }
.wf-sec-head { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: var(--c-text-3); margin-bottom: 5px; display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
.wf-sec-cnt { font-weight: 400; font-size: 9px; background: var(--c-bg-tint); padding: 1px 5px; border-radius: 8px; color: var(--c-text-2); }
.wf-sec-arr { margin-left: auto; font-size: 8px; transition: transform .2s; }
.wf-sec-arr.is-collapsed { transform: rotate(-90deg); }
.wf-sec-body { display: flex; flex-direction: column; gap: 2px; }
.wf-sec-actions { display: flex; gap: 8px; margin-bottom: 2px; }
.wf-sec-hint { margin: 4px 0 0; font-size: 9.5px; color: var(--c-text-3); line-height: 1.4; }
.wf-link { background: none; border: none; color: var(--c-primary); cursor: pointer; font-size: 11px; padding: 0; }
.wf-link:hover { text-decoration: underline; }

.wf-li { display: flex; align-items: center; gap: 6px; padding: 2px 5px; border-radius: 3px; font-size: 11px; color: var(--c-text-2); cursor: pointer; user-select: none; }
.wf-li:hover { background: var(--c-bg-tint); }
.wf-li.is-static { cursor: default; }
.wf-li input[type="checkbox"] { accent-color: var(--c-primary); width: 12px; height: 12px; margin: 0; flex-shrink: 0; }
.wf-li-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.wf-li-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-li-tag { margin-left: auto; font-size: 8px; color: var(--c-text-3); background: var(--c-bg-tint); padding: 0 4px; border-radius: 3px; }
.wf-chanlist { max-height: 200px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
.wf-li-spark { margin-left: auto; flex-shrink: 0; }
.wf-seg-stepper { display: flex; align-items: center; gap: 4px; margin-top: 4px; }

.wf-row { display: flex; align-items: center; gap: 4px; }
.wf-row-lbl { font-size: 9px; color: var(--c-text-3); flex-shrink: 0; }
.wf-row-end { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.wf-unit-tag { font-size: 9px; color: var(--c-text-3); }
.wf-sep { color: var(--c-text-3); font-size: 10px; }
.wf-inp { width: 100%; min-width: 0; height: 24px; padding: 0 6px; background: var(--c-bg-soft); border: 1px solid var(--c-border-2); border-radius: 3px; color: var(--c-text); font-size: 11px; outline: none; font-family: var(--ff-mono); }
.wf-inp:focus { border-color: var(--c-primary); background: var(--c-surface); }
.wf-inp:disabled { opacity: .5; }
.wf-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 4px; }
.wf-grid2.is-off { opacity: .55; }
.wf-grid2-lbl { font-size: 9px; color: var(--c-text-3); margin-bottom: 1px; }
.wf-chk { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--c-text-2); cursor: pointer; padding: 2px 0; }
.wf-chk input { accent-color: var(--c-primary); width: 12px; height: 12px; }
.wf-chk.is-disabled { color: var(--c-text-3); cursor: default; }
.wf-apply { width: 100%; padding: 5px 0; margin-top: 5px; border: none; border-radius: 3px; background: var(--c-primary); color: #fff; font-size: 11px; font-weight: 600; cursor: pointer; font-family: inherit; }
.wf-apply:hover:not(:disabled) { opacity: .9; }
.wf-apply:disabled { opacity: .45; cursor: default; }
.wf-view-tag { font-size: 8px; color: var(--c-warning); background: var(--c-warning-soft); border-radius: 6px; padding: 0 4px; margin-left: 4px; font-weight: 600; letter-spacing: 0; text-transform: none; }

/* ===== 中栏 ===== */
.wf-center { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.wf-ctoolbar { display: flex; align-items: center; gap: 4px; padding: 6px 12px; background: var(--c-surface); border-bottom: 1px solid var(--c-border); flex-wrap: wrap; flex-shrink: 0; }
.wf-tg { display: flex; align-items: center; gap: 4px; padding: 0 8px; border-right: 1px solid var(--c-border); }
.wf-tg:last-child { border-right: none; }
.wf-tg:first-child { padding-left: 0; }
.wf-lbl { font-size: 10px; color: var(--c-text-3); }
.wf-cin { width: 58px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; font-family: var(--ff-mono); text-align: center; }
.wf-cin:focus { border-color: var(--c-primary); outline: none; }
.wf-csel { height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text); font-size: 12px; padding: 0 6px; }
.wf-dash { color: var(--c-text-3); }
.wf-step { width: 24px; height: 26px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); cursor: pointer; font-size: 13px; padding: 0; }
.wf-step:hover:not(:disabled) { background: var(--c-bg-tint); color: var(--c-text); }
.wf-step:disabled { opacity: .4; cursor: default; }
.wf-seg-idx { font-size: 11px; color: var(--c-text-2); min-width: 48px; text-align: center; }
.wf-ctb { height: 26px; padding: 0 9px; border: 1px solid var(--c-border-2); border-radius: var(--r-sm); background: var(--c-surface); color: var(--c-text-2); font-size: 11px; cursor: pointer; }
.wf-ctb:hover:not(:disabled) { background: var(--c-bg-tint); color: var(--c-text); }
.wf-ctb.is-on { background: var(--c-primary-soft); border-color: var(--c-primary); color: var(--c-primary); font-weight: 600; }
.wf-ctb.is-disabled, .wf-ctb:disabled { opacity: .5; cursor: default; }

.wf-chart-wrap { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 10px 12px; background: var(--c-bg-soft); }
.wf-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--c-text-2); font-size: 13px; text-align: center; }
.wf-state--err { color: var(--c-danger); }
.wf-partial { margin-bottom: 8px; padding: 5px 10px; font-size: 11px; color: var(--c-warning); background: var(--c-warning-soft); border: 1px solid rgba(176, 127, 51, .3); border-radius: var(--r-sm); flex-shrink: 0; }
.wf-err-title { font-size: 15px; font-weight: 600; }
.wf-err-msg { color: var(--c-text-2); font-size: 13px; max-width: 480px; }

.wf-facet { flex: 1; min-height: 0; display: grid; grid-auto-rows: 320px; gap: 10px; overflow: auto; align-content: start; }
.wf-facet.is-single { display: flex; }
.wf-cell { display: flex; flex-direction: column; min-height: 0; border: 1px solid var(--c-border); border-radius: var(--r-sm); background: var(--c-surface); overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.wf-facet.is-single .wf-cell { flex: 1; }
.wf-cell-hd { display: flex; align-items: center; gap: 6px; padding: 3px 6px 3px 8px; border-bottom: 1px solid var(--c-border); background: var(--c-bg-soft); }
.wf-cell-tag { width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0; }
.wf-cell-name { font-size: 11px; font-weight: 600; color: var(--c-text-2); font-family: var(--ff-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-cell-meta { margin-left: auto; font-size: 9px; color: var(--c-text-3); flex-shrink: 0; }
.wf-cell-dl { border: none; background: none; color: var(--c-text-3); cursor: pointer; font-size: 12px; padding: 0 2px; flex-shrink: 0; line-height: 1; }
.wf-cell-dl:hover { color: var(--c-primary); }
.wf-cell-plot { flex: 1; min-height: 0; padding: 6px 8px; }

/* ===== 状态条 ===== */
.wf-sbar { height: 24px; display: flex; align-items: center; gap: 8px; padding: 0 12px; background: var(--c-surface); border-top: 1px solid var(--c-border); font-size: 10.5px; color: var(--c-text-3); flex-shrink: 0; overflow: hidden; }
.wf-sbar-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--c-success); flex-shrink: 0; }
.wf-sbar-sep { color: var(--c-border-2); }
.wf-sbar-filter { color: var(--c-warning); font-weight: 600; }
.wf-readout { display: inline-flex; align-items: center; gap: 7px; flex-wrap: nowrap; overflow: hidden; }
.wf-readout-v { font-family: var(--ff-mono); font-weight: 600; }
.wf-readout-more { font-family: var(--ff-mono); }
.wf-readout-unit { color: var(--c-text-3); }

/* ===== 右栏：统计 ===== */
.wf-right { width: 296px; min-width: 296px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--c-surface); border-left: 1px solid var(--c-border); overflow: hidden; }
.wf-right-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--c-border); background: var(--c-bg-soft); flex-shrink: 0; }
.wf-right-head strong { font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.wf-right-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c-primary); }
.wf-right-btns { display: flex; gap: 4px; }
.wf-rbtn { padding: 3px 8px; border: 1px solid var(--c-border-2); border-radius: 3px; background: var(--c-surface); font-size: 10px; color: var(--c-text-2); cursor: pointer; }
.wf-rbtn:hover { border-color: var(--c-primary); color: var(--c-primary); }
.wf-right-scroll { flex: 1; overflow-y: auto; padding: 8px; }
.wf-right-empty { color: var(--c-text-3); font-size: 11px; line-height: 1.6; padding: 12px 4px; text-align: center; }

.wf-hl-row { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 8px; }
.wf-hl-card { background: var(--c-bg-soft); border: 1px solid var(--c-border); border-radius: var(--r-sm); padding: 7px 8px; text-align: center; position: relative; overflow: hidden; }
.wf-hl-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; }
.wf-hl-card.hc-peak::before { background: #3F5E8F; }
.wf-hl-card.hc-trough::before { background: #B0544C; }
.wf-hl-card.hc-mean::before { background: #4F8A6B; }
.wf-hl-card.hc-lat::before { background: #B07F33; }
.wf-hl-val { font-size: 17px; font-weight: 800; font-family: var(--ff-mono); line-height: 1.1; }
.wf-hl-card.hc-peak .wf-hl-val { color: #3F5E8F; }
.wf-hl-card.hc-trough .wf-hl-val { color: #B0544C; }
.wf-hl-card.hc-mean .wf-hl-val { color: #4F8A6B; }
.wf-hl-card.hc-lat .wf-hl-val { color: #B07F33; }
.wf-hl-lbl { font-size: 8px; color: var(--c-text-3); text-transform: uppercase; letter-spacing: 0.4px; margin-top: 3px; }
.wf-hl-sub { font-size: 8.5px; color: var(--c-text-3); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wf-stats-range { font-size: 10px; color: var(--c-text-3); margin: 0 2px 4px; }

.wf-dtable { width: 100%; border-collapse: collapse; font-size: 10px; }
.wf-dtable th { position: sticky; top: 0; background: var(--c-bg-soft); color: var(--c-text-3); font-weight: 600; text-align: right; padding: 4px 5px; border-bottom: 1px solid var(--c-border); font-size: 8.5px; text-transform: uppercase; letter-spacing: 0.3px; }
.wf-dtable th:first-child, .wf-dtable th:nth-child(2) { text-align: left; }
.wf-dtable td { padding: 3px 5px; text-align: right; border-bottom: 1px solid var(--c-border); color: var(--c-text-2); font-family: var(--ff-mono); }
.wf-dtable td:first-child, .wf-dtable td:nth-child(2) { text-align: left; }
.wf-dtable tr:hover td { background: var(--c-bg-tint); }
.wf-dt-seg { color: var(--c-text-2); }
.wf-dt-ch { display: flex; align-items: center; gap: 4px; }
.wf-dt-peak { color: #3F5E8F; font-weight: 600; }
.wf-dt-trough { color: #B0544C; font-weight: 600; }
.wf-dt-lat { color: var(--c-text-3); }
</style>
