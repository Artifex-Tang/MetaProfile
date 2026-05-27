import { discoveryApi } from './client'
import type { WeakSignalItem, SignalNetwork, ScanTaskResponse, SearchResultList } from './types'

export const discoveryService = {
  triggerScan: (domain?: string) =>
    discoveryApi.post<ScanTaskResponse>('/api/v1/new-tech/scan', { domain }).then(r => r.data),

  listSignals: (page = 1, pageSize = 20) =>
    discoveryApi.get<SearchResultList<WeakSignalItem>>('/api/v1/new-tech/signals', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),

  getNetwork: (signalId: string) =>
    discoveryApi.get<SignalNetwork>(`/api/v1/new-tech/signals/${signalId}/network`).then(r => r.data),

  listDiscoveries: (page = 1, pageSize = 20) =>
    discoveryApi.get<SearchResultList<Record<string, unknown>>>('/api/v1/new-tech/list', {
      params: { page, page_size: pageSize },
    }).then(r => r.data),
}
