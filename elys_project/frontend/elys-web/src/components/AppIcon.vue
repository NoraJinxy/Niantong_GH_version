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
  dashboard: ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M14 14h7v7h-7z', 'M3 14h7v7H3z'],
  studies: ['M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-8l-2-3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z'],
  import: ['M12 3v12', 'M7 10l5 5 5-5', 'M4 21h16'],
  analysis: ['M4 7h16', 'M4 12h10', 'M4 17h16'],
  observe: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z', 'M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z'],
  stats: ['M6 20v-6', 'M12 20v-11', 'M18 20v-16'],
  figure: ['M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z', 'M7 9a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'm21 15-5-5L5 21'],
  ai: ['M12 3v3', 'M12 18v3', 'M3 12h3', 'M18 12h3', 'M8 8l-2-2', 'M16 8l2-2', 'M8 16l-2 2', 'M16 16l2 2', 'M9 9h6v6H9z'],
  admin: ['M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z', 'M4 12h2', 'M18 12h2', 'M12 4v2', 'M12 18v2'],
  pipeline: ['M4 6h5v5H4z', 'M15 13h5v5h-5z', 'M9 9h3a3 3 0 0 1 3 3v1'],
  preprocess: ['M4 17c4-8 8 8 16 0', 'M4 7c4 8 8-8 16 0'],
  brain: ['M8 19c-3 0-5-2-5-5 0-2 1-3 2-4 0-3 2-5 5-5 1-2 5-2 6 0 3 0 5 2 5 5 1 1 2 2 2 4 0 3-2 5-5 5H8z'],
  wave: ['M3 12h3l2-6 4 12 3-9 2 3h4'],
  pulse: ['M3 12c1.5-6 4.5-6 6 0s4.5 6 6 0 4.5-6 6 0'],
  spectrum: ['M4 19V5', 'M4 19h16', 'M7 16l3-6 3 3 4-7'],
  heatmap: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],
  network: ['M6 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M18 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M18 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', 'M9 10l6-2', 'M9 12l6 5'],
  source: ['M12 3l8 4-8 4-8-4 8-4z', 'M4 12l8 4 8-4', 'M4 17l8 4 8-4'],
  file: ['M6 3h8l4 4v14H6z', 'M14 3v5h5'],
  database: ['M3 5a9 3 0 1 0 18 0a9 3 0 1 0-18 0', 'M3 5v14a9 3 0 0 0 18 0V5', 'M3 12a9 3 0 0 0 18 0'],
  branch: ['M4 6a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'M4 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'M16 8a2 2 0 1 0 4 0a2 2 0 1 0-4 0', 'M18 10a6 6 0 0 1-6 6H6', 'M6 8v8'],
  layers: ['m12 2 9 5-9 5-9-5 9-5z', 'm3 12 9 5 9-5', 'm3 17 9 5 9-5'],
  cpu: ['M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M9 9h6v6H9z', 'M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3'],
  settings: ['M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z', 'M4 12h2', 'M18 12h2', 'M12 4v2', 'M12 18v2'],
  check: ['M5 13l4 4L19 7'],
  clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3 2'],
  refresh: ['M20 11a8 8 0 0 0-14.2-4.8L4 8', 'M4 4v4h4', 'M4 13a8 8 0 0 0 14.2 4.8L20 16', 'M20 20v-4h-4'],
  plus: ['M12 5v14', 'M5 12h14'],
  x: ['M6 6l12 12', 'M18 6L6 18'],
  warning: ['M12 3 2 20h20z', 'M12 9v5', 'M12 17v.4'],
  activity: ['M3 12h4l3-8 4 16 3-8h4'],
  sparkles: ['M12 4l1.7 4.3L18 10l-4.3 1.7L12 16l-1.7-4.3L6 10l4.3-1.7z'],
  eraser: ['M9 11l7-7 5 5-9 9H7l-3-3z', 'M4 20h16'],
  'chevron-left': ['M15 6l-6 6 6 6'],
  'chevron-right': ['M9 6l6 6-6 6'],
  'chevrons-left': ['M17 6l-6 6 6 6', 'M11 6l-6 6 6 6'],
  'chevrons-right': ['M7 6l6 6-6 6', 'M13 6l6 6-6 6'],
  copy: ['M8 8h10v12H8z', 'M6 16H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2'],
  search: ['M10 18a8 8 0 1 1 5.7-2.3L21 21'],
  trash: ['M3 6h18', 'M8 6V4h8v2', 'M6 6l1 15h10l1-15', 'M10 11v6', 'M14 11v6'],
  restore: ['M4 7v6h6', 'M5 13a7 7 0 1 0 2-5l-3 3'],
  logout: ['M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4', 'M16 17l5-5-5-5', 'M21 12H9'],
  users: ['M16 20v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1', 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8', 'M22 20v-1a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  server: ['M5 4h14a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M5 13h14a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2z', 'M7 8h.01', 'M7 17h.01'],
}

const paths = computed(() => icons[props.name] || icons.plus)
</script>
