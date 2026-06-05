/**
 * 跨页面记住"当前 Study"的轻量工具。
 * 用 sessionStorage(浏览器关掉就清,避免污染长期状态)。
 *
 * 典型用法:
 * - 任何选择了 study 的页面 → setCurrentStudyId(id)
 * - 任何需要兜底 study 的页面 → getCurrentStudyId()
 *
 * 多页面统一选择优先级:URL ?study_id= > sessionStorage > studies[0]
 */

const STORAGE_KEY = 'elys.currentStudyId'

export function getCurrentStudyId(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function setCurrentStudyId(id: string | null | undefined): void {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* sessionStorage 不可用时静默忽略 */
  }
}
