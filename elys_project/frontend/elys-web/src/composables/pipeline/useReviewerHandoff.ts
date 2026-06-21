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
    // 1) 提交决策（关键落库，必须成功）
    try {
      await api.post(`${base}/decision`, { ...ctx.buildBody(), decision_version: ctx.decisionVersion() })
    } catch (err) {
      applyError.value = true
      applyMsg.value = '提交失败：' + describeError(err)
      applying.value = false
      return
    }
    // 2) 续跑（同步端点，跑完才返回）。不再吞错——失败 / 节点没被推进，都要明示而不是默默回到「等待确认」。
    //    resume 返回该节点最新 job：status 仍是 waiting_user_input = 续跑没真正应用决策（后端问题），留在本页报明。
    try {
      const resp = await api.post<{ job?: { status?: string } }>(`${base}/resume`, {})
      if (resp?.data?.job?.status === 'waiting_user_input') {
        applyError.value = true
        applyMsg.value = '已提交，但节点仍停在「等待确认」——续跑未推进该节点（请截图反馈）。'
        applying.value = false
        return
      }
    } catch (err) {
      applyError.value = true
      applyMsg.value = '已提交，但续跑失败：' + describeError(err)
      applying.value = false
      return
    }
    applying.value = false
    applyDone.value = true
    applyMsg.value = `已提交${ctx.summary ? '（' + ctx.summary() + '）' : ''}，正在返回工作流…`
    // 3) 旗标通知工作流页：返回后强制按 id 重载该执行的运行态——覆盖「keep-alive 陈旧态」与
    //    「跳顶级路由后工作区重挂、activeExecutionId 丢失」两种情况，确保看到续跑后的新状态。
    try {
      sessionStorage.setItem('elys:reviewer-applied', JSON.stringify({ executionId: ctx.executionId, at: Date.now() }))
    } catch {
      /* 隐私模式禁用 storage：忽略，退回工作流页常规刷新 */
    }
    returnToPipeline()
  }

  return { applying, applyDone, applyMsg, applyError, describeError, submitAndReturn, returnToPipeline }
}
