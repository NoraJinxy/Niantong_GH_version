import type {
  CreateStudyRequest,
  Study,
  StudyActionResponse,
  StudyListResponse,
  StudyMember,
  StudyMemberListResponse,
  StudyMemberUpsertRequest,
  StudySummaryResponse,
} from '@/types'
import { api } from './client'

export const studyApi = {
  list: () => api.get<StudyListResponse>('/studies'),
  get: (studyId: string) => api.get<Study>(`/studies/${studyId}`),
  summary: (studyId: string) => api.get<StudySummaryResponse>(`/studies/${studyId}/summary`),
  listTrash: () => api.get<StudyListResponse>('/studies/trash'),
  create: (data: CreateStudyRequest) => api.post<Study>('/studies', data),
  trash: (studyId: string, reason?: string) =>
    api.delete<StudyActionResponse>(`/studies/${studyId}`, { data: { reason } }),
  restore: (studyId: string) =>
    api.post<StudyActionResponse>(`/studies/${studyId}/restore`),
  purge: (studyId: string, confirmStudyId: string) =>
    api.delete<StudyActionResponse>(`/studies/${studyId}/purge`, {
      data: { confirm_study_id: confirmStudyId },
    }),
  listMembers: (studyId: string) =>
    api.get<StudyMemberListResponse>(`/studies/${studyId}/members`),
  saveMember: (studyId: string, data: StudyMemberUpsertRequest) =>
    api.post<StudyMember>(`/studies/${studyId}/members`, data),
  updateMember: (studyId: string, memberId: string, data: Pick<StudyMemberUpsertRequest, 'role'>) =>
    api.put<StudyMember>(`/studies/${studyId}/members/${memberId}`, data),
  removeMember: (studyId: string, memberId: string) =>
    api.delete<void>(`/studies/${studyId}/members/${memberId}`),
}
