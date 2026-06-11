// 工作流编辑器 · 事件标签下拉编辑器（检查器里 Epoch / ERP 节点的 event_select 属性）
//
// 从 PipelinePage.vue 抽出。Epoch 节点：从 graph 中所有 LoadData 节点的"已选中" data_infos 聚合事件；
// ERP 节点：候选 condition 只能是上游 Epoch 节点 event_id 里选过的（按 LoadData dataset_ids 过滤 count/datasets）。
// 关键：用注入的 loadDataSelectedInfos —— LoadData 没勾文件 → 无事件，不会泄漏数据库全集。
//
// 依赖承重墙 selectedNode / definition + LoadData 的 loadDataSelectedInfos（注入，留在主文件作共享 helper）
// + 画布 updateLiteGraphNode + 保存 markDirty。

import { computed, type Ref, type ComputedRef } from 'vue'
import type { NodeProperty, PipelineGraphNode, LoadDataDataInfo, PipelineDefinitionPayload } from '@/types'
import { EPOCH_NODE_TYPE, ERP_NODE_TYPE, LOAD_DATA_NODE_TYPE } from './pipelineConstants'

interface EventSelectEditorOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  definition: Ref<PipelineDefinitionPayload>
  loadDataSelectedInfos: (node: PipelineGraphNode) => LoadDataDataInfo[]
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useEventSelectEditor(options: EventSelectEditorOptions) {
  const { selectedNode, definition, loadDataSelectedInfos, updateLiteGraphNode, markDirty } = options

  const isEpochNode = computed(() => selectedNode.value?.type === EPOCH_NODE_TYPE)
  const isErpNode = computed(() => selectedNode.value?.type === ERP_NODE_TYPE)

  /** 沿 graph.links 倒推：从某节点开始向上找指定 type 的最近祖先节点（BFS）。 */
  function findUpstreamNodeByType(startNodeId: string, targetType: string): typeof definition.value.graph.nodes[number] | null {
    const links = definition.value.graph.links || []
    const incoming: Record<string, string[]> = {}
    for (const link of links) {
      const from = link.from?.node
      const to = link.to?.node
      if (typeof from === 'string' && typeof to === 'string') {
        if (!incoming[to]) incoming[to] = []
        incoming[to].push(from)
      }
    }
    const visited = new Set<string>([startNodeId])
    const queue: string[] = [...(incoming[startNodeId] || [])]
    while (queue.length) {
      const cur = queue.shift() as string
      if (visited.has(cur)) continue
      visited.add(cur)
      const node = definition.value.graph.nodes.find((n) => n.id === cur)
      if (node?.type === targetType) return node
      const parents = incoming[cur] || []
      for (const p of parents) if (!visited.has(p)) queue.push(p)
    }
    return null
  }

  const availableEventLabels = computed<Array<{ label: string; count: number; datasets: number }>>(() => {
    // Epoch 节点：从 graph 中所有 LoadData 节点的"已选中" data_infos 聚合事件。
    // 关键：用 loadDataSelectedInfos —— LoadData 没勾文件 → 无事件，不会泄漏数据库全集。
    if (isEpochNode.value) {
      const aggregate = new Map<string, { count: number; datasets: number }>()
      for (const node of definition.value.graph.nodes) {
        if (node.type !== LOAD_DATA_NODE_TYPE) continue
        for (const info of loadDataSelectedInfos(node)) {
          const labels = info.event_labels || []
          const counts = info.event_counts || {}
          for (const label of labels) {
            const existing = aggregate.get(label) || { count: 0, datasets: 0 }
            existing.count += counts[label] || 0
            existing.datasets += 1
            aggregate.set(label, existing)
          }
        }
      }
      return Array.from(aggregate.entries())
        .map(([label, info]) => ({ label, count: info.count, datasets: info.datasets }))
        .sort((a, b) => {
          const an = Number(a.label)
          const bn = Number(b.label)
          if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn
          return a.label.localeCompare(b.label)
        })
    }

    // ERP 节点：候选 condition 只能是上游 Epoch 节点 event_id 里选过的
    // count / datasets 同样按 LoadData dataset_ids 过滤。
    if (isErpNode.value && selectedNode.value) {
      const upstreamEpoch = findUpstreamNodeByType(selectedNode.value.id, EPOCH_NODE_TYPE)
      const raw = upstreamEpoch?.params?.event_id
      let labels: string[] = []
      if (Array.isArray(raw)) labels = raw.map((s) => String(s).trim()).filter(Boolean)
      else if (typeof raw === 'string' && raw.trim()) {
        labels = raw.split(',').map((s) => s.trim()).filter(Boolean)
      }

      const allowed = new Set(labels)
      const aggregate = new Map<string, { count: number; datasets: number }>()
      for (const n of definition.value.graph.nodes) {
        if (n.type !== LOAD_DATA_NODE_TYPE) continue
        for (const info of loadDataSelectedInfos(n)) {
          const ls = info.event_labels || []
          const counts = info.event_counts || {}
          for (const lab of ls) {
            if (!allowed.has(lab)) continue
            const existing = aggregate.get(lab) || { count: 0, datasets: 0 }
            existing.count += counts[lab] || 0
            existing.datasets += 1
            aggregate.set(lab, existing)
          }
        }
      }

      // 保持上游 Epoch event_id 中的标签顺序；没真实 count 的填 0
      return labels.map((label) => {
        const info = aggregate.get(label)
        return { label, count: info?.count ?? 0, datasets: info?.datasets ?? 0 }
      })
    }

    return []
  })

  function getEventIdArray(prop: NodeProperty): string[] {
    const raw = selectedNode.value?.params?.[prop.name]
    if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
    if (typeof raw === 'string' && raw.trim()) {
      return raw
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    }
    return []
  }

  function isEventIdSelected(prop: NodeProperty, label: string) {
    return getEventIdArray(prop).includes(label)
  }

  function toggleEventId(prop: NodeProperty, label: string) {
    const node = selectedNode.value
    if (!node) return
    const current = new Set(getEventIdArray(prop))
    if (current.has(label)) current.delete(label)
    else current.add(label)
    node.params = { ...node.params, [prop.name]: Array.from(current) }
    updateLiteGraphNode(node)
    markDirty()
  }

  function clearEventIds(prop: NodeProperty) {
    const node = selectedNode.value
    if (!node) return
    node.params = { ...node.params, [prop.name]: [] }
    updateLiteGraphNode(node)
    markDirty()
  }

  return {
    availableEventLabels,
    getEventIdArray,
    isEventIdSelected,
    toggleEventId,
    clearEventIds,
  }
}
