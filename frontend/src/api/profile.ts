import { projectApi, orgApi, personApi } from './client'
import type { SearchResultList } from './types'
import type { AxiosInstance } from 'axios'

const makeProfileService = (api: AxiosInstance, entity: string) => ({
  search: (keyword: string, page = 1, pageSize = 20) =>
    api.post<SearchResultList<Record<string, unknown>>>(`/api/v1/profile/${entity}/search`, {
      keyword, page, page_size: pageSize,
    }).then(r => r.data),

  getById: (id: string) =>
    api.get<Record<string, unknown>>(`/api/v1/profile/${entity}/${id}`).then(r => r.data),

  bulkImport: (profiles: Record<string, unknown>[]) =>
    api.post(`/api/v1/profile/${entity}/import`, { profiles, overwrite: false }).then(r => r.data),

  getStats: () =>
    api.get(`/api/v1/stats/${entity}`).then(r => r.data),

  getRelations: (id: string) =>
    api.get(`/api/v1/relation/${entity}/${id}`).then(r => r.data),
})

export const projectService = makeProfileService(projectApi, 'project')
export const orgService     = makeProfileService(orgApi, 'org')
export const personService  = makeProfileService(personApi, 'person')
