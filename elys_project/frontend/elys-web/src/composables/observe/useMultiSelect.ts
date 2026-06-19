// 通用列表多选（观察页选择器共用）：单击单选 · Ctrl/⌘ 加选切换 · Shift 连选 [锚点..当前]。
// 时域/PSD/TFR 的「段(条件/数据集)」「通道」选择器都走它——消灭三处重复的 onSegClick/onChanClick。
// 按列表「索引」做连选，按「键身份」去重（段用索引号、通道用名字）。
import { ref, type Ref } from 'vue'

export interface MultiSelect<K> {
  /** 当前选中的键集合（响应式）。 */
  selected: Ref<Set<K>>
  /** Shift 连选锚点（列表索引）。 */
  anchor: Ref<number | null>
  /** 列表项点击：i=列表索引，e 带 shift/ctrl/meta 修饰。 */
  onClick: (index: number, e: MouseEvent) => void
  selectAll: () => void
  selectNone: () => void
  /** 直接置入一组键（如默认前 N 个）。 */
  set: (keys: K[]) => void
}

// keys 用 getter（兼容 ref / computed，规避 computed.value 只读与 Ref 的型变冲突）。
export function useMultiSelect<K>(keys: () => K[], initial: K[] = []): MultiSelect<K> {
  const selected = ref<Set<K>>(new Set(initial)) as Ref<Set<K>>
  const anchor = ref<number | null>(null)

  function onClick(index: number, e: MouseEvent) {
    const arr = keys()
    const k = arr[index]
    if (k === undefined) return
    // Shift 连选：锚点到当前的闭区间
    if (e.shiftKey) {
      let anchorIdx = anchor.value
      // anchor 未设置时（页面刚打开、首次 shift+click），从当前选中集里取第一个选中项的索引作为 fallback 锚点
      if (anchorIdx == null && selected.value.size > 0) {
        const firstSel = [...selected.value][0]
        const fi = arr.findIndex((k) => k === firstSel)
        if (fi >= 0) anchorIdx = fi
      }
      if (anchorIdx != null) {
        const lo = Math.min(anchorIdx, index)
        const hi = Math.max(anchorIdx, index)
        const s = new Set<K>()
        for (let j = lo; j <= hi; j++) {
          const kk = arr[j]
          if (kk !== undefined) s.add(kk)
        }
        selected.value = s
        return
      }
    }
    // Ctrl/⌘ 加选切换：至少留一个
    if (e.ctrlKey || e.metaKey) {
      const s = new Set(selected.value)
      if (s.has(k)) s.delete(k)
      else s.add(k)
      if (!s.size) s.add(k)
      selected.value = s
      anchor.value = index
      return
    }
    // 普通单击：单选
    selected.value = new Set([k])
    anchor.value = index
  }

  function selectAll() {
    selected.value = new Set(keys())
  }
  function selectNone() {
    selected.value = new Set()
  }
  function set(ks: K[]) {
    selected.value = new Set(ks)
  }

  return { selected, anchor, onClick, selectAll, selectNone, set }
}
