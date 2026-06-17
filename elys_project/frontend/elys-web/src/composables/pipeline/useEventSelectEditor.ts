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
import { EPOCH_NODE_TYPE, ERP_NODE_TYPE, TFR_NODE_TYPE, PSD_NODE_TYPE, LOAD_DATA_NODE_TYPE } from './pipelineConstants'

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
  // ERP / TFR / PSD 同口径：候选 condition 都来自上游 Epoch 勾选的分组
  const isConditionFromEpoch = computed(
    () =>
      selectedNode.value?.type === ERP_NODE_TYPE ||
      selectedNode.value?.type === TFR_NODE_TYPE ||
      selectedNode.value?.type === PSD_NODE_TYPE,
  )

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

  /** 把上游所有 LoadData「已选中」data_infos 的事件分组聚合成 名字→{count,datasets}。
   *  Epoch 节点直接列出供勾选；ERP/TFR 节点用它给候选 condition 回填真实事件数。
   *  关键：用 loadDataSelectedInfos —— LoadData 没勾文件 → 无事件，不会泄漏数据库全集。 */
  function loadDataGroupCounts(): Map<string, { count: number; datasets: number }> {
    const aggregate = new Map<string, { count: number; datasets: number }>()
    for (const node of definition.value.graph.nodes) {
      if (node.type !== LOAD_DATA_NODE_TYPE) continue
      for (const info of loadDataSelectedInfos(node)) {
        for (const g of info.condition_groups || []) {
          const name = String(g?.name ?? '').trim()
          if (!name) continue
          const existing = aggregate.get(name) || { count: 0, datasets: 0 }
          existing.count += Number(g?.count) || 0
          existing.datasets += 1
          aggregate.set(name, existing)
        }
      }
    }
    return aggregate
  }

  const availableEventLabels = computed<Array<{ label: string; count: number; datasets: number }>>(() => {
    const groups = loadDataGroupCounts()

    // Epoch 节点：列出上游 LoadData 的全部事件分组供勾选。
    if (isEpochNode.value) {
      return Array.from(groups.entries())
        .map(([label, info]) => ({ label, count: info.count, datasets: info.datasets }))
        .sort((a, b) => {
          const an = Number(a.label)
          const bn = Number(b.label)
          if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn
          return a.label.localeCompare(b.label)
        })
    }

    // ERP / TFR 节点：候选 = 上游 Epoch 勾选的 condition 名（直接读其 conditions 参数）。
    // 计数回查 LoadData 分组：分组名字符串能直接命中真实事件数；脚本/API 的友好名字典
    // （name=fist 之类）匹配不到 → 回落 0，但不再把"有 40 试次"误显成 0。
    if (isConditionFromEpoch.value && selectedNode.value) {
      const upstreamEpoch = findUpstreamNodeByType(selectedNode.value.id, EPOCH_NODE_TYPE)
      const raw = upstreamEpoch?.params?.conditions
      let names: string[] = []
      if (Array.isArray(raw)) {
        names = raw
          .map((s) => (typeof s === 'string' ? s : String((s as { name?: unknown })?.name ?? '')))
          .map((s) => s.trim())
          .filter(Boolean)
      }
      return names.map((label) => {
        const g = groups.get(label)
        return { label, count: g?.count ?? 0, datasets: g?.datasets ?? 1 }
      })
    }

    return []
  })

  function getEventIdArray(prop: NodeProperty): string[] {
    const raw = selectedNode.value?.params?.[prop.name]
    // conditions 可能是前端勾的「分组名字符串」，也可能是脚本/API 写的 {name,pattern,mode} 规则字典；
    // 后者取 name 显示，避免 String(dict) 渲染成 [object Object]（chip 只做展示对齐，不还原 pattern/mode）。
    if (Array.isArray(raw)) {
      return raw
        .map((item) =>
          item && typeof item === 'object'
            ? String((item as Record<string, unknown>).name ?? (item as Record<string, unknown>).pattern ?? '')
            : String(item),
        )
        .filter(Boolean)
    }
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
