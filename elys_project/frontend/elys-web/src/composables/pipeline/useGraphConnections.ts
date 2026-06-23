// 工作流编辑器 · 节点连接管理（检查器右侧的连接列表 + 上游候选 + 快连/断连）
//
// 从 PipelinePage.vue 抽出：
//   - selectedNodeInputLinks：当前节点的入链列表；
//   - connectableUpstreamCandidates：可连的上游候选（按 0 号 input 端口类型兼容、排除已连）；
//   - connectUpstreamToSelected：优先在 litegraph 画布上连（有 graphNode 时），否则直接改 definition.links。
// 画布同步函数（findLiteGraphNode/syncDefinitionFrom/ToLiteGraph）由主文件注入（画布核心仍在主文件）。
// 依赖承重墙 selectedNode/selectedNodeSpec/definition/specForNode/statusMessage + 注入的画布同步 + markDirty。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { LGraphNode } from 'litegraph.js'
import type { PipelineGraphNode, NodeSpec, PipelineDefinitionPayload } from '@/types'
import { portTypesCompatible } from './pipelineFormatters'

let linkIdCounter = 0

function generateLinkId(): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  if (uuid) return `l_${uuid}`
  linkIdCounter += 1
  return `l_${Date.now().toString(36)}_${linkIdCounter}`
}

interface GraphConnectionsOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  selectedNodeSpec: ComputedRef<NodeSpec | null>
  definition: Ref<PipelineDefinitionPayload>
  statusMessage: Ref<string>
  specForNode: (node: PipelineGraphNode | null | undefined) => NodeSpec | null
  markDirty: () => void
  findLiteGraphNode: (nodeId: string) => LGraphNode | null
  syncDefinitionFromLiteGraph: (markAsDirty?: boolean) => void
  syncDefinitionToLiteGraph: () => void
}

export function useGraphConnections(options: GraphConnectionsOptions) {
  const {
    selectedNode,
    selectedNodeSpec,
    definition,
    statusMessage,
    specForNode,
    markDirty,
    findLiteGraphNode,
    syncDefinitionFromLiteGraph,
    syncDefinitionToLiteGraph,
  } = options

  const upstreamNodeId = ref('')

  const selectedNodeInputLinks = computed(() => {
    if (!selectedNode.value) return []
    return definition.value.graph.links.filter((link) => link.to.node === selectedNode.value?.id)
  })

  const connectableUpstreamCandidates = computed(() => {
    if (!selectedNode.value || !selectedNodeSpec.value) return []
    const targetInput = selectedNodeSpec.value.inputs?.[0]
    if (!targetInput) return []
    const alreadyConnected = new Set(
      selectedNodeInputLinks.value.map((link) => link.from.node),
    )
    const candidates: Array<{
      node: PipelineGraphNode
      label: string
      outputType: string
      tooltip: string
    }> = []
    for (const node of definition.value.graph.nodes) {
      if (node.id === selectedNode.value.id) continue
      if (alreadyConnected.has(node.id)) continue
      const spec = specForNode(node)
      if (!spec || !spec.outputs?.length) continue
      const output = spec.outputs.find((port) => portTypesCompatible(port.type, targetInput.type))
      if (!output) continue
      const label = node.title || spec.title || node.id
      candidates.push({
        node,
        label,
        outputType: output.label || output.type || output.name,
        tooltip: `${spec.title || node.id} 的 ${output.label || output.type} → 当前节点的 ${targetInput.label || targetInput.type}`,
      })
    }
    return candidates
  })

  function quickConnectUpstream(upstreamId: string) {
    if (!upstreamId) return
    upstreamNodeId.value = upstreamId
    connectUpstreamToSelected()
  }

  function upstreamNodeLabel(nodeId: string): string {
    const node = definition.value.graph.nodes.find((item) => item.id === nodeId)
    if (!node) return nodeId
    return node.title || specForNode(node)?.title || node.id
  }

  function connectUpstreamToSelected() {
    if (!selectedNode.value || !upstreamNodeId.value || !selectedNodeSpec.value) return
    const upstream = definition.value.graph.nodes.find((node) => node.id === upstreamNodeId.value)
    const upstreamSpec = specForNode(upstream)
    if (!upstream || !upstreamSpec) return

    const input = selectedNodeSpec.value.inputs[0]
    const output = upstreamSpec.outputs.find((port) => !input || portTypesCompatible(port.type, input.type)) || upstreamSpec.outputs[0]
    if (!input || !output) {
      statusMessage.value = '该节点缺少可连接端口'
      return
    }

    const exists = definition.value.graph.links.some(
      (link) => link.from.node === upstream.id && link.to.node === selectedNode.value?.id && link.to.port === input.name,
    )
    if (exists) {
      statusMessage.value = '该连接已存在'
      return
    }

    const upstreamGraphNode = findLiteGraphNode(upstream.id)
    const selectedGraphNode = findLiteGraphNode(selectedNode.value.id)
    if (upstreamGraphNode && selectedGraphNode) {
      const outputSlot = Math.max(0, upstreamGraphNode.findOutputSlot(output.name))
      const inputSlot = Math.max(0, selectedGraphNode.findInputSlot(input.name))
      upstreamGraphNode.connect(outputSlot, selectedGraphNode, inputSlot)
      upstreamNodeId.value = ''
      syncDefinitionFromLiteGraph(true)
      return
    }

    definition.value.graph.links.push({
      id: generateLinkId(),
      from: { node: upstream.id, port: output.name },
      to: { node: selectedNode.value.id, port: input.name },
    })
    upstreamNodeId.value = ''
    syncDefinitionToLiteGraph()
    markDirty()
  }

  function removeLink(linkId: string) {
    definition.value.graph.links = definition.value.graph.links.filter((link) => link.id !== linkId)
    syncDefinitionToLiteGraph()
    markDirty()
  }

  return {
    upstreamNodeId,
    selectedNodeInputLinks,
    connectableUpstreamCandidates,
    quickConnectUpstream,
    upstreamNodeLabel,
    removeLink,
  }
}
