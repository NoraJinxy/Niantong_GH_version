// 工作流编辑器 · litegraph 画布纯工具（类型 + 节点 id 读写 + 图遍历 + 节点自绘原语）
//
// 从 PipelinePage.vue 抽出的「无状态」画布工具：不碰 Vue 响应式、不持有 liteGraph 实例，
// 全是「输入 graph/ctx/参数 → 输出」的纯函数。litegraph 实例的初始化/同步/CRUD 仍在主文件（画布核心）。

import { LGraph, LGraphNode, LiteGraph } from 'litegraph.js'
import { LITEGRAPH_NODE_ID_PROP, LOAD_DATA_NODE_TYPE } from './pipelineConstants'
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
