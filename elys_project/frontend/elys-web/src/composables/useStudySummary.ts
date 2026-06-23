import { ref } from 'vue'
import { studyApi } from '@/api/studies'
import type { StudySummaryResponse } from '@/types'

/**
 * 研究项概览聚合数据。
 *
 * 概览 tab 需要一次性展示 数据/工作流/运行/结果 全貌。容器化前这是前端并发拼
 * 约 12 个请求（N+1）；现统一走后端 `GET /studies/{id}/summary` 一次返回，
 * 消除 N+1 与 EXECUTION_PIPELINE_LIMIT 截断导致的计数失真。
 */
export function useStudySummary() {
  const summary = ref<StudySummaryResponse | null>(null)
  const loading = ref(false)
  const error = ref('')
  let latestToken = 0

  async function load(studyId: string): Promise<void> {
    if (!studyId) return
    const token = ++latestToken
    loading.value = true
    error.value = ''
    try {
      const res = await studyApi.summary(studyId)
      if (token === latestToken) summary.value = res.data // 防竞态：只认最新请求
    } catch (err: any) {
      if (token === latestToken) {
        error.value = err?.response?.data?.detail || '研究项概览加载失败'
        summary.value = null
      }
    } finally {
      if (token === latestToken) loading.value = false
    }
  }

  return { summary, loading, error, load }
}
