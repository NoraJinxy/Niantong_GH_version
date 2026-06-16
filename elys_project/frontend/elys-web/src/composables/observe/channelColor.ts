// 曲线分类色板（elys 风格版）+ 黄金角兜底
// 决策见 日志/10_观察作图与缓存架构260614/05 P-10：默认长在 elys 品牌色上，临床稳重、与全站 token 同源。
// 前 N 条用色板取色；>N 条（多通道/多条件叠加）用黄金角 HSL 生成器保证仍互相可分。

/** elys 风格版 8 色色板（首色=主蓝，2~4 复用 elys 语义红/绿/琥珀）。 */
export const CURVE_PALETTE = [
  '#3F5E8F', // elys 主蓝
  '#B0544C', // 语义红
  '#4F8A6B', // 语义绿
  '#B07F33', // 语义琥珀
  '#5E7BA8', // 强调蓝
  '#7B5EA8', // 紫
  '#2F8A86', // 青
  '#8A6E5E', // 棕
] as const

/**
 * 色板元数据：一处定义，下拉里既拿名字也拿色卡条直接预览。
 * 「定性色板」= 给互不相干的类别（通道 / 条件）分配区分色；
 * 「连续色」（parula / viridis）= 从低到高的有序渐变，更适合强度 / 有序条件。
 */
export interface PaletteDef {
  /** 存储用 key（写进 paletteKey / 未来落库） */
  key: string
  /** 下拉里显示的名字（求短、专业、无来源印记） */
  label: string
  /** 分组（下拉里按组分隔） */
  group: '品牌' | '期刊配色' | '色盲安全' | '通用'
  /** 角标（如「默认」），可选 */
  tag?: string
  /** true=连续色（渐变，按数量取样插值）；缺省=离散色（分类，超出长度循环复用） */
  continuous?: boolean
  /** 色板本体（离散=分类锚点；连续=渐变采样点） */
  colors: readonly string[]
}

export const PALETTE_DEFS: readonly PaletteDef[] = [
  // —— 品牌 —— elys 自有，长在全站 token 上，临床稳重
  { key: 'elys', label: 'elys 风格', group: '品牌', tag: '默认', colors: CURVE_PALETTE },

  // —— 期刊配色 —— 照各大期刊正文图的定性用色，投稿 / 出图直接对味
  { key: 'npg', label: 'Nature 风格', group: '期刊配色',
    colors: ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#7E6148'] },
  { key: 'aaas', label: 'Science 风格', group: '期刊配色',
    colors: ['#3B4992', '#EE0000', '#008B45', '#631879', '#008280', '#BB0021', '#5F559B', '#A20056'] },
  { key: 'lancet', label: 'Lancet 风格', group: '期刊配色',
    colors: ['#00468B', '#ED0000', '#42B540', '#0099B4', '#925E9F', '#FDAF91', '#AD002A', '#ADB6B6'] },
  { key: 'nejm', label: 'NEJM 风格', group: '期刊配色',
    colors: ['#BC3C29', '#0072B5', '#E18727', '#20854E', '#7876B1', '#6F99AD', '#FFDC91', '#EE4C97'] },
  { key: 'jama', label: 'JAMA 风格', group: '期刊配色',
    colors: ['#374E55', '#DF8F44', '#00A1D5', '#B24745', '#79AF97', '#6A6599', '#80796B'] },

  // —— 色盲安全 —— 经红绿色盲校验仍可区分；做演讲 / 投稿无障碍要求时用
  { key: 'wong', label: 'Wong', group: '色盲安全',
    colors: ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#999999'] },
  { key: 'tol', label: 'Tol Bright', group: '色盲安全',
    colors: ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB'] },

  // —— 通用 —— 可视化界出镜率最高的几套；前段定性色板，后段 parula / viridis 是连续色
  // 许可：ColorBrewer = Apache-2.0、seaborn = BSD、viridis = CC0 公共领域，均可商用；
  // Scientific Lines / parula 仅自行列出 RGB 数值（不含任何专有源码）。
  { key: 'tableau', label: 'Tableau 10', group: '通用',
    colors: ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC'] },
  { key: 'd3', label: 'D3 Category10', group: '通用',
    colors: ['#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD', '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF'] },
  { key: 'seaborn', label: 'seaborn deep', group: '通用',
    colors: ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B3', '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD'] },
  { key: 'set1', label: 'ColorBrewer Set1', group: '通用',
    colors: ['#E41A1C', '#377EB8', '#4DAF4A', '#984EA3', '#FF7F00', '#FFFF33', '#A65628', '#F781BF', '#999999'] },
  { key: 'set2', label: 'ColorBrewer Set2', group: '通用',
    colors: ['#66C2A5', '#FC8D62', '#8DA0CB', '#E78AC3', '#A6D854', '#FFD92F', '#E5C494', '#B3B3B3'] },
  { key: 'scientific', label: 'Scientific Lines', group: '通用',
    colors: ['#0072BD', '#D95319', '#EDB120', '#7E2F8E', '#77AC30', '#4DBEEE', '#A2142F'] },
  // 以下两套为连续色：从低到高的有序渐变，按索引取样亦可给多曲线上色
  { key: 'parula', label: 'parula', group: '通用', continuous: true,
    colors: ['#352A87', '#0B5DCF', '#1F8FC9', '#2DB7A3', '#7AC35C', '#C0BB3E', '#F6C72B', '#FCED2E'] },
  { key: 'viridis', label: 'viridis', group: '通用', continuous: true,
    colors: ['#440154', '#482878', '#3E4A89', '#31688E', '#26828E', '#1F9E89', '#35B779', '#6DCD59', '#B4DE2C', '#FDE725'] },
]

/** key → 色板，供 channelColor 取色。 */
export const PALETTES: Record<string, readonly string[]> = Object.fromEntries(
  PALETTE_DEFS.map((d) => [d.key, d.colors]),
)

function hexToRgb(hex: string): [number, number, number] {
  const s = hex.replace('#', '')
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)]
}

/** 把色板当渐变，在 t∈[0,1] 处取样（相邻锚点间线性插值），供连续色板用。 */
function sampleRamp(colors: readonly string[], t: number): string {
  const n = colors.length
  if (n === 0) return '#888888'
  if (n === 1) return colors[0]
  const x = Math.max(0, Math.min(1, t)) * (n - 1)
  const i0 = Math.floor(x)
  const i1 = Math.min(n - 1, i0 + 1)
  const f = x - i0
  const [r0, g0, b0] = hexToRgb(colors[i0])
  const [r1, g1, b1] = hexToRgb(colors[i1])
  return `rgb(${Math.round(r0 + (r1 - r0) * f)}, ${Math.round(g0 + (g1 - g0) * f)}, ${Math.round(b0 + (b1 - b0) * f)})`
}

/**
 * 第 i 条曲线（同维度共 count 条）的颜色。
 * - 连续色板（viridis / parula）：把色板当渐变、按 i/(count-1) 铺满取样——全选 63 通道时每条都有不同色（修「通道一多配色不生效」）。
 * - 离散色板：前 N 条直接取色板；超出色板长度则循环复用，保证所选色板始终生效，而非退化成与色板无关的彩虹。
 */
export function channelColor(
  i: number,
  palette: readonly string[] = CURVE_PALETTE,
  opts?: { count?: number; continuous?: boolean },
): string {
  const n = palette.length
  if (opts?.continuous && n > 0) {
    const count = Math.max(1, opts.count ?? n)
    return sampleRamp(palette, count <= 1 ? 0 : i / (count - 1))
  }
  if (i >= 0 && i < n) return palette[i]
  if (n > 0) return palette[((i % n) + n) % n] // 离散超长：循环复用色板
  const hue = Math.round((i * 137.508) % 360) // 空色板兜底：黄金角
  return `hsl(${hue}, 58%, 46%)`
}
