// 工作流编辑器 · 事件标签选择器（检查器里 Epoch / ERP / TFR / PSD 节点的 event_select 属性）
//
// 方案 B：候选「沿链路在后端解析」——选中 event_select 节点时，把（可能未保存的）实时图 + 节点 id
// POST 给 /pipeline/resolve-conditions，后端按上游链路算出可用 condition（Epoch=看上游 LoadData 链路；
// ERP/TFR/PSD=看上游 Epoch 实际切出的 condition），前端只渲染。取代旧的「前端各自扫 LoadData + BFS」，
// 与运行时切分共用一套服务端口径，且天然支持将来的事件变换节点（方案 C）。
//
// 依赖承重墙 selectedNode / definition + selectedStudyId（取数）+ 画布 updateLiteGraphNode + 保存 markDirty。

import { computed, reactive, ref, watch, type Ref, type ComputedRef } from 'vue'
import type { NodeProperty, PipelineGraphNode, PipelineDefinitionPayload, ConditionOption } from '@/types'
import { EPOCH_NODE_TYPE, ERP_NODE_TYPE, TFR_NODE_TYPE, PSD_NODE_TYPE, EVENT_REMAP_NODE_TYPE } from './pipelineConstants'
import { pipelineApi } from '@/api/pipelines'

interface EventSelectEditorOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  definition: Ref<PipelineDefinitionPayload>
  selectedStudyId: Ref<string> | ComputedRef<string>
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

// 这些节点的条件候选都沿链路在后端解析：Epoch（看上游 LoadData）、ERP/TFR/PSD（看上游 Epoch 切出的）、
// Event Remap（看上游原始事件，作为重映射规则的「源」池）。
const EVENT_SELECT_TYPES = new Set<string>([
  EPOCH_NODE_TYPE,
  ERP_NODE_TYPE,
  TFR_NODE_TYPE,
  PSD_NODE_TYPE,
  EVENT_REMAP_NODE_TYPE,
])

/** Event Remap 一条规则：把若干「源事件分组名」映射到一个目标名（目标留空 = 丢弃）。 */
type RemapRule = { sources: string[]; target: string }

export function useEventSelectEditor(options: EventSelectEditorOptions) {
  const { selectedNode, definition, selectedStudyId, updateLiteGraphNode, markDirty } = options

  // 后端沿链路解析的候选缓存（按节点 id）。方案 B：服务端单一事实源。
  const conditionsByNodeId = reactive<Record<string, ConditionOption[]>>({})
  const conditionsLoading = ref(false)
  let resolveSeq = 0

  /** 让某节点的候选重新从后端解析（seq 防过期响应覆盖新结果）。 */
  async function fetchConditions(node: PipelineGraphNode) {
    const studyId = selectedStudyId.value
    if (!studyId || !EVENT_SELECT_TYPES.has(node.type)) return
    const seq = ++resolveSeq
    conditionsLoading.value = true
    try {
      const res = await pipelineApi.resolveConditions(studyId, {
        node_id: node.id,
        graph: definition.value.graph,
      })
      if (seq !== resolveSeq) return // 过期响应丢弃
      conditionsByNodeId[node.id] = res.data.conditions || []
    } catch {
      if (seq !== resolveSeq) return
      conditionsByNodeId[node.id] = []
    } finally {
      if (seq === resolveSeq) conditionsLoading.value = false
    }
  }

  // 选中 event_select 节点、或其上游（连线 / LoadData 选择 / 上游 Epoch 勾选）变化 → 重解析。
  // 签名刻意**排除选中节点自身的 conditions**：勾选自己的 condition 不影响自己的输入候选，避免无谓重取。
  const resolveSignature = computed(() => {
    const node = selectedNode.value
    if (!node || !EVENT_SELECT_TYPES.has(node.type)) return ''
    const graph = definition.value.graph
    const links = (graph.links || []).map((l) => `${l.from?.node}>${l.to?.node}`).join('|')
    const params = (graph.nodes || [])
      .map((n) => {
        const conds = n.id === node.id ? '' : JSON.stringify(n.params?.conditions ?? '')
        return `${n.id}:${JSON.stringify(n.params?.dataset_ids ?? '')}:${conds}`
      })
      .join('|')
    return `${node.id}#${links}#${params}`
  })

  watch(
    resolveSignature,
    (sig) => {
      const node = selectedNode.value
      if (!sig || !node) return
      void fetchConditions(node)
    },
    { immediate: true },
  )

  const availableEventLabels = computed<Array<{ label: string; count: number; datasets: number }>>(() => {
    const node = selectedNode.value
    if (!node) return []
    return (conditionsByNodeId[node.id] || []).map((c) => ({
      label: c.name,
      count: c.count,
      datasets: c.datasets,
    }))
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

  // —— Event Remap 规则编辑（方案 C）：rules = [{sources:[分组名], target:"新名字"}]；源池 = availableEventLabels ——
  function getRemapRules(prop: NodeProperty): RemapRule[] {
    const raw = selectedNode.value?.params?.[prop.name]
    if (!Array.isArray(raw)) return []
    return raw.map((r) => {
      const rec = (r && typeof r === 'object' ? r : {}) as Record<string, unknown>
      return {
        sources: Array.isArray(rec.sources) ? rec.sources.map((s) => String(s)).filter(Boolean) : [],
        target: typeof rec.target === 'string' ? rec.target : '',
      }
    })
  }
  function setRemapRules(prop: NodeProperty, rules: RemapRule[]) {
    const node = selectedNode.value
    if (!node) return
    node.params = { ...node.params, [prop.name]: rules }
    updateLiteGraphNode(node)
    markDirty()
  }
  function addRemapRule(prop: NodeProperty) {
    setRemapRules(prop, [...getRemapRules(prop), { sources: [], target: '' }])
  }
  function removeRemapRule(prop: NodeProperty, index: number) {
    const rules = getRemapRules(prop)
    rules.splice(index, 1)
    setRemapRules(prop, rules)
  }
  function toggleRemapRuleSource(prop: NodeProperty, index: number, label: string) {
    const rules = getRemapRules(prop)
    const rule = rules[index]
    if (!rule) return
    const set = new Set(rule.sources)
    if (set.has(label)) set.delete(label)
    else set.add(label)
    rule.sources = Array.from(set)
    setRemapRules(prop, rules)
  }
  function isRemapRuleSourceSelected(prop: NodeProperty, index: number, label: string) {
    return getRemapRules(prop)[index]?.sources.includes(label) ?? false
  }
  function setRemapRuleTarget(prop: NodeProperty, index: number, value: string) {
    const rules = getRemapRules(prop)
    const rule = rules[index]
    if (!rule) return
    rule.target = value
    setRemapRules(prop, rules)
  }

  return {
    availableEventLabels,
    conditionsLoading,
    getEventIdArray,
    isEventIdSelected,
    toggleEventId,
    clearEventIds,
    getRemapRules,
    addRemapRule,
    removeRemapRule,
    toggleRemapRuleSource,
    isRemapRuleSourceSelected,
    setRemapRuleTarget,
  }
}
