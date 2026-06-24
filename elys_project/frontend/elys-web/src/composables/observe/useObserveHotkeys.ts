// 观察/分析五视图（时域/频域/时频/ICA/去伪迹）共用的键盘快捷键引擎。
// 设计要点（见方案）：
// - 输入框守卫：焦点在 input/textarea/select/contenteditable/[role=textbox] 或中文合成态时，单键不触发（带 Ctrl/⌘ 的组合键可穿透）。
// - def 元数据驱动：一份 HotkeyDef[] 既注册键、又渲染「? 速查卡」（按分组）。
// - 条件键 when()：不满足时静默吞键，不误触（如焦点仅多曲线重叠时可用）。
// - Esc 分层退一步：escLayers 按序尝试，首个返 true 即停（一次只退一级）；输入框内放行原生（失焦）。
// - ? 唤出/关闭速查卡（实为 Shift+/）。
// 注：window 级监听，onUnmounted 必解绑（本仓库有重挂闭包过期前例）。
import { onMounted, onUnmounted, ref, computed } from 'vue'

export type HotkeyGroup = 'nav' | 'zoom' | 'mark' | 'view' | 'general'

export interface HotkeyDef {
  /** 规范化键：单键小写 'f'；组合 'Ctrl+Enter' / 'Shift+ArrowLeft'；方向键 'ArrowLeft' 等。 */
  key: string
  /** 速查卡文案。 */
  label: string
  group: HotkeyGroup
  /** 条件键：返回 false 时静默吞键（不触发、也不在速查卡显示）。 */
  when?: () => boolean
  /** 命中后执行。 */
  run: (e: KeyboardEvent) => void
  /** 默认 true（命中即 preventDefault）。 */
  preventDefault?: boolean
}

const GROUP_LABEL: Record<HotkeyGroup, string> = {
  nav: '导航',
  zoom: '缩放',
  mark: '标记',
  view: '视图',
  general: '通用',
}

/** 焦点是否落在「正在输入」的元素上——单键快捷应让位。 */
export function isTypingTarget(el: EventTarget | null): boolean {
  const t = el as HTMLElement | null
  if (!t || !t.tagName) return false
  const tag = t.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (t.isContentEditable) return true
  if (t.getAttribute?.('role') === 'textbox') return true
  return false
}

/** KeyboardEvent → 'Ctrl+Shift+ArrowLeft' / 'f' / 'Ctrl+Enter' 形式（单字符键统一小写）。 */
function comboOf(e: KeyboardEvent): string {
  const parts: string[] = []
  if (e.ctrlKey || e.metaKey) parts.push('Ctrl')
  if (e.shiftKey) parts.push('Shift')
  if (e.altKey) parts.push('Alt')
  let k = e.key
  if (k.length === 1) k = k.toLowerCase()
  parts.push(k)
  return parts.join('+')
}

export function useObserveHotkeys(
  getDefs: () => HotkeyDef[],
  opts: { escLayers?: Array<() => boolean> } = {},
) {
  const helpOpen = ref(false)

  function onKeydown(e: KeyboardEvent) {
    if (e.isComposing || e.keyCode === 229) return // 中文合成态：放行
    const typing = isTypingTarget(e.target)

    // Esc：输入框内放行原生（失焦/取消编辑）；否则逐级退一步
    if (e.key === 'Escape') {
      if (typing) return
      if (helpOpen.value) { helpOpen.value = false; e.preventDefault(); return }
      for (const layer of opts.escLayers ?? []) {
        if (layer()) { e.preventDefault(); return }
      }
      return
    }

    // ? 速查卡（Shift+/ → e.key '?'）
    if (e.key === '?' && !typing) { helpOpen.value = !helpOpen.value; e.preventDefault(); return }

    // 输入框内：仅放行带 Ctrl/⌘ 的组合键（不与打字冲突），单键吞回给输入框
    if (typing && !(e.ctrlKey || e.metaKey)) return

    const combo = comboOf(e)
    for (const d of getDefs()) {
      if (d.key !== combo) continue
      if (d.when && !d.when()) continue // 条件不满足 → 跳过本绑定，继续匹配后续同键绑定
      if (d.preventDefault !== false) e.preventDefault()
      d.run(e)
      return
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))

  // 速查卡分组（只列当前可用的键：when() 非 false）
  const helpGroups = computed(() => {
    const order: HotkeyGroup[] = ['nav', 'zoom', 'mark', 'view', 'general']
    return order
      .map((g) => ({
        group: g,
        title: GROUP_LABEL[g],
        items: getDefs().filter((d) => d.group === g && d.when?.() !== false),
      }))
      .filter((s) => s.items.length > 0)
  })

  return { helpOpen, helpGroups }
}
