// 工作流编辑器 · litegraph 画布纯工具（类型 + 节点 id 读写 + 图遍历 + 节点自绘原语）
//
// 从 PipelinePage.vue 抽出的「无状态」画布工具：不碰 Vue 响应式、不持有 liteGraph 实例，
// 全是「输入 graph/ctx/参数 → 输出」的纯函数。litegraph 实例的初始化/同步/CRUD 仍在主文件（画布核心）。

import { LGraph, LGraphNode, LiteGraph } from 'litegraph.js'
import type { NodeSpec } from '@/types'
import { LITEGRAPH_NODE_ID_PROP, LOAD_DATA_NODE_TYPE, NODE_CARD_WIDTH, NODE_CARD_MIN_HEIGHT } from './pipelineConstants'
import { formatJobStatus, nodeStatusColor, nodeStatusSoftColor, withAlpha } from './pipelineFormatters'

export type LiteGraphNode = LGraphNode & {
  elysNodeId?: string
  constructor?: typeof LGraphNode & { title?: string; desc?: string }
}

export type LooseLiteGraph = Record<string, any> & {
  _nodes?: LiteGraphNode[]
  _version?: number
  onAfterChange?: () => void
  onConnectionChange?: () => void
  onNodeRemoved?: () => void
}

export type LiteGraphLink = {
  id?: number | string
  origin_id: number
  origin_slot: number
  target_id: number
  target_slot: number
}

/** 取节点的 elys 业务 id（优先 elysNodeId，回退 properties 里的副本，再回退 litegraph 内部数字 id）。 */
export function getLiteGraphNodeId(node: LiteGraphNode | LGraphNode | null | undefined) {
  const liteNode = node as LiteGraphNode | null | undefined
  const fromProperty = liteNode?.properties?.[LITEGRAPH_NODE_ID_PROP]
  return String(liteNode?.elysNodeId || fromProperty || liteNode?.id || '')
}

/** 把 elys 业务 id 写到节点（同时存 elysNodeId 快捷字段 + properties 持久副本）。 */
export function setLiteGraphNodeId(node: LiteGraphNode, id: string) {
  node.elysNodeId = id
  node.properties = {
    ...(node.properties || {}),
    [LITEGRAPH_NODE_ID_PROP]: id,
  }
}

/** 取 litegraph 图里的全部节点（读内部 _nodes，做了 null/类型兜底）。 */
export function liteGraphNodes(graph: LGraph | null | undefined): LiteGraphNode[] {
  return ((graph as unknown as LooseLiteGraph | null | undefined)?._nodes || []) as LiteGraphNode[]
}

/** 从 LiteGraph 自身 link 结构出发，BFS 找出"从某个 LoadData 节点可顺流到达"的所有节点 elysNodeId 集合。
 *  用于画布"保存指示胶囊"判定：节点必须通过 input 链路一路追溯到 LoadData，才认为可达。
 *
 *  关键：直接读 LiteGraph 的 outputs[].links + liteGraph.links（不依赖 Vue 响应式 definition.value.graph，
 *  避免新节点拖入后 graph 还没 sync 的时序问题——task #65 的修复留下的盲区是只看了"自己有 input link"）。
 */
export function liteGraphReachableFromLoadData(graph: LGraph | null | undefined): Set<string> {
  const reachable = new Set<string>()
  if (!graph) return reachable
  const allNodes = liteGraphNodes(graph)
  const links = ((graph as unknown as { links?: Record<string, LiteGraphLink> })?.links) || {}

  // 用 LiteGraph 内部 numeric id 走 BFS（link.target_id 是 numeric）
  const visitedInternal = new Set<number>()
  const queue: number[] = []
  for (const n of allNodes) {
    const type = String((n as { type?: unknown }).type || '')
    if (type !== LOAD_DATA_NODE_TYPE) continue
    const internalId = (n as unknown as { id?: number }).id
    const elysId = getLiteGraphNodeId(n)
    if (typeof internalId !== 'number' || !elysId) continue
    if (visitedInternal.has(internalId)) continue
    visitedInternal.add(internalId)
    reachable.add(elysId)
    queue.push(internalId)
  }

  const getNodeById = (graph as unknown as { getNodeById?: (id: number) => LiteGraphNode | null }).getNodeById?.bind(graph)
  if (!getNodeById) return reachable

  while (queue.length) {
    const curId = queue.shift() as number
    const cur = getNodeById(curId)
    if (!cur) continue
    const outputs = (cur as unknown as { outputs?: Array<{ links?: unknown } | null> }).outputs || []
    for (const out of outputs) {
      const outLinks = out?.links
      if (!Array.isArray(outLinks)) continue
      for (const linkId of outLinks as unknown[]) {
        if (typeof linkId !== 'number') continue
        const link = links[String(linkId) as keyof typeof links] || (links as unknown as Record<number, LiteGraphLink>)[linkId]
        if (!link || typeof link.target_id !== 'number') continue
        if (visitedInternal.has(link.target_id)) continue
        visitedInternal.add(link.target_id)
        const targetNode = getNodeById(link.target_id)
        if (targetNode) {
          const targetElysId = getLiteGraphNodeId(targetNode)
          if (targetElysId) reachable.add(targetElysId)
        }
        queue.push(link.target_id)
      }
    }
  }
  return reachable
}

/** 节点左侧 4px 的 accent 竖条（category 颜色），裁剪到与节点边框一致的圆角内。
 *  注意 roundRect 的半径要和 onDrawForeground 边框完全一致（原点 0.5、半径 6），否则圆弧对不上。
 */
export function drawNodeAccentBar(
  ctx: CanvasRenderingContext2D,
  color: string,
  width: number,
  bodyHeight: number,
  titleHeight: number,
) {
  const fullHeight = bodyHeight + titleHeight
  ctx.save()
  ctx.beginPath()
  // 与 onDrawForeground 里节点边框完全一致的圆角路径（原点 0.5、半径 6）
  ctx.roundRect(0.5, -titleHeight + 0.5, width, fullHeight, [6])
  ctx.clip()
  ctx.fillStyle = color
  ctx.fillRect(0, -titleHeight, 4, fullHeight)
  ctx.restore()
}

/** 标题栏右侧的运行状态徽标胶囊（运行中/完成/失败…），颜色取 nodeStatusColor 家族。 */
export function drawNodeStatusBadge(ctx: CanvasRenderingContext2D, width: number, status: string) {
  const label = formatJobStatus(status)
  const titleHeight = LiteGraph.NODE_TITLE_HEIGHT
  const badgeHeight = 18
  ctx.save()
  ctx.font = '600 10px "Segoe UI", Arial, sans-serif'
  const textWidth = ctx.measureText(label).width
  const badgeWidth = Math.max(40, textWidth + 14)
  const x = Math.max(10, width - badgeWidth - 8)
  // 标题栏内（y < 0），上下居中：badge 高 18，标题栏高 titleHeight，居中 -titleHeight + (titleHeight - 18)/2
  const y = -titleHeight + (titleHeight - badgeHeight) / 2
  ctx.fillStyle = nodeStatusSoftColor(status)
  ctx.strokeStyle = withAlpha(nodeStatusColor(status), 0.42)
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.roundRect(x, y, badgeWidth, badgeHeight, [badgeHeight / 2])
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = nodeStatusColor(status)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(label, x + badgeWidth / 2, y + badgeHeight / 2)
  ctx.restore()
}

/**
 * 在节点底部画一个"保留"指示胶囊 —— 颜色取节点自己的 spec.ui.color。
 *
 * 设计参考: mockup_save_indicator.html 变体 6（圆角胶囊色块）。
 * 形状: 距左右各 14px、距底 3px、高 4px 的圆角矩形（圆角半径 = 高度的一半 → 完全胶囊形）。
 *
 * 概念：节点产物只有"保留"一种状态。color 传 null 表示不画
 * （不可达节点 / 用户选择 retention=cached/none / intermediate 默认）。
 */
export function drawNodeSaveIcon(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  color: string | null,
) {
  if (!color) return

  const padX = 14
  const barH = 4
  const marginBottom = 3
  const x = padX
  const y = height - barH - marginBottom
  const w = Math.max(0, width - padX * 2)
  if (w <= 0) return

  ctx.save()
  ctx.fillStyle = color
  ctx.beginPath()
  if (typeof (ctx as unknown as { roundRect?: unknown }).roundRect === 'function') {
    ctx.roundRect(x, y, w, barH, [barH / 2])
  } else {
    ctx.rect(x, y, w, barH)
  }
  ctx.fill()
  ctx.restore()
}

/** 节点卡片尺寸：优先 spec.ui.default_size/size，否则按端口行数估算（最小宽高兜底）。 */
export function graphNodeSize(spec: NodeSpec): [number, number] {
  const uiSize = spec.ui?.default_size || spec.ui?.size
  if (Array.isArray(uiSize) && uiSize.length >= 2) {
    const width = Number(uiSize[0])
    const height = Number(uiSize[1])
    if (Number.isFinite(width) && Number.isFinite(height)) return [Math.max(NODE_CARD_WIDTH, width), Math.max(NODE_CARD_MIN_HEIGHT, height)]
  }
  const portRows = Math.max(spec.inputs?.length || 0, spec.outputs?.length || 0)
  return [NODE_CARD_WIDTH, Math.max(NODE_CARD_MIN_HEIGHT, 78 + portRows * 26)]
}

/**
 * 工作流自动布局：把「多为线性、偶有末端分叉」的 DAG 排成「打字机式」折行网格（每行恒从左到右）。
 *
 * 为什么不用蛇形（boustrophedon）：litegraph 节点端口是固定的——输入永远在左、输出永远在右，
 * 数据天然向右流。蛇形让偶数行反向（右→左），那一行的节点「出口在右却要连左边的下一个节点」，
 * 连线整个往回兜，方向完全看不清（实测被用户打脸）。所以这里**每行都保持从左到右**：
 * 行尾换到下一行行首（像文字折行 / 打字机回车），每个节点的「出→入」方向恒定向右，一眼可辨流向。
 * 换行处那条「回扫线」（上行最右 → 下行最左）就像段落换行，人一看就懂。
 *
 * 排序规则：
 *   1) 算每个节点的「层深 depth」= 从任一根节点到它的最长路径长度（Kahn 拓扑排序 + 松弛）。
 *      这样节点一定排在其所有上游之后；末端 ERP/TFR/PSD 这类同层分叉会聚在一起。
 *   2) 同层按节点在原数组里的先后做稳定排序，最终展平成一条线性序列。
 *   3) 序列按列数 cols 折行铺进网格，**每行一律左→右**（不反向）。
 *
 * 列数 cols 按画布宽高比 aspect 自适应：让网格宽高比 ≈ 画布宽高比，fit（缩放到全部可见）后最舒服。
 *   推导：网格宽 = cols·gapX，网格高 ≈ (n/cols)·gapY；令 宽/高 = aspect
 *        → cols² = aspect·n·gapY/gapX → cols = √(aspect·n·gapY/gapX)。
 *   （调用方按节点实际宽高传 gapX/gapY，所以节点越高 cols 越多、行数越少、回扫线越少。）
 *
 * @returns 节点 id → [x, y] 画布坐标的 Map；空图返回空 Map。（DAG 应无环；万一有环，环上节点 depth 取 0 兜底。）
 */
export function computeFlowLayout(
  nodes: Array<{ id: string }>,
  links: Array<{ from?: { node?: string } | null; to?: { node?: string } | null } | null> | null | undefined,
  opts: { gapX: number; gapY: number; aspect: number; marginX?: number; marginY?: number },
): Map<string, [number, number]> {
  const layout = new Map<string, [number, number]>()
  const n = nodes.length
  if (n === 0) return layout

  const { gapX, gapY } = opts
  const aspect = opts.aspect > 0 ? opts.aspect : 1.6
  const marginX = opts.marginX ?? 80
  const marginY = opts.marginY ?? 80

  const orderIndex = new Map<string, number>()
  nodes.forEach((node, i) => orderIndex.set(node.id, i))
  const ids = new Set(nodes.map((node) => node.id))

  const children = new Map<string, string[]>()
  const indeg = new Map<string, number>()
  for (const id of ids) {
    children.set(id, [])
    indeg.set(id, 0)
  }
  for (const link of links || []) {
    const from = link?.from?.node
    const to = link?.to?.node
    if (!from || !to || from === to || !ids.has(from) || !ids.has(to)) continue
    children.get(from)!.push(to)
    indeg.set(to, (indeg.get(to) || 0) + 1)
  }

  // Kahn 拓扑 + 最长路径层深；入队按原始顺序，保持同层稳定
  const depth = new Map<string, number>()
  for (const id of ids) depth.set(id, 0)
  const queue = nodes.filter((node) => (indeg.get(node.id) || 0) === 0).map((node) => node.id)
  while (queue.length) {
    const cur = queue.shift() as string
    const curDepth = depth.get(cur) || 0
    for (const next of children.get(cur) || []) {
      if (curDepth + 1 > (depth.get(next) || 0)) depth.set(next, curDepth + 1)
      indeg.set(next, (indeg.get(next) || 0) - 1)
      if ((indeg.get(next) || 0) === 0) queue.push(next)
    }
  }

  const sequence = [...ids].sort((a, b) => {
    const da = depth.get(a) || 0
    const db = depth.get(b) || 0
    if (da !== db) return da - db
    return (orderIndex.get(a) || 0) - (orderIndex.get(b) || 0)
  })

  let cols = Math.round(Math.sqrt((aspect * n * gapY) / gapX))
  cols = Math.max(2, Math.min(n, cols))

  sequence.forEach((id, i) => {
    const row = Math.floor(i / cols)
    const col = i % cols // 打字机式：每行一律左→右，不反向（保持流向可读）
    layout.set(id, [marginX + col * gapX, marginY + row * gapY])
  })

  return layout
}
