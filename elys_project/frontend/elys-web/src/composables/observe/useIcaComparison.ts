// ICA 成分审核：整体去除前后对比的「实时预览」编排。
// 设计参照 Niantong Interact_ICA.js：勾选成分组合 → 防抖请求后端 → 拿某通道去除前后波形 →
// 过期检查（请求序号）丢弃迟到的旧响应，避免快速连点时旧结果覆盖新结果。
// 后端：GET /studies/{study}/outputs/{output}/ica-components/preview（轻量，只算对比波形 + 方差降幅）。
import { ref, watch, type Ref } from 'vue'
import { dataApi } from '@/api/client'

export interface IcaPreview {
  has_comparison: boolean
  channel_name?: string
  channel_index?: number
  components_removed?: number[]
  variance_reduction?: number
  times?: number[]
  original?: number[]
  filtered?: number[]
  message?: string
}

export function useIcaComparison(studyId: Ref<string>, outputId: Ref<string>, isLive: () => boolean) {
  // 当前标记要剔除的成分集合——本 composable 是「剔除清单」的唯一事实源，页面其余派生量都从这里来。
  const excludedSet = ref<Set<number>>(new Set())
  const preview = ref<IcaPreview | null>(null)
  const previewLoading = ref(false)
  const channel = ref<string>('') // '' = 让后端取首通道
  const maxSeconds = ref<number>(10)

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let reqSeq = 0 // 请求序号：响应回来时若已不是最新一发，丢弃（防旧覆盖新）

  function setExcluded(next: Set<number>) {
    excludedSet.value = next
    schedule()
  }
  function toggle(index: number) {
    const next = new Set(excludedSet.value)
    if (next.has(index)) next.delete(index)
    else next.add(index)
    setExcluded(next)
  }
  function clearExcluded() {
    setExcluded(new Set())
  }

  function schedule(delay = 300) {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(fetchPreview, Math.max(0, delay))
  }

  async function fetchPreview() {
    if (!isLive()) return
    // 空剔除集也请求：后端返回该通道的原始信号（去除后=原始，蓝灰重合），
    // 让用户一进来就看到原始波形作参照，而非空白。勾选成分后蓝线才分离。
    const seq = ++reqSeq
    previewLoading.value = true
    try {
      const res = await dataApi.get<IcaPreview>(
        `/studies/${studyId.value}/outputs/${outputId.value}/ica-components/preview`,
        {
          params: {
            excluded: [...excludedSet.value].sort((a, b) => a - b).join(','),
            channel: channel.value || undefined,
            max_seconds: maxSeconds.value,
          },
        },
      )
      if (seq !== reqSeq) return // 过期响应，丢弃
      preview.value = res.data
    } catch {
      if (seq === reqSeq) preview.value = null
    } finally {
      if (seq === reqSeq) previewLoading.value = false
    }
  }

  // 切通道 / 切时窗 → 立即重取（无需等防抖，这是显式操作）
  watch([channel, maxSeconds], () => schedule(0))

  return {
    excludedSet,
    preview,
    previewLoading,
    channel,
    maxSeconds,
    toggle,
    setExcluded,
    clearExcluded,
    refresh: () => schedule(0),
  }
}
