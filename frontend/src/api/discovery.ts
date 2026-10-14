import { discoveryApi } from './client'
import type {
  ComputeTaskResponse,
  DisruptionList,
  EmergenceList,
  ScanTaskResponse,
  SearchResultList,
  SignalNetwork,
  WeakSignalItem,
} from './types'

export const discoveryService = {
  triggerScan: (domain?: string) =>
    discoveryApi.post<ScanTaskResponse>('/api/v1/new-tech/scan', { domain }).then(r => r.data),

  listSignals: (page = 1, pageSize = 10) =>
    discoveryApi.get<SearchResultList<WeakSignalItem>>('/api/v1/new-tech/signals', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),

  getNetwork: (signalId: string) =>
    discoveryApi.get<SignalNetwork>(`/api/v1/new-tech/signals/${signalId}/network`).then(r => r.data),

  listDiscoveries: (page = 1, pageSize = 10) =>
    discoveryApi.get<SearchResultList<Record<string, unknown>>>('/api/v1/new-tech/list', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),

  listEmergence: (params: {
    object_type?: string; window?: string; quadrant?: string
    page?: number; page_size?: number
  }) =>
    discoveryApi.get<EmergenceList>('/api/v1/new-tech/emergence', { params }).then(r => r.data),

  computeEmergence: () =>
    discoveryApi.post<ComputeTaskResponse>('/api/v1/new-tech/emergence/compute').then(r => r.data),

  listDisruption: (params: {
    window?: string; verdict?: string; page?: number; page_size?: number
  }) =>
    discoveryApi.get<DisruptionList>('/api/v1/new-tech/disruption', { params }).then(r => r.data),

  computeDisruption: (llm = true) =>
    discoveryApi.post<ComputeTaskResponse>('/api/v1/new-tech/disruption/compute', null, {
      params: { llm },
    }).then(r => r.data),
}
