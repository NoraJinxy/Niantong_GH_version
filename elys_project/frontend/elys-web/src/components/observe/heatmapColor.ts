// 时频热图配色（TFR 专用）：
//  招牌：elys 风格发散色（默认；红蓝为主·无屎黄·深沉，冷端入深靛取 Turbo 深度 + Viridis 沉稳）
//  双色/发散（值有正负、0 居中，多用于有基线校正的 ERD/ERS）：elys / rdbu / rdylbu / coolwarm / spectral / puor
//  单向/顺序（值恒非负，多用于绝对功率）：viridis / plasma / inferno / magma / hot / jet / turbo
// 大面积着色走 buildHeatmapLut()+ImageData（HeatmapCanvas），少量小色块走 heatmapColorOf()，
// colorbar / 色卡走 heatmapCssGradient()（纯 CSS 渐变，从关键帧生成、与 LUT 同源）。

export type HeatmapCmap =
  | 'elys'
  | 'rdbu' | 'rdylbu' | 'coolwarm' | 'spectral' | 'puor'
  | 'viridis' | 'plasma' | 'inferno' | 'magma' | 'hot' | 'jet' | 'turbo'
export const HEATMAP_LUT_N = 256

const WHITE: readonly [number, number, number] = [245, 247, 250]
const BLUE: readonly [number, number, number] = [38, 92, 186]
const RED: readonly [number, number, number] = [206, 52, 48]

type Stops = readonly (readonly [number, readonly [number, number, number]])[]

// ---- 单向/顺序色关键帧（k∈[0,1]，线性分段插值）----
const VIRIDIS: Stops = [
  [0.0, [68, 1, 84]], [0.25, [59, 82, 139]], [0.5, [33, 144, 140]], [0.75, [93, 201, 99]], [1.0, [253, 231, 37]],
]
const PLASMA: Stops = [
  [0.0, [13, 8, 135]], [0.25, [126, 3, 168]], [0.5, [204, 71, 120]], [0.75, [248, 149, 64]], [1.0, [240, 249, 33]],
]
const INFERNO: Stops = [
  [0.0, [0, 0, 4]], [0.25, [87, 16, 110]], [0.5, [188, 55, 84]], [0.75, [249, 142, 9]], [1.0, [252, 255, 164]],
]
const MAGMA: Stops = [
  [0.0, [0, 0, 4]], [0.25, [81, 18, 124]], [0.5, [183, 55, 121]], [0.75, [252, 137, 97]], [1.0, [252, 253, 191]],
]
const HOT: Stops = [
  [0.0, [0, 0, 0]], [0.35, [255, 0, 0]], [0.65, [255, 255, 0]], [1.0, [255, 255, 255]],
]
const JET: Stops = [
  [0.0, [0, 0, 131]], [0.2, [0, 60, 170]], [0.4, [5, 255, 255]], [0.6, [255, 255, 0]], [0.8, [250, 0, 0]], [1.0, [128, 0, 0]],
]
const TURBO: Stops = [
  [0.0, [48, 18, 59]], [0.25, [33, 144, 229]], [0.5, [124, 242, 103]], [0.75, [244, 168, 46]], [1.0, [122, 4, 3]],
]

// ---- 双色/发散色关键帧（t∈[-1,1]，负=减弱/ERD，正=增强/ERS，0 居中）----
const RDBU: Stops = [
  [-1.0, [38, 92, 186]], [0.0, [245, 247, 250]], [1.0, [206, 52, 48]],
]
const RDYLBU: Stops = [
  [-1.0, [69, 117, 180]], [-0.5, [171, 217, 233]], [0.0, [255, 255, 191]], [0.5, [253, 174, 97]], [1.0, [215, 48, 39]],
]
const COOLWARM: Stops = [
  [-1.0, [59, 76, 192]], [-0.5, [124, 159, 230]], [0.0, [221, 221, 221]], [0.5, [230, 146, 123]], [1.0, [180, 4, 38]],
]
const SPECTRAL: Stops = [
  [-1.0, [50, 136, 189]], [-0.5, [153, 213, 148]], [0.0, [255, 255, 191]], [0.5, [253, 174, 97]], [1.0, [213, 62, 79]],
]
const PUOR: Stops = [
  [-1.0, [179, 88, 6]], [-0.5, [241, 163, 64]], [0.0, [247, 247, 247]], [0.5, [153, 142, 195]], [1.0, [84, 39, 136]],
]

// elys 招牌发散色（TFR 默认）：深靛→钴蓝→中蓝→冷净白(0)→灰玫→绯红→深酒红。
// 红蓝为主·无屎黄（暖端只走 白→玫→红，不碰金/桃/铜）·深沉，冷端入深靛取 Turbo 深度 + Viridis 沉稳；
// 中段贴品牌主蓝 #3F5E8F × 语义红 #B0544C 一脉，与时域/频域曲线色同家族（团队多轮比选定稿，原 elys1/3/4 已弃）。
const ELYS: Stops = [
  [-1.0, [37, 27, 68]], [-0.55, [45, 80, 150]], [-0.2, [112, 150, 202]],
  [0.0, [235, 238, 242]],
  [0.2, [212, 150, 150]], [0.55, [184, 74, 74]], [1.0, [106, 30, 42]],
]

const STOPS: Record<HeatmapCmap, Stops> = {
  elys: ELYS,
  rdbu: RDBU, rdylbu: RDYLBU, coolwarm: COOLWARM, spectral: SPECTRAL, puor: PUOR,
  viridis: VIRIDIS, plasma: PLASMA, inferno: INFERNO, magma: MAGMA, hot: HOT, jet: JET, turbo: TURBO,
}

export const IS_SEQUENTIAL: Record<HeatmapCmap, boolean> = {
  elys: false,
  rdbu: false, rdylbu: false, coolwarm: false, spectral: false, puor: false,
  viridis: true, plasma: true, inferno: true, magma: true, hot: true, jet: true, turbo: true,
}

// 色卡下拉用：发散在前、顺序在后（同顺序也决定下拉里的排列）
export const HEATMAP_CMAPS: { key: HeatmapCmap; label: string }[] = [
  { key: 'elys', label: 'elys 风格' },
  { key: 'rdbu', label: 'RdBu' },
  { key: 'rdylbu', label: 'RdYlBu' },
  { key: 'coolwarm', label: 'Coolwarm' },
  { key: 'spectral', label: 'Spectral' },
  { key: 'puor', label: 'PuOr' },
  { key: 'viridis', label: 'Viridis' },
  { key: 'plasma', label: 'Plasma' },
  { key: 'inferno', label: 'Inferno' },
  { key: 'magma', label: 'Magma' },
  { key: 'hot', label: 'Hot' },
  { key: 'jet', label: 'Jet' },
  { key: 'turbo', label: 'Turbo' },
]

function lerp(a: number, b: number, k: number): number {
  return a + (b - a) * k
}

function lerpStops(stops: Stops, t: number): [number, number, number] {
  const tt = t < stops[0][0] ? stops[0][0] : t > stops[stops.length - 1][0] ? stops[stops.length - 1][0] : t
  for (let i = 1; i < stops.length; i++) {
    const [p0, c0] = stops[i - 1]
    const [p1, c1] = stops[i]
    if (tt <= p1) {
      const f = (tt - p0) / (p1 - p0 || 1)
      return [Math.round(lerp(c0[0], c1[0], f)), Math.round(lerp(c0[1], c1[1], f)), Math.round(lerp(c0[2], c1[2], f))]
    }
  }
  const last = stops[stops.length - 1][1]
  return [last[0], last[1], last[2]]
}

// 烤 LUT：i∈[0,N)。顺序色 k∈[0,1]；发散色 t=k*2-1∈[-1,1]。
export function buildHeatmapLut(cmap: HeatmapCmap): Uint8Array {
  const lut = new Uint8Array(HEATMAP_LUT_N * 3)
  const stops = STOPS[cmap]
  const seq = IS_SEQUENTIAL[cmap]
  for (let i = 0; i < HEATMAP_LUT_N; i++) {
    const k = i / (HEATMAP_LUT_N - 1)
    let rgb: [number, number, number]
    if (cmap === 'rdbu') {
      // rdbu：轻 gamma 0.8 让中等幅值也显色（保留经典 ERSP 观感）
      const t = k * 2 - 1
      const target = t < 0 ? BLUE : RED
      const kk = Math.pow(Math.abs(t), 0.8)
      rgb = [
        Math.round(lerp(WHITE[0], target[0], kk)),
        Math.round(lerp(WHITE[1], target[1], kk)),
        Math.round(lerp(WHITE[2], target[2], kk)),
      ]
    } else {
      rgb = lerpStops(stops, seq ? k : k * 2 - 1)
    }
    lut[i * 3] = rgb[0]
    lut[i * 3 + 1] = rgb[1]
    lut[i * 3 + 2] = rgb[2]
  }
  return lut
}

const lutCache: Partial<Record<HeatmapCmap, Uint8Array>> = {}
function cachedLut(cmap: HeatmapCmap): Uint8Array {
  return (lutCache[cmap] ??= buildHeatmapLut(cmap))
}

/** 值→归一化 LUT 下标。顺序色 v/zmax∈[0,1]；发散色 v/zmax∈[-1,1]。 */
export function heatmapLutIndex(value: number, zmax: number, cmap: HeatmapCmap): number {
  const s = zmax > 0 ? zmax : 1
  if (IS_SEQUENTIAL[cmap]) {
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

/** colorbar / 色卡的 CSS 渐变，从关键帧生成。dir 默认 'to top'（colorbar 竖排）；色卡传 'to right'。 */
export function heatmapCssGradient(cmap: HeatmapCmap, dir: 'to top' | 'to right' = 'to top'): string {
  const stops = STOPS[cmap]
  const seq = IS_SEQUENTIAL[cmap]
  const parts = stops.map(([p, c]) => {
    const pct = Math.round((seq ? p : (p + 1) / 2) * 100)
    return `rgb(${c[0]},${c[1]},${c[2]}) ${pct}%`
  })
  return `linear-gradient(${dir}, ${parts.join(', ')})`
}
