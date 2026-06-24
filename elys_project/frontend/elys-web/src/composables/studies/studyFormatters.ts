// 研究项（Study）域的展示格式化：状态标签 / 状态 tone / 成员角色标签。
// 此前散在 Dashboard.statusLabel、StudiesPage.statusLabel+roleLabel、StudyOverviewTab.roleLabel，
// 收成一份，避免「活跃/已归档」与角色名各页漂移。
import type { StatusTone } from '@/composables/common/statusTone'

export function studyStatusLabel(status?: string | null): string {
  const labels: Record<string, string> = {
    active: '活跃',
    archived: '已归档',
    trashed: '回收站',
    deleted: '已删除',
  }
  return (status && labels[status]) || status || '未知'
}

export function studyStatusTone(status?: string | null): StatusTone {
  if (status === 'active') return 'success'
  if (status === 'trashed' || status === 'deleted') return 'danger'
  return 'muted'
}

export function studyRoleLabel(role?: string | null): string {
  if (!role) return '未同步'
  const labels: Record<string, string> = {
    owner: '负责人',
    admin: '管理员',
    editor: '编辑',
    viewer: '查看',
    pi: 'PI',
  }
  return labels[role] || role
}
