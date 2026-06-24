// 工作流编辑器 · 核心上下文（承重墙 + 会话标志）
//
// 从 PipelinePage.vue 抽出的「地基状态」：图定义 / 选中节点 / 节点规格（承重墙），
// 外加编辑器会话级共享标志（dirty / statusMessage / hydrating）。被画布、执行、检查器、
// 产物等几乎所有域读写。
//
// 用法：
//   - PipelinePage 顶层 `const editor = usePipelineEditor()` —— 创建上下文并 provide。
//   - 深层 composable / 子组件（如 inspectors/）用 `useEditorContext()` inject 取用，
//     避免一路 props / 散参数透传（解决核心域参数爆炸）。
// CRUD（增删改连、保存、运行）仍留在 PipelinePage，通过解构拿到同一份 ref 引用直接操作
// （响应式跨边界保持）。注意：selectNode 依赖画布 selectLiteGraphNode，故不在此处。

import { computed, ref, provide, inject, type InjectionKey } from 'vue'
import type { NodeSpec, PipelineDefinitionPayload, PipelineGraphNode } from '@/types'

function createPipelineEditorContext() {
  const nodeSpecs = ref<NodeSpec[]>([])
  const definition = ref<PipelineDefinitionPayload>(createEmptyDefinition())
  const selectedNodeId = ref('')

  // 编辑器会话级共享标志（多域共享：脏标记 / 状态提示条 / 加载中守卫）
  const dirty = ref(false)
  const statusMessage = ref('')
  const hydrating = ref(false)

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
    dirty,
    statusMessage,
    hydrating,
    selectedNode,
    selectedNodeSpec,
    createEmptyDefinition,
    specForNode,
  }
}

export type PipelineEditorContext = ReturnType<typeof createPipelineEditorContext>

const EDITOR_CONTEXT_KEY: InjectionKey<PipelineEditorContext> = Symbol('elys.pipeline.editor')

/** 在 PipelinePage 顶层调用一次：创建编辑器核心上下文，并 provide 给子组件 / 深层 composable。 */
export function usePipelineEditor(): PipelineEditorContext {
  const ctx = createPipelineEditorContext()
  provide(EDITOR_CONTEXT_KEY, ctx)
  return ctx
}

/** 子组件 / 深层 composable 用：inject 已 provide 的编辑器上下文。 */
export function useEditorContext(): PipelineEditorContext {
  const ctx = inject(EDITOR_CONTEXT_KEY)
  if (!ctx) {
    throw new Error('[ELYS] useEditorContext 必须在 PipelinePage（已 provide 编辑器上下文）的组件树内调用')
  }
  return ctx
}
