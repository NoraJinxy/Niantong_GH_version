// 时频热图配色（TFR 专用）：
//  - 发散色 rdbu：基线校正后的有符号功率（dB/%/z），0 居中、负偏蓝(ERD)、正偏红(ERS)——ERSP 临床标准。
//    白心 + 蓝/红两端与 TopoStrip 的发散色严格一致，保证观察页内「热图 ↔ 地形图」视觉同源。
//  - 顺序色 viridis：绝对功率（baseline_mode=none，值恒非负），低→高单调，色盲友好。
// 大面积着色走 buildHeatmapLut()+ImageData（HeatmapCanvas），少量小色块走 heatmapColorOf()，
// colorbar 走 heatmapCssGradient()（纯 CSS 渐变，不占画布）。

export type HeatmapCmap = 'rdbu' | 'viridis'
export const HEATMAP_LUT_N = 256

const WHITE: readonly [number, number, number] = [245, 247, 250]
const BLUE: readonly [number, number, number] = [38, 92, 186] // ERD（功率减弱）
const RED: readonly [number, number, number] = [206, 52, 48] // ERS（功率增强）
// viridis 关键停靠点（标准近似，5 段线性插值已足够平滑）
const VIRIDIS: readonly (readonly [number, readonly [number, number, number]])[] = [
  [0.0, [68, 1, 84]],
  [0.25, [59, 82, 139]],
  [0.5, [33, 144, 140]],
  [0.75, [93, 201, 99]],
  [1.0, [253, 231, 37]],
]

function lerp(a: number, b: number, k: number): number {
  return a + (b - a) * k
}

function viridisAt(k: number): [number, number, number] {
  const t = k < 0 ? 0 : k > 1 ? 1 : k
  for (let i = 1; i < VIRIDIS.length; i++) {
    const [p0, c0] = VIRIDIS[i - 1]
    const [p1, c1] = VIRIDIS[i]
    if (t <= p1) {
      const f = (t - p0) / (p1 - p0 || 1)
      return [Math.round(lerp(c0[0], c1[0], f)), Math.round(lerp(c0[1], c1[1], f)), Math.round(lerp(c0[2], c1[2], f))]
    }
  }
  const last = VIRIDIS[VIRIDIS.length - 1][1]
  return [last[0], last[1], last[2]]
}

// 烤 LUT：i∈[0,N)。rdbu → t∈[-1,1] 发散（轻 gamma 0.8 让中等幅值也显色）；viridis → k∈[0,1] 顺序。
export function buildHeatmapLut(cmap: HeatmapCmap): Uint8Array {
  const lut = new Uint8Array(HEATMAP_LUT_N * 3)
  for (let i = 0; i < HEATMAP_LUT_N; i++) {
    let r: number
    let g: number
    let b: number
    if (cmap === 'viridis') {
      ;[r, g, b] = viridisAt(i / (HEATMAP_LUT_N - 1))
    } else {
      const t = (i / (HEATMAP_LUT_N - 1)) * 2 - 1
      const target = t < 0 ? BLUE : RED
      const k = Math.pow(Math.abs(t), 0.8)
      r = Math.round(lerp(WHITE[0], target[0], k))
      g = Math.round(lerp(WHITE[1], target[1], k))
      b = Math.round(lerp(WHITE[2], target[2], k))
    }
    lut[i * 3] = r
    lut[i * 3 + 1] = g
    lut[i * 3 + 2] = b
  }
  return lut
}

// 模块级 LUT 缓存（heatmapColorOf 用；画布自己持 LUT 不走这里）
const lutCache: Partial<Record<HeatmapCmap, Uint8Array>> = {}
function cachedLut(cmap: HeatmapCmap): Uint8Array {
  return (lutCache[cmap] ??= buildHeatmapLut(cmap))
}

/** 值→归一化 LUT 下标。rdbu：v/zmax∈[-1,1]→[0,N)；viridis：v/zmax∈[0,1]→[0,N)。 */
export function heatmapLutIndex(value: number, zmax: number, cmap: HeatmapCmap): number {
  const s = zmax > 0 ? zmax : 1
  if (cmap === 'viridis') {
    let k = value / s
    k = k < 0 ? 0 : k > 1 ? 1 : k
    return (k * (HEATMAP_LUT_N - 1)) | 0
  }
  let t = value / s
  t = t < -1 ? -1 : t > 1 ? 1 : t
  return (((t + 1) * 0.5) * (HEATMAP_LUT_N - 1)) | 0
}

/** 单值取 rgb 字符串（右栏色块等少量用途）。 */
export function heatmapColorOf(value: number, zmax: number, cmap: HeatmapCmap): string {
  if (!Number.isFinite(value)) return 'rgb(245,247,250)'
  const lut = cachedLut(cmap)
  const li = heatmapLutIndex(value, zmax, cmap) * 3
  return `rgb(${lut[li]},${lut[li + 1]},${lut[li + 2]})`
}

/** colorbar 的 CSS 渐变（从下到上 = 低值→高值）。 */
export function heatmapCssGradient(cmap: HeatmapCmap): string {
  if (cmap === 'viridis') return 'linear-gradient(to top, #440154, #3b528b, #21908c, #5ec962, #fde725)'
  return 'linear-gradient(to top, rgb(38,92,186), rgb(245,247,250), rgb(206,52,48))'
}
