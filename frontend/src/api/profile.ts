import { projectApi, orgApi, personApi } from './client'
import type {
  SearchResultList, RelationList,
  PersonProfile, PersonSearchItem,
  OrgProfile, OrgSearchItem,
  ProjectProfile, ProjectSearchItem,
} from './types'

/** enrich 补全任务提交响应（4 画像共用形状）。 */
interface EnrichmentTaskResponse {
  task_id: string
  status: string
  current_completeness?: number
}

/** enrich 补全任务状态轮询响应（celery AsyncResult，与 tech 一致）。 */
export interface EnrichTaskStatus {
  task_id: string
  state: string
  status?: string
  completeness_after?: number
  filled_fields?: string[]
  error?: string | null
}

export const personService = {
  search: (keyword: string, page = 1, pageSize = 20) =>
    personApi.post<SearchResultList<PersonSearchItem>>('/api/v1/profile/person/search', {
      keyword, page, page_size: pageSize,
    }).then(r => r.data),

  getById: (id: string) =>
    personApi.get<PersonProfile>(`/api/v1/profile/person/${id}`).then(r => r.data),

  bulkImport: (profiles: Partial<PersonProfile>[]) =>
    personApi.post('/api/v1/profile/person/import', { profiles, overwrite: false }).then(r => r.data),

  getRelations: (id: string) =>
    personApi.get<RelationList>(`/api/v1/relation/person/${id}`).then(r => r.data),

  getStats: () =>
    personApi.get<{ total: number }>('/api/v1/stats/person').then(r => r.data),

  enrich: (id: string) =>
    personApi.post<EnrichmentTaskResponse>(`/api/v1/profile/person/${id}/enrich`).then(r => r.data),

  getEnrichTaskStatus: (taskId: string) =>
    personApi.get<EnrichTaskStatus>(`/api/v1/profile/person/enrich/task/${taskId}`).then(r => r.data),
}

export const orgService = {
  search: (keyword: string, page = 1, pageSize = 20) =>
    orgApi.post<SearchResultList<OrgSearchItem>>('/api/v1/profile/org/search', {
      keyword, page, page_size: pageSize,
    }).then(r => r.data),

  getById: (id: string) =>
    orgApi.get<OrgProfile>(`/api/v1/profile/org/${id}`).then(r => r.data),

  bulkImport: (profiles: Partial<OrgProfile>[]) =>
    orgApi.post('/api/v1/profile/org/import', { profiles, overwrite: false }).then(r => r.data),

  getRelations: (id: string) =>
    orgApi.get<RelationList>(`/api/v1/relation/org/${id}`).then(r => r.data),

  getStats: () =>
    orgApi.get<{ total: number }>('/api/v1/stats/org').then(r => r.data),

  enrich: (id: string) =>
    orgApi.post<EnrichmentTaskResponse>(`/api/v1/profile/org/${id}/enrich`).then(r => r.data),

  getEnrichTaskStatus: (taskId: string) =>
    orgApi.get<EnrichTaskStatus>(`/api/v1/profile/org/enrich/task/${taskId}`).then(r => r.data),
}

export const projectService = {
  search: (keyword: string, page = 1, pageSize = 20) =>
    projectApi.post<SearchResultList<ProjectSearchItem>>('/api/v1/profile/project/search', {
      keyword, page, page_size: pageSize,
    }).then(r => r.data),

  getById: (id: string) =>
    projectApi.get<ProjectProfile>(`/api/v1/profile/project/${id}`).then(r => r.data),

  bulkImport: (profiles: Partial<ProjectProfile>[]) =>
    projectApi.post('/api/v1/profile/project/import', { profiles, overwrite: false }).then(r => r.data),

  getRelations: (id: string) =>
    projectApi.get<RelationList>(`/api/v1/relation/project/${id}`).then(r => r.data),

  getStats: () =>
    projectApi.get<{ total: number }>('/api/v1/stats/project').then(r => r.data),

  enrich: (id: string) =>
    projectApi.post<EnrichmentTaskResponse>(`/api/v1/profile/project/${id}/enrich`).then(r => r.data),

  getEnrichTaskStatus: (taskId: string) =>
    projectApi.get<EnrichTaskStatus>(`/api/v1/profile/project/enrich/task/${taskId}`).then(r => r.data),
}
