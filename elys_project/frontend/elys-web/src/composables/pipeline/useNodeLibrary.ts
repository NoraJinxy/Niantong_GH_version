// 工作流编辑器 · 左侧节点库（搜索 / 分组 / 折叠）
//
// 从 PipelinePage.vue 抽出：按关键词过滤节点规格、按 category 分组排序、分组折叠状态。
// 依赖承重墙的 nodeSpecs（以 Ref 形式传入、保持响应式）；其余状态自持。
// 分组的默认展开（首次加载节点规格时填充 groupOpen）仍由 PipelinePage 的 loadNodeSpecs 负责。

import { computed, reactive, ref, type Ref } from 'vue'
import type { NodeSpec } from '@/types'

// 大类按「分析工作流」顺序排列（而非字母序）+ 友好中文名 —— 用户一眼看出流程方向。
const CATEGORY_ORDER = ['data', 'preprocess', 'ica', 'epoch', 'analysis', 'group']
const CATEGORY_LABEL: Record<string, string> = {
  data: '数据',
  preprocess: '预处理',
  ica: 'ICA 去伪迹',
  epoch: '分段',
  analysis: '分析',
  group: '组分析',
}
// 同一大类内的节点也按工作流顺序（不按字母）；未列出的排到末尾。
const NODE_ORDER = [
  'eeg/data/load',
  'eeg/filter/apply', 'eeg/preproc/resample', 'eeg/preproc/rereference',
  'eeg/preproc/channel_location', 'eeg/preproc/bad_channels',
  'eeg/preproc/artifact_mark', 'eeg/preproc/event_remap',
  'eeg/ica/compute', 'eeg/ica/apply', 'eeg/ica/iclabel',
  'eeg/epoch/segment', 'eeg/epoch/baseline', 'eeg/epoch/reject',
  'eeg/analysis/erp', 'eeg/analysis/tfr', 'eeg/analysis/psd',
  'eeg/group/merge', 'eeg/group/average', 'eeg/group/compare',
]

// 老节点 category 别名归一（"preprocessing" 与 "preprocess" 合成一组）。
function normCategory(category: string): string {
  return category === 'preprocessing' ? 'preprocess' : category
}
function catRank(category: string): number {
  const i = CATEGORY_ORDER.indexOf(category)
  return i < 0 ? CATEGORY_ORDER.length : i
}
function nodeRank(type: string): number {
  const i = NODE_ORDER.indexOf(type)
  return i < 0 ? NODE_ORDER.length : i
}

export interface NodeLibraryGroup {
  category: string
  label: string
  nodes: NodeSpec[]
}

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

  const groupedNodeSpecs = computed<NodeLibraryGroup[]>(() => {
    const groups = new Map<string, NodeSpec[]>()
    for (const spec of filteredNodeSpecs.value) {
      const category = normCategory(spec.category)
      const list = groups.get(category) || []
      list.push(spec)
      groups.set(category, list)
    }
    return Array.from(groups.entries())
      .map(([category, nodes]) => ({
        category,
        label: CATEGORY_LABEL[category] || category,
        nodes: nodes.sort((a, b) => nodeRank(a.type) - nodeRank(b.type) || a.title.localeCompare(b.title)),
      }))
      .sort((a, b) => catRank(a.category) - catRank(b.category) || a.category.localeCompare(b.category))
  })

  function toggleGroup(category: string) {
    groupOpen[category] = groupOpen[category] === false
  }

  return { nodeSearch, groupOpen, filteredNodeSpecs, groupedNodeSpecs, toggleGroup }
}
