// 点击元素外部时回调（观察页下拉收口用）：配色/色卡下拉是就地展开的手风琴，
// 点击页面别处理应收起。用捕获阶段 mousedown，先于各处 click 触发、收得干脆；
// 不 preventDefault / 不 stopPropagation，故画布拖拽框选等原有手势不受影响。
import { onMounted, onUnmounted, type Ref } from 'vue'

export function useClickOutside(el: Ref<HTMLElement | null>, onOutside: () => void) {
  function onDocMouseDown(e: MouseEvent) {
    const target = e.target as Node | null
    if (el.value && target && !el.value.contains(target)) onOutside()
  }
  onMounted(() => document.addEventListener('mousedown', onDocMouseDown, true))
  onUnmounted(() => document.removeEventListener('mousedown', onDocMouseDown, true))
}
