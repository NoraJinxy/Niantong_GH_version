// 工作流编辑器 · 标签输入编辑器（检查器里 prop.type === 'tags_input' 的通用属性，Save 节点等使用）
//
// 从 PipelinePage.vue 抽出。用户自由打标签的 chip 输入：回车提交（支持逗号一次多条、去重），点 chip 移除。
// 草稿按 `节点id::属性名` 分桶，互不串台。依赖承重墙 selectedNode + 画布 updateLiteGraphNode + 保存 markDirty。

import { reactive, type ComputedRef } from 'vue'
import type { NodeProperty, PipelineGraphNode } from '@/types'

interface TagsInputEditorOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useTagsInputEditor(options: TagsInputEditorOptions) {
  const { selectedNode, updateLiteGraphNode, markDirty } = options

  const paramTagDrafts = reactive<Record<string, string>>({})

  function paramTagKey(prop: NodeProperty): string {
    const node = selectedNode.value
    return `${node?.id || ''}::${prop.name}`
  }

  function getTagsArray(prop: NodeProperty): string[] {
    const node = selectedNode.value
    if (!node) return []
    const raw = node.params[prop.name]
    if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
    if (typeof raw === 'string' && raw.trim()) {
      return raw.split(',').map((item) => item.trim()).filter(Boolean)
    }
    return []
  }

  function paramTagDraftFor(prop: NodeProperty): string {
    return paramTagDrafts[paramTagKey(prop)] || ''
  }

  function setParamTagDraft(prop: NodeProperty, value: string) {
    paramTagDrafts[paramTagKey(prop)] = value
  }

  function commitParamTagDraft(prop: NodeProperty) {
    const node = selectedNode.value
    if (!node) return
    const draft = (paramTagDrafts[paramTagKey(prop)] || '').trim()
    if (!draft) return
    const existing = getTagsArray(prop)
    const next: string[] = [...existing]
    const seen = new Set(existing)
    for (const piece of draft.split(',')) {
      const text = piece.trim()
      if (!text || seen.has(text)) continue
      seen.add(text)
      next.push(text)
    }
    node.params = { ...node.params, [prop.name]: next }
    paramTagDrafts[paramTagKey(prop)] = ''
    updateLiteGraphNode(node)
    markDirty()
  }

  function toggleParamTag(prop: NodeProperty, tag: string) {
    const node = selectedNode.value
    if (!node) return
    const tags = getTagsArray(prop).filter((item) => item !== tag)
    node.params = { ...node.params, [prop.name]: tags }
    updateLiteGraphNode(node)
    markDirty()
  }

  return {
    getTagsArray,
    paramTagDraftFor,
    setParamTagDraft,
    commitParamTagDraft,
    toggleParamTag,
  }
}
