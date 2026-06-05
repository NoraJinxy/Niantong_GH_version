import type { DashboardSummaryResponse } from '@/types'
import { api } from './client'

export const dashboardApi = {
  summary: () => api.get<DashboardSummaryResponse>('/dashboard/summary'),
}
