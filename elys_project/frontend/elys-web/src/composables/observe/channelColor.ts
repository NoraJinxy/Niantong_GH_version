// 曲线分类色板（elys 烙印版）+ 黄金角兜底
// 决策见 日志/10_观察作图与缓存架构260614/05 P-10：默认长在 elys 品牌色上，临床稳重、与全站 token 同源。
// 前 8 条用定性色板；>8 条（多通道/多条件叠加）用黄金角 HSL 生成器保证仍互相可分。

/** elys 烙印版 8 色定性色板（首色=主蓝，2~4 复用 elys 语义红/绿/琥珀）。 */
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

/** 备用色板：NPG（Nature 期刊感）/ Wong（色盲安全·Nature Methods）。供未来「配色下拉」切换。 */
export const PALETTES: Record<string, readonly string[]> = {
  elys: CURVE_PALETTE,
  npg: ['#E64B35', '#4DBBD5', '#00A087', '#3C5488', '#F39B7F', '#8491B4', '#91D1C2', '#7E6148'],
  wong: ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#999999'],
}

/** 第 i 条曲线的颜色：前 8 走色板，之后黄金角 HSL 兜底。 */
export function channelColor(i: number, palette: readonly string[] = CURVE_PALETTE): string {
  if (i >= 0 && i < palette.length) return palette[i]
  const hue = Math.round((i * 137.508) % 360) // 黄金角，相邻条色相差最大
  return `hsl(${hue}, 58%, 46%)`
}
