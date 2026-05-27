import { techApi } from './client'
import type {
  TechProfile, TechSearchResultItem, SearchResultList,
  TechStatsResponse, RelationList, BulkImportResult,
} from './types'

export const techService = {
  search: (keyword: string, page = 1, pageSize = 20) =>
    techApi.post<SearchResultList<TechSearchResultItem>>('/api/v1/profile/tech/search', {
      keyword, page, page_size: pageSize,
    }).then(r => r.data),

  getById: (id: string) =>
    techApi.get<TechProfile>(`/api/v1/profile/tech/${id}`).then(r => r.data),

  update: (id: string, payload: Record<string, unknown>) =>
    techApi.put<TechProfile>(`/api/v1/profile/tech/${id}`, payload).then(r => r.data),

  bulkImport: (profiles: Partial<TechProfile>[]) =>
    techApi.post<BulkImportResult>('/api/v1/profile/tech/import', {
      profiles, overwrite: false,
    }).then(r => r.data),

  getStats: () =>
    techApi.get<TechStatsResponse>('/api/v1/stats/tech').then(r => r.data),

  getRelations: (id: string) =>
    techApi.get<RelationList>(`/api/v1/relation/tech/${id}`).then(r => r.data),
}
