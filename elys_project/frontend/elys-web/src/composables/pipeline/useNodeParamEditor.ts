// 工作流编辑器 · 节点参数编辑（检查器属性表单的通用读写层）
//
// 从 PipelinePage.vue 抽出：
//   - 条件显示：effectiveNodeParams（默认值+实参合并）→ isPropVisible（visible_when 判定）→ visibleBasic/Advanced；
//   - 通用读写：formatParamValue（显示）/ updateSelectedParam（写 + coerceParamValue 类型强转）/ handleParamInput/Checkbox；
//   - 节点标题：handleNodeTitleInput。
// 注：channel_list / event_select / tags_input 等特殊编辑器各有独立 composable，这里只管「通用字段」。
// 依赖承重墙 selectedNode / selectedNodeSpec + 画布 updateLiteGraphNode + 保存 markDirty。

import { computed, type ComputedRef } from 'vue'
import type { NodeProperty, PipelineGraphNode, NodeSpec } from '@/types'

interface NodeParamEditorOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  selectedNodeSpec: ComputedRef<NodeSpec | null>
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useNodeParamEditor(options: NodeParamEditorOptions) {
  const { selectedNode, selectedNodeSpec, updateLiteGraphNode, markDirty } = options

  // effectiveNodeParams：属性默认值 + 用户实参合并，给 visible_when 判定用（控制字段未显式给时回退默认）
  const effectiveNodeParams = computed<Record<string, unknown>>(() => {
    const eff: Record<string, unknown> = {}
    const spec = selectedNodeSpec.value
    if (spec) {
      for (const prop of spec.properties) {
        if (prop.default !== undefined) eff[prop.name] = prop.default
      }
    }
    const params = (selectedNode.value?.params ?? {}) as Record<string, unknown>
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') eff[key] = value
    }
    return eff
  })

  const isPropVisible = (prop: { visible_when?: Record<string, Array<string | number | boolean>> }): boolean => {
    const rules = prop.visible_when
    if (!rules) return true
    const eff = effectiveNodeParams.value
    return Object.entries(rules).every(([key, allowed]) =>
      allowed.map((value) => String(value)).includes(String(eff[key])),
    )
  }

  const visibleBasicProperties = computed(() =>
    (selectedNodeSpec.value?.properties ?? []).filter((prop) => !prop.advanced && isPropVisible(prop)),
  )
  const visibleAdvancedProperties = computed(() =>
    (selectedNodeSpec.value?.properties ?? []).filter((prop) => prop.advanced && isPropVisible(prop)),
  )

  function formatParamValue(prop: NodeProperty) {
    const value = selectedNode.value?.params[prop.name]
    if (prop.type === 'channel_list' && Array.isArray(value)) return value.join(', ')
    return value ?? ''
  }

  function handleParamInput(prop: NodeProperty, event: Event) {
    const value = (event.target as HTMLInputElement | HTMLSelectElement).value
    updateSelectedParam(prop, value)
  }

  function handleParamCheckbox(prop: NodeProperty, event: Event) {
    updateSelectedParam(prop, (event.target as HTMLInputElement).checked)
  }

  function updateSelectedParam(prop: NodeProperty, rawValue: unknown) {
    if (!selectedNode.value) return
    selectedNode.value.params = {
      ...selectedNode.value.params,
      [prop.name]: coerceParamValue(prop, rawValue),
    }
    updateLiteGraphNode(selectedNode.value)
    markDirty()
  }

  function coerceParamValue(prop: NodeProperty, rawValue: unknown) {
    if (prop.type === 'number') {
      const value = Number(rawValue)
      return Number.isFinite(value) ? value : null
    }
    if (prop.type === 'integer') {
      const value = Number(rawValue)
      return Number.isFinite(value) ? Math.trunc(value) : null
    }
    if (prop.type === 'boolean') return Boolean(rawValue)
    if (prop.type === 'channel_list') {
      return String(rawValue || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    }
    if (prop.type === 'select') {
      const option = prop.options?.find((item) => String(item.value) === String(rawValue))
      return option ? option.value : rawValue
    }
    return rawValue
  }

  function handleNodeTitleInput(event: Event) {
    if (!selectedNode.value) return
    selectedNode.value.title = (event.target as HTMLInputElement).value
    updateLiteGraphNode(selectedNode.value)
    markDirty()
  }

  return {
    visibleBasicProperties,
    visibleAdvancedProperties,
    formatParamValue,
    handleParamInput,
    handleParamCheckbox,
    handleNodeTitleInput,
  }
}
