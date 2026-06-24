// 多产物观察页（时域 / 频域 / 时频）共用：挂载时取各 study_output 的「轻量元数据」，
// 让数据集选择器在「加载重绘图数据之前」就显示真名（被试 · 条件），而非退化的「数据集 N」。
// 名字本来只能从已加载的绘图响应里取，而页面默认只加载第 1 个数据集 → 其余一直是「数据集 N」。
import { pipelineApi } from '@/api/pipelines'
import { fmtSubject } from './observeUtils'

/**
 * 并发取 outputIds 各自的元数据，把「被试 · 条件 / display_name」写进 into[index]（index 与 outputIds 对齐）。
 * best-effort：取不到的项静默跳过（segLabel 自行退回「数据集 N」）；已有值不覆盖（已加载数据填的更准）。
 */
export async function loadOutputLabels(
  studyId: string,
  outputIds: string[],
  into: Record<number, string>,
): Promise<void> {
  if (!studyId || outputIds.length < 2) return
  await Promise.allSettled(
    outputIds.map(async (id, i) => {
      if (into[i]) return
      const { data } = await pipelineApi.getStudyOutput(studyId, id)
      const label =
        [fmtSubject(data.bids_subject_id), data.condition || ''].filter(Boolean).join(' · ') ||
        data.display_name ||
        ''
      if (label) into[i] = label
    }),
  )
}
