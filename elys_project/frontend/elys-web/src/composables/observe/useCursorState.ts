// 游标三态（观察页画布共用）：idle 空闲 / follow 跟随鼠标 / locked 锁定（双击锁定、右键解锁）。
// 显示读数：锁定时取锁定值（冻结），否则取实时悬停值。x 单位/格式化由调用方注入（时域=ms/s、PSD=Hz、TFR=s）。
import { computed, ref, type Ref, type ComputedRef } from 'vue'

export interface CursorReadout<I = unknown> {
  x: number
  items: I[]
}

export interface CursorState<I> {
  cursorReadout: Ref<CursorReadout<I> | null>
  cursorLocked: Ref<boolean>
  lockedReadout: Ref<CursorReadout<I> | null>
  /** 锁定时=锁定值，否则=实时悬停值。 */
  displayReadout: ComputedRef<CursorReadout<I> | null>
  cursorState: ComputedRef<'idle' | 'follow' | 'locked'>
  cursorStateText: ComputedRef<string>
  cursorStateHint: ComputedRef<string>
  /** 画布 @cursor 事件入口。 */
  onCursor: (p: CursorReadout<I> | null) => void
  /** 画布 @lock 事件入口（双击）。 */
  onLock: (p: CursorReadout<I>) => void
  /** 画布 @unlock 事件入口（右键）。 */
  onUnlock: () => void
}

export function useCursorState<I = unknown>(opts: {
  fmtX: (x: number) => number | string
  xUnit: () => string
}): CursorState<I> {
  // as 断言钉死：ref() 会把泛型 I 包成 UnwrapRefSimple<I>，与接口 Ref<CursorReadout<I>> 型变冲突（同 useMultiSelect）
  const cursorReadout = ref<CursorReadout<I> | null>(null) as Ref<CursorReadout<I> | null>
  const cursorLocked = ref(false)
  const lockedReadout = ref<CursorReadout<I> | null>(null) as Ref<CursorReadout<I> | null>

  const displayReadout = computed(() => (cursorLocked.value ? lockedReadout.value : cursorReadout.value))
  const cursorState = computed<'idle' | 'follow' | 'locked'>(() =>
    cursorLocked.value ? 'locked' : cursorReadout.value ? 'follow' : 'idle',
  )
  const cursorStateText = computed(() =>
    cursorState.value === 'locked' ? '游标锁定' : cursorState.value === 'follow' ? '游标跟随' : '游标空闲',
  )
  const cursorStateHint = computed(() =>
    cursorState.value === 'locked'
      ? `锁定 @ ${opts.fmtX(lockedReadout.value?.x ?? 0)}${opts.xUnit()} · 右键解锁`
      : cursorState.value === 'follow'
        ? '双击锁定游标'
        : '悬停曲线查看瞬时值，双击锁定',
  )

  function onCursor(p: CursorReadout<I> | null) {
    cursorReadout.value = p
  }
  function onLock(p: CursorReadout<I>) {
    cursorLocked.value = true
    lockedReadout.value = p
  }
  function onUnlock() {
    cursorLocked.value = false
    lockedReadout.value = null
    cursorReadout.value = null
  }

  return {
    cursorReadout,
    cursorLocked,
    lockedReadout,
    displayReadout,
    cursorState,
    cursorStateText,
    cursorStateHint,
    onCursor,
    onLock,
    onUnlock,
  }
}
