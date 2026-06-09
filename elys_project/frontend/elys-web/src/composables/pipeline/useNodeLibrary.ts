// 工作流编辑器 · 左侧节点库（搜索 / 分组 / 折叠）
//
// 从 PipelinePage.vue 抽出：按关键词过滤节点规格、按 category 分组排序、分组折叠状态。
// 依赖承重墙的 nodeSpecs（以 Ref 形式传入、保持响应式）；其余状态自持。
// 分组的默认展开（首次加载节点规格时填充 groupOpen）仍由 PipelinePage 的 loadNodeSpecs 负责。

import { computed, reactive, ref, type Ref } from 'vue'
import type { NodeSpec } from '@/types'

export function useNodeLibrary(nodeSpecs: Ref<NodeSpec[]>) {
  const nodeSearch = ref('')
  const groupOpen = reactive<Record<string, boolean>>({})

  const filteredNodeSpecs = computed(() => {
    const text = nodeSearch.value.trim().toLowerCase()
    if (!text) return nodeSpecs.value
    return nodeSpecs.value.filter((spec) =>
      [spec.title, spec.type, spec.category, spec.description || '', ...(spec.tags || [])]
        .join(' ')
        .toLowerCase()
        .includes(text),
    )
  })

  const groupedNodeSpecs = computed(() => {
    const groups = new Map<string, NodeSpec[]>()
    for (const spec of filteredNodeSpecs.value) {
      const list = groups.get(spec.category) || []
      list.push(spec)
      groups.set(spec.category, list)
    }
    return Array.from(groups.entries())
      .map(([category, nodes]) => ({ category, nodes: nodes.sort((a, b) => a.title.localeCompare(b.title)) }))
      .sort((a, b) => a.category.localeCompare(b.category))
  })

  function toggleGroup(category: string) {
    groupOpen[category] = groupOpen[category] === false
  }

  return { nodeSearch, groupOpen, filteredNodeSpecs, groupedNodeSpecs, toggleGroup }
}
