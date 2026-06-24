import type {
  AdminAuditEventsResponse,
  AdminAuditFacets,
  AdminHealthResponse,
  AdminOverviewResponse,
  AdminRuntimeResponse,
  AdminSystemResponse,
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
  health: () => api.get<AdminHealthResponse>('/admin/health'),
  runtime: () => api.get<AdminRuntimeResponse>('/admin/runtime'),
  system: () => api.get<AdminSystemResponse>('/admin/system'),
  auditEvents: (params: AdminAuditQuery = {}) =>
    api.get<AdminAuditEventsResponse>('/admin/audit-events', { params }),
  auditFacets: () => api.get<AdminAuditFacets>('/admin/audit-events/facets'),
}
