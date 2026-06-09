// 工作流编辑器 · 承重墙（图定义 / 选中节点 / 节点规格）
//
// 从 PipelinePage.vue 抽出的「地基状态」：被画布、检查器、执行、产物、CRUD 等几十处读写。
// 本模块只持有状态与最基础的派生 / 查询；具体的增删改连、保存、运行等 CRUD 仍留在 PipelinePage，
// 通过解构拿到同一份 definition / selectedNodeId 的 ref 引用直接操作（响应式跨边界保持）。
// 注意：selectNode 依赖画布 selectLiteGraphNode，故不在此处，仍由 PipelinePage 持有。

import { computed, ref } from 'vue'
import type { NodeSpec, PipelineDefinitionPayload, PipelineGraphNode } from '@/types'

export function usePipelineEditor() {
  const nodeSpecs = ref<NodeSpec[]>([])
  const definition = ref<PipelineDefinitionPayload>(createEmptyDefinition())
  const selectedNodeId = ref('')

  const selectedNode = computed(() => definition.value.graph.nodes.find((node) => node.id === selectedNodeId.value) || null)
  const selectedNodeSpec = computed(() => (selectedNode.value ? specForNode(selectedNode.value) : null))

  function createEmptyDefinition(): PipelineDefinitionPayload {
    return {
      schema_version: 'elys.pipeline.v1',
      app_version: 'elys.app.v1',
      engine_version: null,
      name: null,
      description: null,
      graph: {
        nodes: [],
        links: [],
      },
      settings: {
        execution_scope: 'selected_datasets',
        failure_policy: 'continue',
      },
    }
  }

  function specForNode(node: PipelineGraphNode | null | undefined) {
    if (!node) return null
    return nodeSpecs.value.find((spec) => spec.type === node.type) || null
  }

  return {
    nodeSpecs,
    definition,
    selectedNodeId,
    selectedNode,
    selectedNodeSpec,
    createEmptyDefinition,
    specForNode,
  }
}
