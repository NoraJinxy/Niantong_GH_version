// 交互审核台（伪迹 ArtifactMark / ICA Apply）共用的「应用并返回」收尾。
//
// 路线 B（同页导航）：审核台由 PipelinePage 用 router.push 同标签打开，本 composable 负责
//   提交 decision → 续跑(resume) → router.back() 回到工作流页；以及「取消/返回（不提交）」。
// decision body 因节点而异（ICA: excluded_components；Artifact: bad_segments/bad_channels/channel_action），
//   用 buildBody 回调注入，其余链路（提交+续跑+返回+状态+错误格式化）两页完全一致。
//
// 注：resume 当前是同步端点（后端 inline 跑完续跑才返回），故 await 之以保证返回工作流时执行态已推进、
//   PipelinePage onActivated 一刷即见最终态、不踩「刚 fire 还没翻 waiting」的竞态。后续可改异步 resume 提速。

import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'

export interface ReviewerHandoffCtx {
  studyId: string
  executionId: string
  jobId: string
  /** 当前 decision 版本（ICA 来自 query 常量，Artifact 来自 /interaction 回拉的 ref）。 */
  decisionVersion: () => number
  /** 该节点的 decision 主体（不含 decision_version，由本 composable 补上）。 */
  buildBody: () => Record<string, unknown>
  /** 提示文案里的「已提交（…）」摘要，可选。 */
  summary?: () => string
}

export function useReviewerHandoff(ctx: ReviewerHandoffCtx) {
  const router = useRouter()
  const applying = ref(false)
  const applyDone = ref(false)
  const applyMsg = ref('')
  const applyError = ref(false)

  function describeError(err: unknown, fallback = '操作失败'): string {
    const e = err as { response?: { data?: { detail?: { message?: string } | string } }; message?: string }
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message) return detail.message
    return e?.message || fallback
  }

  // 返回工作流：同标签 router.push 打开 → 回上一页（PipelinePage，keep-alive 缓存还在）；
  // 无历史（用户刷新/直接打开审核台 URL）→ 兜底回根，避免 router.back 卡在空历史。
  function returnToPipeline() {
    if (window.history.length > 1) router.back()
    else void router.push('/')
  }

  async function submitAndReturn(): Promise<void> {
    applying.value = true
    applyMsg.value = ''
    applyError.value = false
    const base = `/studies/${ctx.studyId}/pipeline-executions/${ctx.executionId}/jobs/${ctx.jobId}`
    try {
      // 1) 提交决策（关键落库，必须成功）
      await api.post(`${base}/decision`, { ...ctx.buildBody(), decision_version: ctx.decisionVersion() })
      // 2) 续跑（best-effort）：失败也已落库，回工作流可再「继续运行」，不挡返回
      try {
        await api.post(`${base}/resume`, {})
      } catch {
        /* 续跑失败：decision 已落库，工作流页可补触发；不阻断返回 */
      }
      applyDone.value = true
      applyMsg.value = `已提交${ctx.summary ? '（' + ctx.summary() + '）' : ''}，正在返回工作流…`
      // 3) 回工作流页（执行态已随 resume 推进，PipelinePage onActivated 会刷新看到续跑）
      returnToPipeline()
    } catch (err) {
      applyError.value = true
      applyMsg.value = describeError(err, '提交失败')
    } finally {
      applying.value = false
    }
  }

  return { applying, applyDone, applyMsg, applyError, describeError, submitAndReturn, returnToPipeline }
}
