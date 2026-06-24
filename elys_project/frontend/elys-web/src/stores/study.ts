import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Study } from '@/types'
import { studyApi } from '@/api/studies'

/**
 * 当前研究项（study）上下文。
 *
 * 容器化后，"当前是哪个 study" 的事实源是 URL 路径参数 `route.params.studyId`，
 * 子页面（工作流/结果/数据/概览）一律从 route.params 读 id，不依赖本 store 是否 load 完，
 * 避免 "store 还没填好、子页已挂载" 的时序空窗。
 *
 * 本 store 只负责**缓存当前研究项的详情对象**（name/status 等），
 * 供容器标题栏和概览页复用，避免每个 tab 各自 studyApi.get。
 */
export const useStudyStore = defineStore('study', () => {
  const currentStudyId = ref<string>('')
  const currentStudy = ref<Study | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const hasStudy = computed(() => !!currentStudyId.value)
  // id 对齐才算 loaded，防切换瞬间拿到上一个 study 的详情
  const isStudyLoaded = computed(
    () => !!currentStudy.value && currentStudy.value.id === currentStudyId.value,
  )

  /** 设置当前 study id（容器 route.params 变化时调用）。只改 id，不自动拉详情。 */
  function setCurrent(id: string) {
    if (id === currentStudyId.value) return
    currentStudyId.value = id
    // 切到新 study 时丢弃旧详情，避免标题/概览短暂显示上一个
    if (currentStudy.value && currentStudy.value.id !== id) currentStudy.value = null
  }

  /** 拉取 currentStudyId 对应的详情。幂等：已加载且对齐则跳过（tab 间切换不重复请求）。 */
  async function loadStudy(id?: string): Promise<void> {
    const target = id ?? currentStudyId.value
    if (!target) return
    if (id && id !== currentStudyId.value) setCurrent(id)
    if (isStudyLoaded.value && currentStudy.value!.id === target) return
    loading.value = true
    error.value = null
    try {
      const res = await studyApi.get(target)
      if (currentStudyId.value === target) currentStudy.value = res.data // 防竞态：只认最新目标
    } catch (err: any) {
      if (currentStudyId.value === target) {
        error.value = err?.response?.data?.detail || '研究项加载失败'
      }
    } finally {
      if (currentStudyId.value === target) loading.value = false
    }
  }

  /** 离开容器时清空内存上下文。 */
  function reset() {
    currentStudyId.value = ''
    currentStudy.value = null
    loading.value = false
    error.value = null
  }

  return {
    currentStudyId,
    currentStudy,
    loading,
    error,
    hasStudy,
    isStudyLoaded,
    setCurrent,
    loadStudy,
    reset,
  }
})
