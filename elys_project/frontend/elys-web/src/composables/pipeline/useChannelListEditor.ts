// 工作流编辑器 · 通道列表编辑器（检查器里 prop.type === 'channel_list' 的逻辑）
//
// 从 PipelinePage.vue 抽出。通道来源 = 当前节点所有上游 LoadData 节点 selectedInfos 的 ch_names 交集。
// 交集而非并集 —— 用户如果选了多个 ch_names 不一致的文件，只显示"都有"的通道，避免运行时报错。
//
// 依赖承重墙 selectedNode / definition + LoadData 的 loadDataSelectedInfos（注入，留在主文件作共享 helper）
// + 画布 updateLiteGraphNode + 保存 markDirty。listbox 多选交互与 LoadDataPanel Include 一致。

import { computed, reactive, type Ref, type ComputedRef } from 'vue'
import type { NodeProperty, PipelineGraphNode, LoadDataDataInfo, PipelineDefinitionPayload } from '@/types'
import { LOAD_DATA_NODE_TYPE } from './pipelineConstants'

interface ChannelListEditorOptions {
  selectedNode: ComputedRef<PipelineGraphNode | null>
  definition: Ref<PipelineDefinitionPayload>
  loadDataSelectedInfos: (node: PipelineGraphNode) => LoadDataDataInfo[]
  updateLiteGraphNode: (node: PipelineGraphNode) => void
  markDirty: () => void
}

export function useChannelListEditor(options: ChannelListEditorOptions) {
  const { selectedNode, definition, loadDataSelectedInfos, updateLiteGraphNode, markDirty } = options

  const channelFilterDrafts = reactive<Record<string, string>>({})

  function channelFilterKey(prop: NodeProperty): string {
    return `${selectedNode.value?.id || ''}::${prop.name}`
  }

  function channelFilterFor(prop: NodeProperty): string {
    return channelFilterDrafts[channelFilterKey(prop)] || ''
  }

  function setChannelFilter(prop: NodeProperty, value: string) {
    channelFilterDrafts[channelFilterKey(prop)] = value
  }

  /** 沿 graph.links 倒推所有上游节点中类型为 targetType 的全部节点（BFS，不止找第一个）。 */
  function findAllUpstreamNodesByType(startNodeId: string, targetType: string): typeof definition.value.graph.nodes {
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
    const result: typeof definition.value.graph.nodes = []
    while (queue.length) {
      const cur = queue.shift() as string
      if (visited.has(cur)) continue
      visited.add(cur)
      const node = definition.value.graph.nodes.find((n) => n.id === cur)
      if (node) {
        if (node.type === targetType) result.push(node)
        for (const p of incoming[cur] || []) if (!visited.has(p)) queue.push(p)
      }
    }
    return result
  }

  /** 当前选中节点的上游通道选项（交集 + 保持出现顺序）。
   *  过滤空字符串/None 名字，避免 backend 旧 cache 数据 / 异常 mne info 导致 listbox 出现空行。
   */
  const upstreamChannels = computed<string[]>(() => {
    const node = selectedNode.value
    if (!node) return []
    const loadDataNodes = findAllUpstreamNodesByType(node.id, LOAD_DATA_NODE_TYPE)
    let common: string[] | null = null
    for (const ld of loadDataNodes) {
      for (const info of loadDataSelectedInfos(ld)) {
        const names = (info.ch_names || [])
          .map((n) => (n == null ? '' : String(n).trim()))
          .filter(Boolean)
        if (!names.length) continue
        if (common === null) {
          common = [...names]
        } else {
          const s = new Set(names)
          common = common.filter((c) => s.has(c))
        }
      }
    }
    return common || []
  })

  function getChannelListArray(prop: NodeProperty): string[] {
    const node = selectedNode.value
    if (!node) return []
    const raw = node.params[prop.name]
    if (Array.isArray(raw)) return raw.map((item) => String(item)).filter(Boolean)
    if (typeof raw === 'string' && raw.trim()) {
      return raw.split(',').map((item) => item.trim()).filter(Boolean)
    }
    return []
  }

  function isChannelSelected(prop: NodeProperty, ch: string): boolean {
    return getChannelListArray(prop).includes(ch)
  }

  function setChannelListArray(prop: NodeProperty, channels: string[]) {
    const node = selectedNode.value
    if (!node) return
    // 保持 upstreamChannels 的顺序，避免乱序导致 hash 抖动
    const order = new Map(upstreamChannels.value.map((c, i) => [c, i]))
    const sorted = [...new Set(channels)].sort((a, b) => {
      const ai = order.has(a) ? (order.get(a) as number) : Number.MAX_SAFE_INTEGER
      const bi = order.has(b) ? (order.get(b) as number) : Number.MAX_SAFE_INTEGER
      return ai - bi
    })
    node.params = { ...node.params, [prop.name]: sorted }
    updateLiteGraphNode(node)
    markDirty()
  }

  function toggleChannel(prop: NodeProperty, ch: string) {
    const current = new Set(getChannelListArray(prop))
    if (current.has(ch)) current.delete(ch)
    else current.add(ch)
    setChannelListArray(prop, Array.from(current))
  }

  function selectAllChannels(prop: NodeProperty) {
    setChannelListArray(prop, [...upstreamChannels.value])
  }

  function clearChannels(prop: NodeProperty) {
    setChannelListArray(prop, [])
  }

  function invertChannels(prop: NodeProperty) {
    const cur = new Set(getChannelListArray(prop))
    const inverted = upstreamChannels.value.filter((c) => !cur.has(c))
    setChannelListArray(prop, inverted)
  }

  function filteredChannelOptions(prop: NodeProperty): string[] {
    const q = channelFilterFor(prop).trim().toLowerCase()
    if (!q) return upstreamChannels.value
    return upstreamChannels.value.filter((c) => c.toLowerCase().includes(q))
  }

  // === channel_list listbox 多选交互（与 LoadDataPanel Include 一致） ===
  // 单击 = toggle，按住左键拖过行 = 范围多选，Shift+点击 = 从上次锚点到当前位置范围加入，
  // Ctrl+A = 全选可见，Delete = 移除已选
  //
  // 注：不用 :ref="callback" 拿 DOM，因为 v-if/v-show 切换时 callback 会反复 mount/unmount，
  // 配合 reactive 数据闪烁可能产生异常。focus 改成 click 时从 event.currentTarget.closest 找。

  /** prop key → 上次点击的可见索引（Shift 范围锚点） */
  const channelLastAnchor = reactive<Record<string, number>>({})
  let channelDragKey = ''
  let channelDragStart = -1
  let channelDragBase: Set<string> | null = null
  let channelDragMoved = false
  let suppressChannelClick = false

  function focusChannelListBox(e: MouseEvent) {
    ;(e.currentTarget as HTMLElement | null)
      ?.closest<HTMLElement>('.channel-list__box')
      ?.focus()
  }

  function applyChannelDragRange(prop: NodeProperty, idx: number) {
    const visible = filteredChannelOptions(prop)
    const start = channelDragStart
    if (start < 0) return
    const current = new Set(channelDragBase ?? [])
    const [lo, hi] = [Math.min(start, idx), Math.max(start, idx)]
    for (let i = lo; i <= hi; i++) {
      const item = visible[i]
      if (item) current.add(item)
    }
    setChannelListArray(prop, Array.from(current))
    channelLastAnchor[channelFilterKey(prop)] = idx
  }

  function endChannelDrag() {
    const moved = channelDragMoved
    channelDragKey = ''
    channelDragStart = -1
    channelDragBase = null
    channelDragMoved = false
    window.removeEventListener('mouseup', endChannelDrag)
    if (moved) {
      window.setTimeout(() => { suppressChannelClick = false }, 0)
    }
  }

  function handleChannelListMouseDown(e: MouseEvent, prop: NodeProperty, idx: number) {
    if (e.button !== 0) return
    focusChannelListBox(e)
    channelDragKey = channelFilterKey(prop)
    channelDragStart = idx
    channelDragMoved = false
    suppressChannelClick = false
    channelDragBase = (e.ctrlKey || e.metaKey) ? new Set(getChannelListArray(prop)) : new Set<string>()
    channelLastAnchor[channelDragKey] = idx
    window.addEventListener('mouseup', endChannelDrag)
    e.preventDefault()
  }

  function handleChannelListMouseEnter(e: MouseEvent, prop: NodeProperty, idx: number) {
    const key = channelFilterKey(prop)
    if (!channelDragKey || channelDragKey !== key || channelDragStart < 0 || e.buttons !== 1) return
    if (idx !== channelDragStart) channelDragMoved = true
    suppressChannelClick = channelDragMoved
    applyChannelDragRange(prop, idx)
  }

  function handleChannelListClick(e: MouseEvent, prop: NodeProperty, idx: number, ch: string) {
    if (suppressChannelClick) {
      suppressChannelClick = false
      return
    }
    // focus 父 listbox（按 keydown 监听就在它上面）—— 用 currentTarget 找最近 .channel-list__box
    focusChannelListBox(e)
    const key = channelFilterKey(prop)
    const visible = filteredChannelOptions(prop)
    const lastIdx = channelLastAnchor[key]

    if (e.shiftKey && typeof lastIdx === 'number' && lastIdx >= 0) {
      const current = new Set(getChannelListArray(prop))
      const [start, end] = [Math.min(lastIdx, idx), Math.max(lastIdx, idx)]
      for (let i = start; i <= end; i++) {
        const item = visible[i]
        if (item) current.add(item)
      }
      setChannelListArray(prop, Array.from(current))
    } else {
      toggleChannel(prop, ch)
    }
    channelLastAnchor[key] = idx
  }

  function handleChannelListKeydown(e: KeyboardEvent, prop: NodeProperty) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
      e.preventDefault()
      // 只全选当前过滤后可见的（与文件列表 Ctrl+A 一致）
      const visible = filteredChannelOptions(prop)
      const current = new Set(getChannelListArray(prop))
      for (const ch of visible) current.add(ch)
      setChannelListArray(prop, Array.from(current))
      return
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      // 移除当前已选的所有通道（focused listbox 内）
      if (getChannelListArray(prop).length > 0) {
        e.preventDefault()
        clearChannels(prop)
      }
    }
  }

  return {
    upstreamChannels,
    channelFilterFor,
    setChannelFilter,
    getChannelListArray,
    isChannelSelected,
    selectAllChannels,
    clearChannels,
    invertChannels,
    filteredChannelOptions,
    handleChannelListMouseDown,
    handleChannelListMouseEnter,
    handleChannelListClick,
    handleChannelListKeydown,
  }
}
