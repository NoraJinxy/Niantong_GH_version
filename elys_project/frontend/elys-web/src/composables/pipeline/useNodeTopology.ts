// 工作流编辑器 · 节点拓扑与保留（检查器底部 keep checkbox + 拓扑角色判定）
//
// 从 PipelinePage.vue 抽出：
//   - reachableNodeIds：从所有 LoadData 出发 BFS 标记"上游可达数据源"的节点（孤立节点谈不上保留产物）；
//   - isLeafNode：输出端口未被任何 link 引用 → 叶子（最终产出，强制保留）；
//   - topologyLabel：leaf / intermediate / detached（未连数据源）；
//   - keep checkbox 据此禁用/强制。
// 依赖承重墙 selectedNode / definition + 画布 updateLiteGraphNode + 保存 markDirty。

import { computed, type Ref, type ComputedRef } from 'vue'
import type { PipelineGraphNode, PipelineDefinitionPayload } from '@/types'
import { LOAD_DATA_NODE_TYPE } from './pipelineConstants'

interface NodeTopologyOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  definition: Ref<PipelineDefinitionPayload>
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useNodeTopology(options: NodeTopologyOptions) {
  const { selectedNode, definition, updateLiteGraphNode, markDirty } = options

  /**
   * 从所有 LoadData 节点出发 BFS，标记所有"上游可达 LoadData"的节点 id。
   * 用于画布保留指示：只有可达节点才谈得上"保留产物"，孤立节点（拖出但没连数据源）不画。
   */
  const reachableNodeIds = computed<Set<string>>(() => {
    const reachable = new Set<string>()
    const nodes = definition.value.graph.nodes
    const links = definition.value.graph.links || []
    const queue: string[] = []
    for (const n of nodes) {
      if (n.type === LOAD_DATA_NODE_TYPE) {
        reachable.add(n.id)
        queue.push(n.id)
      }
    }
    if (queue.length === 0) return reachable
    const downstreamByFrom: Record<string, string[]> = {}
    for (const link of links) {
      const from = link.from?.node
      const to = link.to?.node
      if (typeof from === 'string' && typeof to === 'string') {
        if (!downstreamByFrom[from]) downstreamByFrom[from] = []
        downstreamByFrom[from].push(to)
      }
    }
    while (queue.length) {
      const cur = queue.shift() as string
      const next = downstreamByFrom[cur] || []
      for (const id of next) {
        if (!reachable.has(id)) {
          reachable.add(id)
          queue.push(id)
        }
      }
    }
    return reachable
  })

  /** 拓扑角色：节点的输出端口在 graph.links 中出现 → intermediate，否则 leaf。
   *  source 节点（LoadData）在这套 UI 中无 save 子对象不会渲染折叠区，不需要单独处理。
   */
  const isLeafNode = computed<boolean>(() => {
    const node = selectedNode.value
    if (!node) return true
    const links = definition.value.graph.links || []
    return !links.some((link) => link.from?.node === node.id)
  })

  /** 叶子节点（最终输出）强制保留的提示文案。 */
  const keepLeafHint = '最终结果默认保存；不需要请直接删除该节点'

  /** 当前选中节点是否保留输出。
   *  叶子节点（最终产出）强制保留；中间节点取 params.keep override，默认不保留。 */
  const selectedNodeKeep = computed<boolean>(() => {
    if (isLeafNode.value) return true
    const override = selectedNode.value?.params?.keep
    if (typeof override === 'boolean') return override
    if (override === 'true') return true
    if (override === 'false') return false
    return false
  })

  /** 节点拓扑前缀（leaf / intermediate / detached）。 */
  const topologyLabel = computed<string>(() => {
    const node = selectedNode.value
    if (!node) return ''
    if (!reachableNodeIds.value.has(node.id)) return 'detached'
    return isLeafNode.value ? 'leaf' : 'intermediate'
  })

  /** keep checkbox 是否禁用：叶子节点强制保留、或未连数据源不产出。 */
  const keepCheckboxDisabled = computed<boolean>(() => isLeafNode.value || topologyLabel.value === 'detached')

  function onToggleKeep(event: Event) {
    const node = selectedNode.value
    if (!node || keepCheckboxDisabled.value) return
    const checked = (event.target as HTMLInputElement).checked
    node.params = { ...node.params, keep: checked }
    updateLiteGraphNode(node)
    markDirty()
  }

  return {
    reachableNodeIds,
    isLeafNode,
    keepLeafHint,
    selectedNodeKeep,
    topologyLabel,
    keepCheckboxDisabled,
    onToggleKeep,
  }
}
