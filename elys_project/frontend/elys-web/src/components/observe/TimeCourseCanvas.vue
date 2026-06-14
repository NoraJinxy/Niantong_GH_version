<template>
  <div ref="hostRef" class="tcc-host">
    <div v-if="loading" class="tcc-loading">加载中…</div>
  </div>
</template>

<script setup lang="ts">
// 时域 uPlot 宿主：只负责「拿数据画线 + 冒泡游标」，不持业务状态。
// 决策见 日志/10_观察作图与缓存架构260614/06 §4。1D 曲线统一走 uPlot（P-1）。
import { onMounted, onUnmounted, ref, shallowRef, watch, nextTick } from 'vue'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface SeriesCfg { name: string; color: string }
interface CursorItem { name: string; color: string; uv: number }

const props = withDefaults(
  defineProps<{
    /** uPlot AlignedData：[ x[], ...每条可见通道的 y[] ]。x 已是显示单位、y 已是 µV（父层换算好）。 */
    data: (number[])[]
    series: SeriesCfg[]
    xLabel?: string
    yLabel?: string
    /** null=自动；非 null=对称 ±yMax。 */
    yMax?: number | null
    showGrid?: boolean
    loading?: boolean
  }>(),
  { xLabel: '时间', yLabel: 'μV', yMax: null, showGrid: true, loading: false },
)

const emit = defineEmits<{
  (e: 'cursor', payload: { x: number; items: CursorItem[] } | null): void
}>()

const hostRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<uPlot | null>(null)
let ro: ResizeObserver | null = null

// 画布内是 Canvas 绘制，CSS 变量不生效，必须用具体色值（对齐 elys token）。
const AXIS = '#79859A' // --c-text-3
const GRID = '#E4E9F1' // --c-border

function buildOpts(w: number, h: number): uPlot.Options {
  const grid = props.showGrid
  const opts: uPlot.Options = {
    width: w,
    height: h,
    legend: { show: false },
    cursor: { drag: { x: true, y: false }, focus: { prox: 16 } },
    scales: {
      x: { time: false },
      y: props.yMax != null ? { range: [-props.yMax, props.yMax] } : {},
    },
    axes: [
      { label: props.xLabel, stroke: AXIS, grid: { show: grid, stroke: GRID }, ticks: { stroke: GRID }, font: '11px var(--ff-mono, monospace)' },
      { label: props.yLabel, stroke: AXIS, grid: { show: grid, stroke: GRID }, ticks: { stroke: GRID }, font: '11px var(--ff-mono, monospace)' },
    ],
    series: [
      {},
      ...props.series.map((s) => ({ label: s.name, stroke: s.color, width: 1.5, points: { show: false } })),
    ],
    hooks: {
      setCursor: [
        (u: uPlot) => {
          const idx = u.cursor.idx
          if (idx == null) {
            emit('cursor', null)
            return
          }
          const xv = u.data[0]?.[idx]
          if (xv == null) {
            emit('cursor', null)
            return
          }
          const items: CursorItem[] = props.series.map((s, si) => ({
            name: s.name,
            color: s.color,
            uv: Number(u.data[si + 1]?.[idx] ?? 0),
          }))
          emit('cursor', { x: Number(xv), items })
        },
      ],
    },
  }
  return opts
}

function rebuild() {
  const host = hostRef.value
  if (!host) return
  chart.value?.destroy()
  chart.value = null
  if (!props.series.length || !props.data[0]?.length) return
  const w = host.clientWidth || 800
  const h = host.clientHeight || 400
  chart.value = new uPlot(buildOpts(w, h), props.data as unknown as uPlot.AlignedData, host)
}

onMounted(async () => {
  await nextTick()
  rebuild()
  ro = new ResizeObserver(() => {
    const host = hostRef.value
    if (host && chart.value) chart.value.setSize({ width: host.clientWidth, height: host.clientHeight })
  })
  if (hostRef.value) ro.observe(hostRef.value)
})

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  chart.value?.destroy()
  chart.value = null
})

// 数据/序列/Y档/网格 都是用户级低频变化 → 直接重建（最稳，避免 setData/setScale 微妙状态问题）。
watch(
  () => [props.data, props.series, props.yMax, props.showGrid],
  () => rebuild(),
  { deep: false },
)
</script>

<style scoped>
.tcc-host { position: relative; width: 100%; height: 100%; min-height: 0; }
.tcc-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--c-text-3); font-size: 13px; }
</style>
