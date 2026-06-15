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
  const step = Math.max(1, Math.floor(n / w))
  let min = Infinity
  let max = -Infinity
  for (let i = 0; i < n; i += step) {
    const v = vals[i]
    if (v < min) min = v
    if (v > max) max = v
  }
  if (!Number.isFinite(min) || max === min) {
    min -= 1
    max += 1
  }
  const pad = 1.5
  const cols = Math.ceil(n / step)
  ctx.beginPath()
  ctx.strokeStyle = props.color
  ctx.lineWidth = 0.9
  let first = true
  let xi = 0
  for (let i = 0; i < n; i += step) {
    const v = vals[i]
    const x = (xi / Math.max(1, cols - 1)) * (w - 2 * pad) + pad
    const y = h - pad - ((v - min) / (max - min)) * (h - 2 * pad)
    if (first) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
    first = false
    xi++
  }
  ctx.stroke()
}

onMounted(draw)
watch(() => [props.values, props.color], draw, { deep: false })
</script>

<style scoped>
.mini-spark { display: block; opacity: 0.72; }
</style>
