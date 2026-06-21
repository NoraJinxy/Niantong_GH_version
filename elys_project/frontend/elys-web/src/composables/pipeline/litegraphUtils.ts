// 工作流编辑器 · litegraph 画布纯工具（类型 + 节点 id 读写 + 图遍历 + 节点自绘原语）
//
// 从 PipelinePage.vue 抽出的「无状态」画布工具：不碰 Vue 响应式、不持有 liteGraph 实例，
// 全是「输入 graph/ctx/参数 → 输出」的纯函数。litegraph 实例的初始化/同步/CRUD 仍在主文件（画布核心）。

import { LGraph, LGraphNode, LiteGraph } from 'litegraph.js'
import type { NodeSpec } from '@/types'
import { LITEGRAPH_NODE_ID_PROP, LOAD_DATA_NODE_TYPE, NODE_CARD_WIDTH, NODE_CARD_MIN_HEIGHT } from './pipelineConstants'
import { formatJobStatus, nodeStatusColor, normalizedJobStatus } from './pipelineFormatters'

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

/** 标题栏右侧的运行状态徽标：状态圆点 + 中性灰文字。
 *  改自原「彩色药丸」——药丸的状态色（尤其成功的绿）会与节点类别色撞成第二个色系；降级为一颗小圆点后，
 *  整张卡只剩单一类别色系。成功/排队等常态用中性灰点（安静）；运行/等待用状态色点；失败用红点 + 红字（告警必须显眼）。 */
export function drawNodeStatusBadge(ctx: CanvasRenderingContext2D, width: number, status: string) {
  const label = formatJobStatus(status)
  const normalized = normalizedJobStatus(status)
  const titleHeight = LiteGraph.NODE_TITLE_HEIGHT
  const cy = -titleHeight / 2 // 标题栏（y<0）垂直居中
  const alarm = normalized === 'failed'
  const active = normalized === 'running' || normalized === 'waiting_user_input'
  const dotColor = alarm ? '#B42318' : active ? nodeStatusColor(status) : '#94A3B8'
  const labelColor = alarm ? '#B42318' : '#6B7785'

  ctx.save()
  ctx.font = '600 10px "Segoe UI", Arial, sans-serif'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  const rightX = width - 12 // 与事实行值右缘同列
  ctx.fillStyle = labelColor
  ctx.fillText(label, rightX, cy)
  const labelWidth = ctx.measureText(label).width
  ctx.beginPath()
  ctx.fillStyle = dotColor
  ctx.arc(rightX - labelWidth - 7, cy, 2.6, 0, Math.PI * 2)
  ctx.fill()
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
 * 工作流自动布局：把「多为线性、偶有末端分叉」的 DAG 排成「居中折行」网格——每行恒从左到右、各行个数均衡、整行水平居中。
 *
 * 为什么不用蛇形（boustrophedon）：litegraph 节点端口是固定的——输入永远在左、输出永远在右，
 * 数据天然向右流。蛇形让偶数行反向（右→左），那一行的节点「出口在右却要连左边的下一个节点」，
 * 连线整个往回兜，方向完全看不清（实测被用户打脸）。所以这里**每行都保持从左到右**：
 * 行尾换到下一行行首（像文字折行 / 打字机回车），每个节点的「出→入」方向恒定向右，一眼可辨流向。
 * 换行处那条「回扫线」（上行最右 → 下行最左）就像段落换行，人一看就懂。
 *
 * 分块：先按「连通分量」把节点分成若干互不连线的块——典型如 Group 分析里 S1 / S2 两条独立链。每块各自
 *   折行、整体居中、上下堆叠，块间留空隙。这样并行分支不会被「按层深排序」交错成一锅（S1 第一步紧挨 S2
 *   第一步……）。散落的未连线单节点汇成一块一起折行，免得一堆孤立节点排成一长竖列。单块（单连通图）时
 *   整体退化成原来的「居中折行」，行为不变。
 *
 * 排序规则（块内）：
 *   1) 算每个节点的「层深 depth」= 从任一根节点到它的最长路径长度（Kahn 拓扑排序 + 松弛）。
 *      这样节点一定排在其所有上游之后；末端 ERP/TFR/PSD 这类同层分叉会聚在一起。
 *   2) 同层按节点在原数组里的先后做稳定排序，块内展平成一条线性序列。
 *   3) 序列折行铺进网格，**每行一律左→右**（不反向）；折行方式见下「居中折行」。
 *
 * 折行（「居中折行」）——把旧的「左对齐打字机网格」收顺成自然居中：
 *   · 列数 cols 按画布宽高比挑：每块折成 ceil(size/cols) 行，令所有块堆叠后的总网格宽高比（cols·gapX :
 *     总行数·gapY）最接近画布，同分取更多列（偏好填满的宽行）。画布够宽时自然退化成单行顺流。
 *   · 每块内节点尽量均分到各行（行与行个数差 ≤1），杜绝「3-3-1」那种末行只剩一个的孤儿。
 *   · 每行水平居中（窄行落在最宽行正中），换行回扫线短而对称，不再是左对齐时那条横跨整行的长回扫。
 *   （调用方按节点实际宽高传 gapX/gapY，所以节点越高、行越少。）
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

  // —— 连通分量分块 —— 把无向连通的节点归到一「块」：每条独立链（如 S1 / S2 两条并行分支）各成一块，
  // 各自折行、整体居中、上下堆叠，不再被「按层深排序」交错打散成一锅。散落的未连线单节点汇成一块一起
  // 折行（沿用旧行为，免得一堆孤立节点被竖排成一列）。只有一块（单连通图）时整体退化成原「居中折行」。
  const parent = new Map<string, string>()
  for (const id of ids) parent.set(id, id)
  const find = (x: string): string => {
    let root = x
    while (parent.get(root) !== root) root = parent.get(root)!
    let cur = x
    while (parent.get(cur) !== root) {
      const nxt = parent.get(cur)!
      parent.set(cur, root) // 路径压缩
      cur = nxt
    }
    return root
  }
  for (const [from, kids] of children) {
    for (const to of kids) {
      const ra = find(from)
      const rb = find(to)
      if (ra !== rb) parent.set(ra, rb)
    }
  }

  const byDepthThenOrder = (a: string, b: string): number => {
    const da = depth.get(a) || 0
    const db = depth.get(b) || 0
    if (da !== db) return da - db
    return (orderIndex.get(a) || 0) - (orderIndex.get(b) || 0)
  }
  const minOrder = (members: string[]): number =>
    members.reduce((m, id) => Math.min(m, orderIndex.get(id) ?? 0), Infinity)

  const groups = new Map<string, string[]>()
  for (const id of ids) {
    const root = find(id)
    if (!groups.has(root)) groups.set(root, [])
    groups.get(root)!.push(id)
  }
  const blocks: string[][] = []
  const loose: string[] = []
  for (const members of groups.values()) {
    if (members.length >= 2) blocks.push(members.slice().sort(byDepthThenOrder))
    else loose.push(members[0])
  }
  if (loose.length) blocks.push(loose.sort(byDepthThenOrder))
  blocks.sort((a, b) => minOrder(a) - minOrder(b)) // 块的上下顺序按各自最小原始序，跟节点数组一致

  // 选「列数 cols」：每块折成 ceil(size/cols) 行，令所有块堆叠后的总网格宽高比最贴画布；同分取更多列
  //（总行更少 → 偏宽，画布够宽时单行顺流）。降序枚举 + 严格更优 ⇒ 同分保留更大 cols。单块时与原「按行数选」等价。
  const sizes = blocks.map((b) => b.length)
  const maxSize = Math.max(...sizes)
  let cols = 1
  let bestScore = Infinity
  for (let c = maxSize; c >= 1; c -= 1) {
    const totalRows = sizes.reduce((s, sz) => s + Math.ceil(sz / c), 0)
    const gridAspect = (c * gapX) / (totalRows * gapY)
    const score = Math.abs(Math.log(gridAspect / aspect))
    if (score < bestScore - 1e-9) {
      bestScore = score
      cols = c
    }
  }

  // 每块在 cols 约束下均分行（行间个数差 ≤1，杜绝「末行只剩一个」的孤儿）；所有行水平居中到同一中线、
  // 上下堆叠，块与块之间留一道空隙以示「这是另一条链」。
  const blockRowSizes = blocks.map((members) => {
    const rows = Math.max(1, Math.ceil(members.length / cols))
    const base = Math.floor(members.length / rows)
    const extra = members.length % rows
    return Array.from({ length: rows }, (_, r) => base + (r < extra ? 1 : 0))
  })
  const globalMaxCols = Math.max(...blockRowSizes.map((rs) => rs[0]))
  const centerX = marginX + ((globalMaxCols - 1) * gapX) / 2
  const blockGapY = blocks.length > 1 ? Math.round(gapY * 0.4) : 0

  let y = marginY
  blocks.forEach((members, bi) => {
    let idx = 0
    for (const size of blockRowSizes[bi]) {
      const rowStartX = centerX - ((size - 1) * gapX) / 2 // 本行整体居中
      for (let c = 0; c < size; c += 1) {
        layout.set(members[idx], [Math.round(rowStartX + c * gapX), Math.round(y)])
        idx += 1
      }
      y += gapY
    }
    if (bi < blocks.length - 1) y += blockGapY
  })

  return layout
}
