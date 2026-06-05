<template>
  <svg
    class="ico"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(path, index) in paths" :key="index" :d="path" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    size?: number
  }>(),
  { size: 18 },
)

const icons: Record<string, string[]> = {
  dashboard: ['M4 13h6V4H4v9z', 'M14 20h6V4h-6v16z', 'M4 20h6v-3H4v3z'],
  studies: ['M3 7h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z'],
  import: ['M12 3v12', 'M7 10l5 5 5-5', 'M4 21h16'],
  analysis: ['M4 7h16', 'M4 12h10', 'M4 17h16'],
  observe: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z', 'M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z'],
  stats: ['M4 19V5', 'M4 19h16', 'M9 15V9', 'M14 15v-4', 'M19 15V7'],
  figure: ['M4 5h16v14H4z', 'M8 14l3-3 3 3 2-4 2 5'],
  ai: ['M12 3v3', 'M12 18v3', 'M3 12h3', 'M18 12h3', 'M8 8l-2-2', 'M16 8l2-2', 'M8 16l-2 2', 'M16 16l2 2', 'M9 9h6v6H9z'],
  admin: ['M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z', 'M4 12h2', 'M18 12h2', 'M12 4v2', 'M12 18v2'],
  pipeline: ['M4 6h5v5H4z', 'M15 13h5v5h-5z', 'M9 9h3a3 3 0 0 1 3 3v1'],
  preprocess: ['M4 17c4-8 8 8 16 0', 'M4 7c4 8 8-8 16 0'],
  brain: ['M8 19c-3 0-5-2-5-5 0-2 1-3 2-4 0-3 2-5 5-5 1-2 5-2 6 0 3 0 5 2 5 5 1 1 2 2 2 4 0 3-2 5-5 5H8z'],
  wave: ['M3 12h3l2-6 4 12 3-9 2 3h4'],
  spectrum: ['M4 19V5', 'M4 19h16', 'M7 16l3-6 3 3 4-7'],
  heatmap: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],
  network: ['M6 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M18 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M18 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M9 10l6-2', 'M9 12l6 5'],
  source: ['M12 3l8 4-8 4-8-4 8-4z', 'M4 12l8 4 8-4', 'M4 17l8 4 8-4'],
  file: ['M6 3h8l4 4v14H6z', 'M14 3v5h5'],
  database: ['M5 6c0-2 14-2 14 0v12c0 2-14 2-14 0V6z', 'M5 10c0 2 14 2 14 0', 'M5 14c0 2 14 2 14 0'],
  settings: ['M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z', 'M4 12h2', 'M18 12h2', 'M12 4v2', 'M12 18v2'],
  check: ['M5 13l4 4L19 7'],
  clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3 2'],
  refresh: ['M20 11a8 8 0 0 0-14.2-4.8L4 8', 'M4 4v4h4', 'M4 13a8 8 0 0 0 14.2 4.8L20 16', 'M20 20v-4h-4'],
  plus: ['M12 5v14', 'M5 12h14'],
  copy: ['M8 8h10v12H8z', 'M6 16H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2'],
  search: ['M10 18a8 8 0 1 1 5.7-2.3L21 21'],
  trash: ['M3 6h18', 'M8 6V4h8v2', 'M6 6l1 15h10l1-15', 'M10 11v6', 'M14 11v6'],
  restore: ['M4 7v6h6', 'M5 13a7 7 0 1 0 2-5l-3 3'],
  logout: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9'],
}

const paths = computed(() => icons[props.name] || icons.plus)
</script>
