// 配色状态（观察页共用）：色板选择 + 下拉分组 + 取色器。
// 所有曲线/圆点/sparkline 都走 colorAt()，切换色板即全站生效。移植自 WaveformDetailPage 的 palette 逻辑。
import { computed, ref } from 'vue'
import { channelColor, PALETTE_DEFS } from './channelColor'

const PALETTE_GROUP_ORDER = ['推荐', '期刊配色', '色盲安全', '通用'] as const

export function usePalette(defaultKey = 'elys') {
  const paletteKey = ref<string>(defaultKey)
  const palOpen = ref(false) // 下拉是否展开

  const currentPalette = computed(() => PALETTE_DEFS.find((d) => d.key === paletteKey.value) ?? PALETTE_DEFS[0])
  const palette = computed(() => currentPalette.value.colors)
  const paletteContinuous = computed(() => currentPalette.value.continuous === true)

  // 下拉按组分隔：推荐 / 期刊配色 / 色盲安全 / 通用
  const paletteGroups = PALETTE_GROUP_ORDER.map((label) => ({
    label,
    items: PALETTE_DEFS.filter((d) => d.group === label),
  }))

  function selectPalette(k: string) {
    paletteKey.value = k
    palOpen.value = false
  }

  /** 第 i 项（同维度共 count 个）的颜色：连续色板铺满渐变、离散色板循环复用。 */
  function colorAt(i: number, count: number) {
    return channelColor(i, palette.value, { count, continuous: paletteContinuous.value })
  }

  return { paletteKey, palOpen, currentPalette, palette, paletteContinuous, paletteGroups, selectPalette, colorAt }
}
