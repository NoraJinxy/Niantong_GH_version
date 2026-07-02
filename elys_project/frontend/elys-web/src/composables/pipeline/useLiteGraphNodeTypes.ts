// 工作流编辑器 · litegraph 节点类型注册 + 节点自绘类（ElysPipelineNode）
//
// 从 PipelinePage.vue 抽出：为每个 NodeSpec 动态生成一个 LGraphNode 子类（端口 + 标题栏/编号圆/前景自绘），
// 注册到 litegraph。自绘里的运行状态徽标 / 保存指示胶囊依赖运行态与 liteGraph 实例，经 options 注入（getter）。
// 依赖承重墙 nodeSpecs + 运行态查询 jobForNodeId + liteGraph 实例 getter + 默认参数 defaultParams（均注入）。
// registerLiteGraphNodeSpecs 返回给主文件，被 createLiteGraphNode / initLiteGraphCanvas（画布核心仍在主文件）调用。

import { type Ref } from 'vue'
import { LGraph, LGraphNode, LiteGraph } from 'litegraph.js'
import type { NodeSpec } from '@/types'
import {
  categoryColor,
  categorySoftColor,
  portTypeColor,
  compactNodeTitle,
  liteGraphPortType,
  withAlpha,
} from './pipelineFormatters'
import { NO_SAVE_ICON_NODE_TYPES } from './pipelineConstants'
import {
  drawNodeAccentBar,
  drawNodeStatusBadge,
  drawNodeSaveIcon,
  getLiteGraphNodeId,
  liteGraphReachableFromLoadData,
  graphNodeSize,
  type LiteGraphNode,
} from './litegraphUtils'
import { allowsMultipleInputLinks, liteGraphInputPorts } from './dynamicPorts'

// node type 经 LiteGraph.registerNodeType 全局注册、进程内只注册一次：其自绘（onDrawForeground）闭包会永久
// 指向「首次挂载」那次 useLiteGraphNodeTypes 的运行态实例。从 /artifact /ica 这类顶级路由重挂返回后，
// PipelinePage 整个换了新实例（新 useRunExecution → 新 executionJobByNodeId），但全局旧类的自绘闭包仍读旧
// 实例——旧实例停在导航前的 waiting_user_input → 徽标永远卡「等待确认」，而节点框颜色走当前实例已是新态，
// 同一节点两处对不上（0fd4122 修了数据重载，没修「自绘读旧闭包」这条路，故症状复发）。
// 解法：自绘不读构造期闭包，改读这两个模块级「当前挂载」转发器；每次 useLiteGraphNodeTypes()（= 每次 setup）
// 更新成当前实例的取值器，自绘每帧读它即永远拿到当前 PipelinePage 的实时运行态 / 图实例。
let activeJobForNodeId: (nodeId: string) => { status: string } | null = () => null
let activeGetLiteGraph: () => LGraph | null = () => null

// onDrawForeground 每帧、每个节点都要判「能否从某 LoadData 顺流到达」（保存指示胶囊）。直接每次跑 BFS =
// O(N²·fps)，节点一多画布帧率就塌。改成按图拓扑缓存：LiteGraph 实例在每次连线/增删节点时都会自增 _version
// （见 litegraph.js connect/disconnect/add/remove），故拿 (图实例, _version) 当签名——签名没变就复用上次的
// 可达集，只在拓扑真的变了才重算一次。draw 循环只读缓存，绝不在帧里跑 BFS。
let cachedReachableGraph: LGraph | null = null
let cachedReachableVersion = -1
let cachedReachableSet = new Set<string>()

function reachableFromLoadDataCached(graph: LGraph | null): Set<string> {
  if (!graph) return new Set<string>()
  const version = Number((graph as unknown as { _version?: number })._version ?? -1)
  if (graph === cachedReachableGraph && version === cachedReachableVersion) {
    return cachedReachableSet
  }
  cachedReachableGraph = graph
  cachedReachableVersion = version
  cachedReachableSet = liteGraphReachableFromLoadData(graph)
  return cachedReachableSet
}

type ElysPipelineNodeConstructor = typeof LGraphNode & { desc?: string }

interface LiteGraphNodeTypesOptions {
  nodeSpecs: Ref<NodeSpec[]>
  jobForNodeId: (nodeId: string) => { status: string } | null
  getLiteGraph: () => LGraph | null
  defaultParams: (spec: NodeSpec) => Record<string, unknown>
}

export function useLiteGraphNodeTypes(options: LiteGraphNodeTypesOptions) {
  const { nodeSpecs, jobForNodeId, getLiteGraph, defaultParams } = options
  // 关键：把「当前挂载」的运行态 / 图取值器登记到模块级转发器（见上）。全局注册的节点自绘只认这两个转发器，
  // 不认构造期闭包——否则从 /artifact /ica 重挂返回后，徽标会卡在首挂旧实例的「等待确认」。
  activeJobForNodeId = jobForNodeId
  activeGetLiteGraph = getLiteGraph

  const registeredLiteGraphTypes = new Set<string>()

  function registerLiteGraphNodeSpecs() {
    for (const spec of nodeSpecs.value) {
      if (registeredLiteGraphTypes.has(spec.type)) continue
      if ((LiteGraph as unknown as { registered_node_types?: Record<string, unknown> }).registered_node_types?.[spec.type]) {
        registeredLiteGraphTypes.add(spec.type)
        continue
      }

      const accent = categoryColor(spec.category)
      const softAccent = categorySoftColor(spec.category)
      class ElysPipelineNode extends LGraphNode {
        constructor() {
          super(spec.title)
          this.title = spec.title
          this.properties = defaultParams(spec)
          this.size = graphNodeSize(spec)
          this.color = '#D4DDE8'
          this.boxcolor = accent
          this.bgcolor = '#FFFFFF'
          this.shape = LiteGraph.ROUND_SHAPE
          this.resizable = true
          for (const input of liteGraphInputPorts(spec)) {
            const color = portTypeColor(input.type)
            this.addInput(input.name, liteGraphPortType(input.type), {
              label: input.label || input.name,
              color_on: color,
              color_off: withAlpha(color, 0.36),
              shape: LiteGraph.CIRCLE_SHAPE,
            })
            const slot = (this as unknown as { inputs?: Array<{ cardinality?: string | null }> })
              .inputs?.[(this.inputs?.length || 1) - 1]
            if (slot) slot.cardinality = input.cardinality || null
          }
          for (const output of spec.outputs || []) {
            const color = portTypeColor(output.type)
            this.addOutput(output.name, liteGraphPortType(output.type), {
              label: output.label || output.name,
              color_on: color,
              color_off: withAlpha(color, 0.36),
              shape: LiteGraph.CIRCLE_SHAPE,
            })
          }
        }

        getTitle() {
          return compactNodeTitle(String(this.title || spec.title || spec.type || 'Node'))
        }

        onConnectInput(targetSlot: number) {
          const input = (this as unknown as {
            inputs?: Array<{ cardinality?: string | null; link?: unknown; links?: unknown[] }>
          }).inputs?.[targetSlot]
          const specInput = liteGraphInputPorts(spec)[targetSlot] || null
          if (allowsMultipleInputLinks(spec, specInput)) {
            // LiteGraph outputs use output.links[] for one-to-many. Group Merge
            // mirrors that shape on its input while keeping native input.link
            // empty so new upstreams never replace the previous one.
            if (input && !Array.isArray(input.links)) input.links = []
            input.link = null
          }
          return true
        }

        onDrawTitleBar(ctx: CanvasRenderingContext2D, titleHeight: number, size: [number, number]) {
          // 标题栏顶部 14px 一缕类别淡色竖向晕染到白（左右对称、不留灰端色），保持整卡单一色系。
          const gradient = ctx.createLinearGradient(0, -titleHeight, 0, -titleHeight + 14)
          gradient.addColorStop(0, softAccent)
          gradient.addColorStop(1, '#FFFFFF')
          ctx.fillStyle = gradient
          ctx.beginPath()
          ctx.roundRect(0, -titleHeight, size[0] + 1, titleHeight, [6, 6, 0, 0])
          ctx.fill()

          drawNodeAccentBar(ctx, accent, size[0], size[1], titleHeight)

          ctx.strokeStyle = '#D9E0EA'
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(0, -0.5)
          ctx.lineTo(size[0], -0.5)
          ctx.stroke()
        }

        onDrawTitleBox(ctx: CanvasRenderingContext2D, titleHeight: number) {
          // 单颗实心类别圆点（去掉原「白底 + 0.42 描边圈 + 内点」的牛眼）——与右侧状态圆点
          // 形成「点·标题·点」的对称呼应，靠重复而非装饰出风格，且少一道 withAlpha 半透明描边、HiDPI 更利。
          const x = titleHeight * 0.5 - 1
          const y = -titleHeight * 0.5
          ctx.fillStyle = accent
          ctx.beginPath()
          ctx.arc(x, y, 3.2, 0, Math.PI * 2)
          ctx.fill()
        }

        onDrawBackground(ctx: CanvasRenderingContext2D) {
          const node = this as unknown as LiteGraphNode
          const [width, height] = node.size as [number, number]
          ctx.fillStyle = '#FFFFFF'
          ctx.fillRect(4, 0, width - 4, height)

          ctx.fillStyle = 'rgba(248, 250, 252, 0.92)'
          ctx.fillRect(4, 0, width - 4, 1)
        }

        onDrawForeground(ctx: CanvasRenderingContext2D) {
          const node = this as unknown as LiteGraphNode
          const [width, height] = node.size as [number, number]
          const titleHeight = LiteGraph.NODE_TITLE_HEIGHT
          const selected = Boolean(node.is_selected)
          const hovered = Boolean(node.mouseOver)

          ctx.save()
          // 选中 = 边框直接转 accent 1.5px（去掉原来那圈 3px 半透明模糊光晕）——全卡都是 HiDPI 发丝线
          // 与扁平填充，模糊光晕是唯一不锐利的元素、与临床工具的精密感相悖；一条更实的描边更静更利。
          ctx.strokeStyle = selected ? accent : hovered ? withAlpha(accent, 0.72) : '#D4DDE8'
          ctx.lineWidth = selected ? 1.5 : hovered ? 1.25 : 1
          ctx.beginPath()
          ctx.roundRect(0.5, -titleHeight + 0.5, width, height + titleHeight, [6])
          ctx.stroke()

          if (selected || hovered) {
            drawNodeAccentBar(ctx, selected ? accent : withAlpha(accent, 0.72), width, height, titleHeight)
          }

          const nodeId = getLiteGraphNodeId(node)
          // 运行状态徽标：走模块级转发器拿「当前挂载」的运行态，绝不读构造期闭包 jobForNodeId
          //（全局注册一次，闭包冻在首挂实例 → 重挂返回后会卡「等待确认」，详见文件顶部注释）。
          const job = activeJobForNodeId(nodeId)
          if (job) drawNodeStatusBadge(ctx, width, job.status)

          // 保存状态指示胶囊：直接看 LiteGraph 实际链接，不依赖 definition.value.graph（避开 sync 时序问题）。
          //
          // 规则：
          // - LoadData 等 source 节点 → 不画（在 NO_SAVE_ICON_NODE_TYPES 里）
          // - 必须能从某个 LoadData 节点顺流走到本节点（BFS 可达） —— 即使本节点有 input link，
          //   但若其上游链路没接 LoadData，也不画。这是 task #71 的核心修复（task #65 漏判）。
          // - 节点 outputs 全部未连接 → leaf → 画（默认 retention='current'）
          // - 节点有 output 连接 → intermediate → 不画（默认 cached）
          // - 用户在 params 里显式设了 retention：
          //     'current' / 'pinned' → 强制画（仅当可达）
          //     'cached' / 'none'    → 强制不画
          //     其它/留空            → 走拓扑默认
          // - 颜色用 closure 里的 accent（= categoryColor(spec.category)）
          const nodeType = String((node as { type?: unknown }).type || '')
          if (nodeType && !NO_SAVE_ICON_NODE_TYPES.has(nodeType)) {
            // 先用 BFS 判 LoadData 可达性 —— 不可达就一定不画（用户 override 也无效）。
            // 走按拓扑缓存的版本（见文件顶部 reachableFromLoadDataCached）：每帧每节点重跑 BFS 会塌帧率，
            // 这里只在 (图实例, _version) 变了才真算，否则复用缓存。
            const reachableSet = reachableFromLoadDataCached(activeGetLiteGraph())
            if (reachableSet.has(nodeId)) {
              const params = (node.properties || {}) as Record<string, unknown>
              const override = String((params.retention as string | undefined) || '').trim().toLowerCase()

              let shouldDraw = false
              if (override === 'current' || override === 'pinned') {
                shouldDraw = true
              } else if (override === 'cached' || override === 'none') {
                shouldDraw = false
              } else {
                // 拓扑默认：可达 + 是 leaf（无 output 连接）
                const outputs = (node as unknown as { outputs?: Array<{ links?: unknown } | null> }).outputs || []
                const isLeaf = !outputs.some((o) => Array.isArray(o?.links) && (o.links as unknown[]).length > 0)
                shouldDraw = isLeaf
              }

              if (shouldDraw) {
                drawNodeSaveIcon(ctx, width, height, accent)
              }
            }
          }
          ctx.restore()
        }
      }

      const nodeConstructor = ElysPipelineNode as ElysPipelineNodeConstructor
      nodeConstructor.title = spec.title
      nodeConstructor.desc = spec.description || spec.title
      ;(ElysPipelineNode as unknown as Record<string, unknown>).title_color = softAccent
      ;(ElysPipelineNode as unknown as Record<string, unknown>).title_text_color = '#1F2A37'
      ;(ElysPipelineNode as unknown as Record<string, unknown>).bgcolor = '#FFFFFF'
      ;(ElysPipelineNode as unknown as Record<string, unknown>).color = '#D4DDE8'
      LiteGraph.registerNodeType(spec.type, ElysPipelineNode)
      registeredLiteGraphTypes.add(spec.type)
    }
  }

  return { registerLiteGraphNodeSpecs }
}
