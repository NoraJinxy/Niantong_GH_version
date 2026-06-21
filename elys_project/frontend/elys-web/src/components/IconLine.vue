<!--
  IconLine — 统一的线条 icon 系统（lucide 风格）。

  用法:
    <IconLine name="pin" />
    <IconLine name="x" :size="14" />
    <IconLine name="save" :stroke-width="1.5" class="my-icon" />

  设计原则:
    - 单色：fill="none" + stroke="currentColor"，颜色随父元素文字色（CSS 中 color 控制）
    - 线条粗细统一 1.8px（对齐 AppIcon / 设计系统 Lucide 标准，两套图标粗细一致）
    - 24×24 viewBox，等比缩放
    - rounded line caps/joins（圆角端点，柔和）

  Paths 来自 lucide-icons (MIT License) 简化或直采。
-->
<script setup lang="ts">
interface Props {
  /** Icon 名称，对应 PATHS 字典 key */
  name: string
  /** 像素尺寸（默认 14） */
  size?: number | string
  /** 描边粗细（默认 1.6） */
  strokeWidth?: number | string
}

withDefaults(defineProps<Props>(), {
  size: 14,
  strokeWidth: 1.8,
})

/**
 * SVG path 字典。每个 entry 包含一个或多个独立 path / shape。
 * 用元组数组而非单 path 字符串，便于多 path 组合（如 save 三段、clipboard 两段）。
 *
 * type:
 *  - string  → 单 path d
 *  - array   → 多 path，每个元素是一个 path d
 *
 * 所有 path 在 24×24 viewBox 内。
 */
const PATHS: Record<string, string | string[]> = {
  // === 基础操作 ===
  pin: 'M12 17v5 M9 10.76V7a3 3 0 1 1 6 0v3.76a2 2 0 0 0 1.11 1.79l1.78.9A2 2 0 0 1 19 15.24V16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-.76a2 2 0 0 1 1.11-1.79l1.78-.9A2 2 0 0 0 9 10.76Z',
  x: 'M18 6 6 18 M6 6l12 12',
  check: 'M20 6 9 17l-5-5',
  plus: 'M12 5v14 M5 12h14',
  minus: 'M5 12h14',
  trash: 'M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6',

  // === 文件 / 数据 ===
  save: 'M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z M17 21v-8H7v8 M7 3v5h8',
  clipboard: 'M8 2h8a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2',
  folder: 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
  list: 'M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01',

  // === 工具 / 系统 ===
  // scissors：圆把手用 path 弧线近似 lucide 的两个 circle（IconLine 只渲染 <path>）
  scissors: ['M6 6m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0', 'M6 18m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0', 'M8.12 8.12 12 12', 'M20 4 8.12 15.88', 'M14.8 14.8 20 20'],
  settings: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  lock: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3',
  zap: 'M13 2 3 14h9l-1 8 10-12h-9l1-8z',

  // === 数据 / 图表 ===
  barChart: 'M3 3v18h18 M7 16V10 M12 16V6 M17 16V13',
  pieChart: 'M21.21 15.89A10 10 0 1 1 8 2.83 M22 12A10 10 0 0 0 12 2v10z',
  target: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  trendingUp: 'm22 7-8.5 8.5-5-5L2 17 M16 7h6v6',
  // 被试（人）/ 时长（钟）—— 语义对齐，替换原先用 target(靶心)/play(播放) 充数的写法
  users: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  clock: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M12 6v6l4 2'],

  // === AI / 机器学习 ===
  cpu: 'M16 4h-1a3 3 0 0 0-3 3v1 M15 20h-1a3 3 0 0 1-3-3v-1 M20 16v1a3 3 0 0 1-3 3h-1 M20 8v-1a3 3 0 0 0-3-3h-1 M4 16v1a3 3 0 0 0 3 3h1 M4 8v-1a3 3 0 0 1 3-3h1 M9 9h6v6h-6z M2 14h2 M2 18h2 M2 6h2 M2 10h2 M22 14h-2 M22 18h-2 M22 6h-2 M22 10h-2 M14 22v-2 M18 22v-2 M6 22v-2 M10 22v-2 M14 2v2 M18 2v2 M6 2v2 M10 2v2',
  brain: 'M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z',
  sparkles: 'm12 3-1.9 5.8L4.3 10.7l5.8 1.9 1.9 5.8 1.9-5.8 5.8-1.9-5.8-1.9z M5 3v4 M19 17v4 M3 5h4 M17 19h4',
  bot: 'M12 8V4H8 M14 2H10 M16 8h.01 M8 8h.01 M5 11a8 8 0 0 1 8-8 8 8 0 0 1 8 8v6H5z M9 13v2 M15 13v2 M20 18h2 M2 18h2 M16 22h-8 M11 7l1 1',

  // === 导航 / 状态 ===
  gripVertical: 'M9 4h.01 M9 9h.01 M9 14h.01 M9 19h.01 M15 4h.01 M15 9h.01 M15 14h.01 M15 19h.01',
  chevronRight: 'm9 18 6-6-6-6',
  chevronDown: 'm6 9 6 6 6-6',
  chevronUp: 'm18 15-6-6-6 6',
  chevronLeft: 'm15 18-6-6 6-6',
  info: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 16v-4 M12 8h.01',
  alert: 'M12 9v4 M12 17h.01 M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z',
  play: 'm6 3 14 9-14 9V3z',
  pause: 'M14 4h4v16h-4z M6 4h4v16H6z',
}

function asPaths(value: string | string[]): string[] {
  return Array.isArray(value) ? value : [value]
}
</script>

<template>
  <svg
    class="icon-line"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    :stroke-width="strokeWidth"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path
      v-for="(d, idx) in asPaths(PATHS[name] || '')"
      :key="idx"
      :d="d"
    />
  </svg>
</template>

<style scoped>
.icon-line {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
