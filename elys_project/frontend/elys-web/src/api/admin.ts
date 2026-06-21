import type {
  AdminAuditEventsResponse,
  AdminAuditFacets,
  AdminOverviewResponse,
  AdminRuntimeResponse,
} from '@/types'
import { api } from './client'

export interface AdminAuditQuery {
  action?: string
  actor_id?: string
  resource_kind?: string
  study_id?: string
  since?: string
  until?: string
  limit?: number
  offset?: number
}

export const adminApi = {
  overview: () => api.get<AdminOverviewResponse>('/admin/overview'),
  runtime: () => api.get<AdminRuntimeResponse>('/admin/runtime'),
  auditEvents: (params: AdminAuditQuery = {}) =>
    api.get<AdminAuditEventsResponse>('/admin/audit-events', { params }),
  auditFacets: () => api.get<AdminAuditFacets>('/admin/audit-events/facets'),
}
