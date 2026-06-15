<template>
  <canvas ref="cv" class="mini-spark"></canvas>
</template>

<script setup lang="ts">
// 通道列表里的内嵌迷你波形：把整段下采样成一条 ~40px 宽的小折线，供选道前预览。
// 纯展示、无交互；数据/颜色变化时重画。
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{ values: number[]; color?: string; w?: number; h?: number }>(),
  { color: '#5E7BA8', w: 40, h: 13 },
)

const cv = ref<HTMLCanvasElement | null>(null)
const dpr = Math.max(window.devicePixelRatio || 1, 2)

function draw() {
  const c = cv.value
  if (!c) return
  const w = props.w
  const h = props.h
  c.width = w * dpr
  c.height = h * dpr
  c.style.width = w + 'px'
  c.style.height = h + 'px'
  const ctx = c.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)
  const vals = props.values
  const n = vals.length
  if (n < 2) return
  // 全样本扫真实极值（抽样会漏掉尖峰；逐列 min/max 包络保峰）
  let min = Infinity
  let max = -Infinity
  for (let i = 0; i < n; i++) {
    const v = vals[i]
    if (!Number.isFinite(v)) continue
    if (v < min) min = v
    if (v > max) max = v
  }
  if (!Number.isFinite(min) || max === min) {
    min -= 1
    max += 1
  }
  const pad = 1.5
  const cols = Math.min(w, n)
  const colW = n / cols
  const yOf = (v: number) => h - pad - ((v - min) / (max - min)) * (h - 2 * pad)
  const xOf = (ci: number) => (ci / Math.max(1, cols - 1)) * (w - 2 * pad) + pad
  ctx.beginPath()
  ctx.strokeStyle = props.color
  ctx.lineWidth = 0.9
  let started = false
  for (let ci = 0; ci < cols; ci++) {
    const lo = Math.floor(ci * colW)
    const hi = Math.min(n, Math.floor((ci + 1) * colW))
    let cmin = Infinity
    let cmax = -Infinity
    for (let i = lo; i < hi; i++) {
      const v = vals[i]
      if (!Number.isFinite(v)) continue
      if (v < cmin) cmin = v
      if (v > cmax) cmax = v
    }
    if (!Number.isFinite(cmin)) {
      started = false // 该列全无有限值 → 断笔，下一有效列重新起笔
      continue
    }
    const x = xOf(ci)
    if (started) ctx.lineTo(x, yOf(cmax))
    else { ctx.moveTo(x, yOf(cmax)); started = true }
    ctx.lineTo(x, yOf(cmin)) // 同列 max→min 画竖段成包络
  }
  ctx.stroke()
}

onMounted(draw)
watch(() => [props.values, props.color], draw, { deep: false })
</script>

<style scoped>
.mini-spark { display: block; opacity: 0.72; }
</style>
