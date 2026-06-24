/**
 * Purpose: 观察页线图(时域 ERP / 频域 PSD) PNG 导出——把已渲染的高清 chart canvas
 *          合成进一张「页眉(标题 / 被试条件 / 类型徽标) + 页脚(溯源指纹 / 品牌·时间戳)」的
 *          设计画框，时域、频域两页共用。chart 本体不重画、1:1 贴入保清晰。
 * Related: views/WaveformPage.vue、views/PsdPage.vue 的 exportCell；
 *          chart 由 TimeCourseCanvas.getExportCanvas 产出；与地形图导出同设计语言(纯白 + 淡描边 + 无阴影)。
 */

// 离屏 canvas 取不到 CSS 变量，硬编码 elys token 真值（与地形图导出同策略）。
const PAPER = '#ffffff'
const CARD_BORDER = '#E5E9F2'
const DIVIDER = '#E4E9F1'
const C_TITLE = '#20293B'
const C_SUB = '#79859A'
const C_PRIMARY = '#3F5E8F'
const BADGE_BG = '#E9EEF6'
const FONT_SANS = `'Inter', -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif`
const FONT_MONO = `'JetBrains Mono', Consolas, Menlo, monospace`

export interface LineExportMeta {
  /** 主标题：通道 / facet 名（如 "Pz"、"sub-01 · clench_fist · C3"） */
  title: string
  /** 副标题：数据集友好名 */
  subtitle?: string
  /** 右上类型徽标：ERP / Epochs / PSD … */
  badge?: string
  /** 页脚左栏：溯源指纹串（采样率 / 通道 / 时窗 / 滤波…，调用方已拼好） */
  footerLeft?: string
  /** 页脚右栏品牌（默认「念析 ELYS」） */
  brand?: string
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2))
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.arcTo(x + w, y, x + w, y + h, rr)
  ctx.arcTo(x + w, y + h, x, y + h, rr)
  ctx.arcTo(x, y + h, x, y, rr)
  ctx.arcTo(x, y, x + w, y, rr)
  ctx.closePath()
}

function hline(ctx: CanvasRenderingContext2D, x1: number, x2: number, y: number): void {
  ctx.beginPath()
  ctx.moveTo(x1, y)
  ctx.lineTo(x2, y)
  ctx.stroke()
}

/**
 * 把高清 chart canvas 合成进设计画框，返回最终可下载的 canvas。
 * 尺寸按 src 实宽等比缩放（mockup 以 ~1100 逻辑宽设计）；chart 1:1 贴入、不二次缩放。
 */
export function composeLineExport(src: HTMLCanvasElement, meta: LineExportMeta): HTMLCanvasElement {
  const k = Math.max(0.5, src.width / 1100)
  const r = (v: number) => Math.round(v * k)
  const padX = r(28)
  const titleY = r(18) + r(26)
  const subY = r(18) + r(48)
  const headDivY = r(18) + r(62)
  const gap = r(12)
  const chartY = headDivY + gap
  const footDivY = chartY + src.height + gap
  const footTextY = footDivY + r(28)
  const W = src.width + padX * 2
  const H = footTextY + r(20)

  const out = document.createElement('canvas')
  out.width = W
  out.height = H
  const ctx = out.getContext('2d')
  if (!ctx) return src // 极端：取不到 2d 上下文，退回无框 chart

  ctx.fillStyle = PAPER
  ctx.fillRect(0, 0, W, H)

  // 外框：1px 淡描边圆角，无阴影（沿用地形图「靠描边不靠投影」）
  ctx.strokeStyle = CARD_BORDER
  ctx.lineWidth = Math.max(1, r(1))
  roundRect(ctx, r(10), r(10), W - r(20), H - r(20), r(6))
  ctx.stroke()

  // 页眉：主标题 + 副标题（左对齐）
  ctx.textAlign = 'left'
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = C_TITLE
  ctx.font = `500 ${r(22)}px ${FONT_SANS}`
  ctx.fillText(meta.title || '', padX, titleY)
  if (meta.subtitle) {
    ctx.fillStyle = C_SUB
    ctx.font = `${r(14)}px ${FONT_SANS}`
    ctx.fillText(meta.subtitle, padX, subY)
  }
  // 类型徽标（右上药丸）
  if (meta.badge) {
    ctx.font = `500 ${r(13)}px ${FONT_MONO}`
    const bh = r(28)
    const bw = ctx.measureText(meta.badge).width + r(20)
    const bx = W - padX - bw
    const by = r(18) + r(10)
    ctx.fillStyle = BADGE_BG
    roundRect(ctx, bx, by, bw, bh, bh / 2)
    ctx.fill()
    ctx.fillStyle = C_PRIMARY
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(meta.badge, bx + bw / 2, by + bh / 2)
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
  }
  // 页眉分隔线
  ctx.strokeStyle = DIVIDER
  ctx.lineWidth = Math.max(1, r(1))
  hline(ctx, padX, W - padX, headDivY)

  // 绘图区：chart 本体 1:1 贴入（不缩放，保清晰）
  ctx.drawImage(src, padX, chartY)

  // 页脚分隔线 + 左溯源 + 右品牌·时间戳
  hline(ctx, padX, W - padX, footDivY)
  ctx.font = `${r(12)}px ${FONT_MONO}`
  if (meta.footerLeft) {
    ctx.fillStyle = C_SUB
    ctx.textAlign = 'left'
    ctx.fillText(meta.footerLeft, padX, footTextY)
  }
  const stamp = ' · ' + new Date().toLocaleString('zh-CN')
  ctx.textAlign = 'right'
  ctx.fillStyle = C_SUB
  ctx.fillText(stamp, W - padX, footTextY)
  const stampW = ctx.measureText(stamp).width
  ctx.fillStyle = C_PRIMARY
  ctx.fillText(meta.brand || '念析 ELYS', W - padX - stampW, footTextY)
  ctx.textAlign = 'left'

  return out
}

/** 触发浏览器下载 canvas 为 PNG。 */
export function triggerPngDownload(canvas: HTMLCanvasElement, filename: string): void {
  const a = document.createElement('a')
  a.href = canvas.toDataURL('image/png')
  a.download = filename
  a.click()
}

/** 导出文件名清洗：非「字母 / 数字 / 连字符」→ 下划线，去首尾下划线。 */
export function sanitizeExportName(s: string): string {
  return (s || 'plot').replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'plot'
}
