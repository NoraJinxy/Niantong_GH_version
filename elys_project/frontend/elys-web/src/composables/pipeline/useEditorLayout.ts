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
  // 拖动时直接操作面板 DOM，绕过 Vue nextTick
  // library 手柄用 _dragHandleEl 同步位置；inspector 手柄已移入 inspector 内部，随面板自动跟手，无需单独更新
  let _dragHandleEl: HTMLElement | null = null
  let _dragPanelEl: HTMLElement | null = null
  // 指针捕获句柄：拖拽期间锁定收事件的手柄元素 + pointerId（onDrawerDragEnd 释放）
  let _dragPointerHandle: HTMLElement | null = null
  let _dragPointerId: number | null = null

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

  function startDrawerDrag(which: 'library' | 'inspector', e: PointerEvent) {
    drawerDragging.value = which
    _drawerDragStartX = e.clientX
    _drawerDragStartWidth = which === 'library' ? libraryWidth.value : inspectorWidth.value
    // 缓存面板 DOM 供直接操作；inspector 手柄已在面板内部，自动跟手，无需缓存
    const handle = e.currentTarget as HTMLElement | null
    const root = handle?.closest('.pipeline-page') as HTMLElement | null
    if (root) {
      _dragHandleEl = which === 'library'
        ? root.querySelector<HTMLElement>('.drawer-handle--seam-left')
        : null
      _dragPanelEl = root.querySelector<HTMLElement>(which === 'library' ? '.library' : '.inspector')
    }
    // 指针捕获：把后续 pointermove / pointerup 一律锁定派发到手柄本身。
    // 即使光标移到中间 litegraph 画布上空、或越出窗口边界，也保证收得到「松手」——
    // 根治右栏「松手后拖拽不结束、光标卡在 ew-resize 双箭头」（右栏加宽要向左拖、易划过画布，最常踩）。
    if (handle) {
      try {
        handle.setPointerCapture(e.pointerId)
        _dragPointerHandle = handle
        _dragPointerId = e.pointerId
      } catch {
        // 个别环境不支持指针捕获，降级到下面的 document 监听仍可用
      }
    }
    document.body.style.cursor = 'ew-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('pointermove', onDrawerDragMove)
    document.addEventListener('pointerup', onDrawerDragEnd)
    document.addEventListener('pointercancel', onDrawerDragEnd)
    e.preventDefault()
  }

  function onDrawerDragMove(e: PointerEvent) {
    if (!drawerDragging.value) return
    const isLibrary = drawerDragging.value === 'library'
    // 左栏向右拖变宽(+dx)，右栏向左拖变宽(−dx)
    const dx = e.clientX - _drawerDragStartX
    const rawW = isLibrary ? _drawerDragStartWidth + dx : _drawerDragStartWidth - dx
    const minW = isLibrary ? 180 : 320
    const maxW = isLibrary ? 400 : 800
    const newW = Math.max(minW, Math.min(maxW, rawW))

    // 手柄严格跟随光标（gap=0），撞到上下限即停在边界——标准 resize 手感（VSCode/Figma 同款）。
    // 注：早先为「消死区」加过撞界重置锚点，但实测会让手柄与光标产生恒定偏移、反向拖时手柄飘在
    // 光标前方更难抓（右栏 max 800 量程大、易过冲，偏移最明显——正是右栏手感怪的真凶），故移除。

    if (isLibrary) {
      libraryWidth.value = newW
      // 直接写 DOM，不等 Vue nextTick，手柄与面板同帧更新
      if (_dragHandleEl) _dragHandleEl.style.left = newW + 'px'
      if (_dragPanelEl) _dragPanelEl.style.width = newW + 'px'
    } else {
      // inspector 手柄在面板内部、随面板左缘自动跟手，无需单独写 DOM
      inspectorWidth.value = newW
      if (_dragPanelEl) _dragPanelEl.style.width = newW + 'px'
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
    _dragHandleEl = null
    _dragPanelEl = null
    if (_dragPointerHandle && _dragPointerId !== null) {
      try { _dragPointerHandle.releasePointerCapture(_dragPointerId) } catch { /* 已随 pointerup 自动释放 */ }
    }
    _dragPointerHandle = null
    _dragPointerId = null
    document.removeEventListener('pointermove', onDrawerDragMove)
    document.removeEventListener('pointerup', onDrawerDragEnd)
    document.removeEventListener('pointercancel', onDrawerDragEnd)
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
