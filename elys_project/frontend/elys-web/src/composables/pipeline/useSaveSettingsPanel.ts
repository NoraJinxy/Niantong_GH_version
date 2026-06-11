// 工作流编辑器 · 保存设置面板（检查器底部 P4 折叠区：display_name 模板 / auto_tags 预览 / 自定义标签）
//
// 从 PipelinePage.vue 抽出。saveSpec 来自节点 spec 的 save 子对象（source 节点无 save → 隐藏整个折叠区）。
// previewDisplayName / autoTagsPreview 在前端复刻后端 render_template，用 studyDatasets 第一项作示例 subject/task。
// 依赖承重墙 selectedNode / selectedNodeSpec + LoadData 的 studyDatasets（注入）+ 画布 updateLiteGraphNode + markDirty。

import { computed, ref, type Ref, type ComputedRef } from 'vue'
import type { Recording, PipelineGraphNode, NodeSpec } from '@/types'

interface SaveSettingsPanelOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  selectedNodeSpec: ComputedRef<NodeSpec | null>
  studyDatasets: Ref<Recording[]>
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useSaveSettingsPanel(options: SaveSettingsPanelOptions) {
  const { selectedNode, selectedNodeSpec, studyDatasets, updateLiteGraphNode, markDirty } = options

  // 折叠区展开状态 + 自定义标签草稿（独立于其他 tag drafts）
  const saveSettingsOpen = ref(false)
  const userTagDraft = ref('')

  /** 节点 spec 中 save 子对象（P0 起所有处理节点都填）。无则隐藏整个折叠区。 */
  const saveSpec = computed<Record<string, unknown> | null>(() => {
    const raw = (selectedNodeSpec.value as unknown as Record<string, unknown> | null)?.save
    if (!raw || typeof raw !== 'object') return null
    // LoadData 等 source 节点不声明 save 字段，但后端 Pydantic schema
    // 用 default_factory=dict 默认填空 {} → 前端要把空 dict 视为"无保存配置"。
    if (Object.keys(raw as Record<string, unknown>).length === 0) return null
    return raw as Record<string, unknown>
  })

  /** Epoch 节点 split_by=condition 时，模板使用 _split 变体；否则用 default 模板。 */
  const splitMode = computed<string>(() => {
    const node = selectedNode.value
    if (!node) return 'none'
    const raw = node.params?.split_by
    return typeof raw === 'string' ? raw.trim().toLowerCase() : 'none'
  })

  /** 选择当前生效的 spec 模板（split 影响模板选择）。 */
  const effectiveNameTemplate = computed<string>(() => {
    const spec = saveSpec.value
    if (!spec) return '{subject}_{task}_{node_title}'
    if (splitMode.value === 'condition') {
      return String(spec.name_template_default_split || spec.name_template_default || '{subject}_{task}_{node_title}')
    }
    return String(spec.name_template_default || '{subject}_{task}_{node_title}')
  })

  /** display_name 预览（前端复刻后端 render_template，缺失值回落 {name?}）。 */
  function renderTemplatePreview(tpl: string, ctx: Record<string, unknown>): string {
    if (!tpl) return ''
    return tpl.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (_match, name: string) => {
      if (name === 'subject') {
        const v = ctx.subject || ctx.bids_subject_id || ctx.subject_id
        return v ? String(v) : '{subject?}'
      }
      if (name === 'index') {
        return ctx.index != null ? String(ctx.index) : '{index?}'
      }
      const v = ctx[name]
      if (v === undefined || v === null || v === '') return `{${name}?}`
      return String(v)
    })
  }

  const previewDisplayName = computed<string>(() => {
    const node = selectedNode.value
    const spec = saveSpec.value
    if (!node || !spec) return ''
    const userTemplate = String(node.params?.display_name_template || '').trim()
    const template = userTemplate || effectiveNameTemplate.value
    // 用 study_datasets 第一项的 subject/task 作为预览示例
    const exampleRaw = ((studyDatasets.value || [])[0] || {}) as Record<string, unknown>
    const exampleSubject =
      (exampleRaw.bids_subject_id as string | undefined) ||
      (exampleRaw.subject_id as string | undefined) ||
      'sub-XX'
    const exampleTask = (exampleRaw.task as string | undefined) || 'task'
    // condition 预览：split=condition 时用 'go'；ERP 节点用 params.condition 第一个
    let exampleCondition: string | undefined
    if (splitMode.value === 'condition') {
      exampleCondition = 'go'
    } else {
      const condRaw = node.params?.condition
      if (typeof condRaw === 'string' && condRaw.trim()) exampleCondition = condRaw.trim()
      else if (Array.isArray(condRaw) && condRaw.length) exampleCondition = String(condRaw[0])
      else if (spec.always_per_condition) exampleCondition = 'go'
    }
    return renderTemplatePreview(template, {
      subject: exampleSubject,
      bids_subject_id: exampleSubject,
      task: exampleTask,
      node_title: node.title || selectedNodeSpec.value?.title || node.type,
      step_label: spec.step_label,
      data_type: spec.data_type,
      condition: exampleCondition,
      index: 1,
    })
  })

  /** 自动 tag 预览（spec 的 auto_tags + dynamic_tags，模板渲染后展示给用户）。 */
  const autoTagsPreview = computed<string[]>(() => {
    const spec = saveSpec.value
    if (!spec) return []
    const result: string[] = []
    const seen = new Set<string>()
    const node = selectedNode.value
    const ctx: Record<string, unknown> = {
      condition: splitMode.value === 'condition' ? '{condition}' : (node?.params?.condition || (spec.always_per_condition ? '{condition}' : '')),
    }
    const sources: unknown[] = [spec.auto_tags]
    if (spec.always_per_condition) sources.push(spec.dynamic_tags_always)
    else if (splitMode.value === 'condition') sources.push(spec.dynamic_tags_when_split)
    for (const source of sources) {
      if (!Array.isArray(source)) continue
      for (const raw of source) {
        const tag = renderTemplatePreview(String(raw), ctx).trim()
        if (!tag || seen.has(tag)) continue
        seen.add(tag)
        result.push(tag)
      }
    }
    return result
  })

  /** 用户自定义标签（存于 selectedNode.params.tags）。 */
  const userTagsArray = computed<string[]>(() => {
    const raw = selectedNode.value?.params?.tags
    if (Array.isArray(raw)) return raw.map((item) => String(item).trim()).filter(Boolean)
    if (typeof raw === 'string' && raw.trim()) {
      return raw.split(',').map((item) => item.trim()).filter(Boolean)
    }
    return []
  })

  function getSaveSetting(field: string): string {
    const raw = selectedNode.value?.params?.[field]
    if (raw == null) return ''
    return String(raw)
  }

  function onSaveSettingInput(field: string, event: Event) {
    const node = selectedNode.value
    if (!node) return
    const target = event.target as HTMLInputElement | HTMLSelectElement
    const value = target.value
    node.params = { ...node.params, [field]: value }
    updateLiteGraphNode(node)
    markDirty()
  }

  function onSaveSettingsToggle(event: Event) {
    saveSettingsOpen.value = (event.target as HTMLDetailsElement).open
  }

  function removeUserTag(tag: string) {
    const node = selectedNode.value
    if (!node) return
    const next = userTagsArray.value.filter((t) => t !== tag)
    node.params = { ...node.params, tags: next }
    updateLiteGraphNode(node)
    markDirty()
  }

  function commitUserTagDraft() {
    const node = selectedNode.value
    if (!node) return
    const draft = userTagDraft.value
    if (!draft.trim()) return
    const pieces = draft.split(',').map((s) => s.trim()).filter(Boolean)
    const merged = [...userTagsArray.value]
    for (const piece of pieces) {
      if (!merged.includes(piece)) merged.push(piece)
    }
    node.params = { ...node.params, tags: merged }
    userTagDraft.value = ''
    updateLiteGraphNode(node)
    markDirty()
  }

  return {
    saveSettingsOpen,
    userTagDraft,
    saveSpec,
    effectiveNameTemplate,
    previewDisplayName,
    autoTagsPreview,
    userTagsArray,
    getSaveSetting,
    onSaveSettingInput,
    onSaveSettingsToggle,
    removeUserTag,
    commitUserTagDraft,
  }
}
