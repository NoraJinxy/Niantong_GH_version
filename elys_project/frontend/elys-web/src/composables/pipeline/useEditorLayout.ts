// 工作流编辑器 · 抽屉式布局（左侧节点库 + 右侧检查器）
//
// 从 PipelinePage.vue 抽出的布局状态与交互：抽屉显隐 / 拖拽改宽 / 固定 / Esc 快捷键。
// 完全自包含——只读写自身 6 个布局状态 + localStorage，不依赖任何 pipeline 业务状态。
// 事件监听的注册 / 注销仍由 PipelinePage 的生命周期钩子负责（本模块只提供同一个 handler 引用）。

import { ref } from 'vue'
import { LAYOUT_LS_PREFIX } from './pipelineConstants'

export function useEditorLayout() {
  const libraryVisible = ref(true)
  const libraryWidth = ref(240)
  const inspectorVisible = ref(false)
  const inspectorWidth = ref(580)
  const inspectorPinned = ref(false)
  const drawerDragging = ref<'library' | 'inspector' | null>(null)

  let _drawerDragStartX = 0
  let _drawerDragStartWidth = 0

  function restoreLayoutState() {
    try {
      const lv = localStorage.getItem(LAYOUT_LS_PREFIX + 'library-visible')
      const lw = parseInt(localStorage.getItem(LAYOUT_LS_PREFIX + 'library-width') || '0', 10)
      const iw = parseInt(localStorage.getItem(LAYOUT_LS_PREFIX + 'inspector-width') || '0', 10)
      const ip = localStorage.getItem(LAYOUT_LS_PREFIX + 'inspector-pinned')

      if (lv !== null) libraryVisible.value = lv !== 'false'
      if (lw >= 180 && lw <= 400) libraryWidth.value = lw
      if (iw >= 320 && iw <= 800) inspectorWidth.value = iw
      if (ip === 'true') {
        inspectorPinned.value = true
        inspectorVisible.value = true
      }
    } catch {
      // localStorage 不可用时使用默认值
    }
  }

  function persistLayout(key: string, value: string) {
    try {
      localStorage.setItem(LAYOUT_LS_PREFIX + key, value)
    } catch {
      // 忽略 localStorage 失败
    }
  }

  function toggleLibrary() {
    libraryVisible.value = !libraryVisible.value
    persistLayout('library-visible', String(libraryVisible.value))
  }

  function toggleInspector() {
    if (inspectorVisible.value) {
      inspectorVisible.value = false
    } else {
      inspectorVisible.value = true
    }
  }

  function showInspector() {
    inspectorVisible.value = true
  }

  function hideInspector() {
    if (inspectorPinned.value) return
    inspectorVisible.value = false
  }

  function forceCloseInspector() {
    inspectorVisible.value = false
    if (inspectorPinned.value) {
      inspectorPinned.value = false
      persistLayout('inspector-pinned', 'false')
    }
  }

  function toggleInspectorPin() {
    inspectorPinned.value = !inspectorPinned.value
    persistLayout('inspector-pinned', String(inspectorPinned.value))
  }

  function startDrawerDrag(which: 'library' | 'inspector', e: MouseEvent) {
    drawerDragging.value = which
    _drawerDragStartX = e.clientX
    _drawerDragStartWidth = which === 'library' ? libraryWidth.value : inspectorWidth.value
    document.body.style.cursor = 'ew-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onDrawerDragMove)
    document.addEventListener('mouseup', onDrawerDragEnd)
    e.preventDefault()
  }

  function onDrawerDragMove(e: MouseEvent) {
    if (!drawerDragging.value) return
    const dx = e.clientX - _drawerDragStartX
    if (drawerDragging.value === 'library') {
      libraryWidth.value = Math.max(180, Math.min(400, _drawerDragStartWidth + dx))
    } else {
      inspectorWidth.value = Math.max(320, Math.min(800, _drawerDragStartWidth - dx))
    }
  }

  function onDrawerDragEnd() {
    if (!drawerDragging.value) return
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    if (drawerDragging.value === 'library') {
      persistLayout('library-width', String(libraryWidth.value))
    } else {
      persistLayout('inspector-width', String(inspectorWidth.value))
    }
    drawerDragging.value = null
    document.removeEventListener('mousemove', onDrawerDragMove)
    document.removeEventListener('mouseup', onDrawerDragEnd)
  }

  function handleLayoutKeydown(e: KeyboardEvent) {
    if (e.key !== 'Escape' || !inspectorVisible.value) return
    const target = e.target as HTMLElement | null
    const tag = target?.tagName?.toLowerCase()
    if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return
    forceCloseInspector()
  }

  return {
    libraryVisible,
    libraryWidth,
    inspectorVisible,
    inspectorWidth,
    inspectorPinned,
    drawerDragging,
    restoreLayoutState,
    persistLayout,
    toggleLibrary,
    toggleInspector,
    showInspector,
    hideInspector,
    forceCloseInspector,
    toggleInspectorPin,
    startDrawerDrag,
    onDrawerDragMove,
    onDrawerDragEnd,
    handleLayoutKeydown,
  }
}
