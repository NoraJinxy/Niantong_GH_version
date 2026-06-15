<template>
  <div class="topo-strip">
    <div class="topo-cap">地形图<span class="topo-cap-sub">区间均值 µV</span></div>
    <div class="topo-cards">
      <div v-for="c in cells" :key="c.seg" class="topo-card" :style="{ borderTopColor: c.color }">
        <div class="topo-hd"><span class="topo-dot" :style="{ background: c.color }"></span>{{ c.label }}</div>
        <svg v-if="c.points && c.points.length" viewBox="-1.28 -1.34 2.56 2.62" class="topo-svg">
          <circle cx="0" cy="0" r="1" fill="#FCFCFE" stroke="#C4CCD8" stroke-width="0.02" />
          <path d="M -0.13 -0.99 Q 0 -1.24 0.13 -0.99" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
          <path d="M -1 -0.2 Q -1.13 0 -1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
          <path d="M 1 -0.2 Q 1.13 0 1 0.2" fill="none" stroke="#C4CCD8" stroke-width="0.02" />
          <circle
            v-for="p in c.points"
            :key="p.name"
            :cx="p.x"
            :cy="-p.y"
            r="0.084"
            :fill="divColor(p.value, vmax)"
            stroke="#ffffff"
            stroke-width="0.016"
          >
            <title>{{ p.name }}: {{ p.value.toFixed(2) }} µV</title>
          </circle>
        </svg>
        <div v-else class="topo-empty">无电极坐标<br />(该结果未带 montage)</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 真实地形图条：用后端给的电极 2D 投影坐标（ch_pos），按统计区间均值给电极点着色。
// 不做插值热力图（那是出图二期 doc04）；这里只画「电极点按值着色 + 头皮轮廓」，是真实数据、不造假。
interface TopoPoint { name: string; x: number; y: number; value: number }
interface TopoCell { seg: number; label: string; color: string; points: TopoPoint[] | null }
defineProps<{ cells: TopoCell[]; vmax: number }>()

// 发散色：负→蓝、零→近白、正→红（与 elys 烙印主蓝/语义红同源）
function divColor(v: number, vmax: number): string {
  const m = vmax > 0 ? vmax : 1
  const t = Math.max(-1, Math.min(1, v / m))
  const white = [244, 246, 249]
  const target = t < 0 ? [63, 94, 143] : [176, 84, 76]
  const k = Math.abs(t)
  const r = Math.round(white[0] + (target[0] - white[0]) * k)
  const g = Math.round(white[1] + (target[1] - white[1]) * k)
  const b = Math.round(white[2] + (target[2] - white[2]) * k)
  return `rgb(${r}, ${g}, ${b})`
}
</script>

<style scoped>
.topo-strip { flex-shrink: 0; display: flex; align-items: stretch; gap: 8px; margin-top: 8px; }
.topo-cap { display: flex; flex-direction: column; justify-content: center; font-size: 10px; color: var(--c-text-3); white-space: nowrap; padding-right: 4px; border-right: 1px solid var(--c-border); }
.topo-cap-sub { font-size: 8px; margin-top: 2px; }
.topo-cards { display: flex; gap: 8px; overflow-x: auto; flex: 1; }
.topo-card { width: 116px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; border: 1px solid var(--c-border); border-top-width: 2px; border-radius: var(--r-sm); background: var(--c-surface); padding: 4px 4px 2px; box-shadow: 0 1px 3px rgba(0, 0, 0, .04); }
.topo-hd { font-size: 9px; font-weight: 600; color: var(--c-text-2); display: flex; align-items: center; gap: 4px; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.topo-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.topo-svg { width: 100%; height: 96px; display: block; }
.topo-empty { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 9px; color: var(--c-text-3); line-height: 1.4; padding: 12px 4px; }
</style>
