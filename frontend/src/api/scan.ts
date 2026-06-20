import { scanApi } from './client'
import type { FrontierTechItem, AlertItem, ScanTaskResponse, SearchResultList } from './types'

export const scanService = {
  triggerScan: (periodFrom: string, periodTo: string, domains?: string[]) =>
    scanApi.post<ScanTaskResponse>('/api/v1/frontier-tech/scan', {
      period_from: periodFrom, period_to: periodTo, tech_domains: domains ?? [],
    }).then(r => r.data),

  listFrontierTech: (page = 1, pageSize = 10) =>
    scanApi.get<SearchResultList<FrontierTechItem>>('/api/v1/frontier-tech/list', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),

  listAlerts: (page = 1, pageSize = 10) =>
    scanApi.get<SearchResultList<AlertItem>>('/api/v1/frontier-tech/alerts', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),

  getFrontierTech: (id: string) =>
    scanApi.get<FrontierTechItem>(`/api/v1/frontier-tech/${id}`).then(r => r.data),

  verify: (id: number) =>
    scanApi.post<{ task_id: string; status: string }>(`/api/v1/frontier-tech/${id}/verify`).then(r => r.data),

  getVerifyTaskStatus: (taskId: string) =>
    scanApi.get<{
      task_id: string; state: string; status?: string;
      llm_verdict?: string; frontier_status?: string; error?: string
    }>(`/api/v1/frontier-tech/verify/task/${taskId}`).then(r => r.data),
}
