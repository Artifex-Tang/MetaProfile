import { settingsApi } from './client'

export interface LLMProviderConfig {
  id: number
  name: string
  provider: string
  model_name: string
  api_key: string | null
  api_base: string | null
  model_role: string
  max_tokens: number
  temperature: number
  is_enabled: boolean
  is_default: boolean
  litellm_synced: boolean
  created_at: string
  updated_at: string
}

export interface LLMProviderConfigCreate {
  name: string
  provider: string
  model_name: string
  api_key?: string
  api_base?: string
  model_role: string
  max_tokens?: number
  temperature?: number
  is_enabled?: boolean
  is_default?: boolean
}

export interface DataSourceConfig {
  id: number
  name: string
  source_type: string
  profile_type: string
  config_json: Record<string, unknown>
  schedule_cron: string | null
  is_enabled: boolean
  last_run_at: string | null
  last_run_status: string | null
  created_at: string
  updated_at: string
}

export interface DataSourceConfigCreate {
  name: string
  source_type: string
  profile_type: string
  config_json: Record<string, unknown>
  schedule_cron?: string
  is_enabled?: boolean
}

export interface CollectionTask {
  id: number
  source_id: number
  source_name: string
  profile_type: string
  status: string
  started_at: string | null
  completed_at: string | null
  records_fetched: number
  records_imported: number
  error_msg: string | null
  log_text: string | null
  created_at: string
}

export interface TriggerResponse {
  task_id: number
  source_id: number
  source_name: string
  status: string
  message: string
}

export interface LLMTestResponse {
  success: boolean
  message: string
  latency_ms: number | null
}

export interface DbConnection {
  id: number
  name: string
  dialect: string
  host: string
  port: number
  database: string
  username: string
  charset: string
  pool_size: number
  read_only: boolean
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface DbConnectionCreate {
  name: string
  dialect?: string
  host: string
  port: number
  database: string
  username: string
  password: string
  charset?: string
  pool_size?: number
  read_only?: boolean
  is_enabled?: boolean
}

export interface CollectionTaskStats {
  task_id: number
  raw_total: number
  raw_success: number
  raw_failed: number
  errors: number
}

export const settingsService = {
  // LLM 配置
  listLLM: () =>
    settingsApi.get<LLMProviderConfig[]>('/api/v1/settings/llm').then(r => r.data),

  createLLM: (body: LLMProviderConfigCreate) =>
    settingsApi.post<LLMProviderConfig>('/api/v1/settings/llm', body).then(r => r.data),

  updateLLM: (id: number, body: Partial<LLMProviderConfigCreate>) =>
    settingsApi.put<LLMProviderConfig>(`/api/v1/settings/llm/${id}`, body).then(r => r.data),

  deleteLLM: (id: number) =>
    settingsApi.delete(`/api/v1/settings/llm/${id}`),

  testLLM: (id: number) =>
    settingsApi.post<LLMTestResponse>(`/api/v1/settings/llm/${id}/test`).then(r => r.data),

  syncLLM: (id: number) =>
    settingsApi.post<LLMProviderConfig>(`/api/v1/settings/llm/${id}/sync`).then(r => r.data),

  // 数据源配置
  listDataSources: () =>
    settingsApi.get<DataSourceConfig[]>('/api/v1/settings/datasources').then(r => r.data),

  createDataSource: (body: DataSourceConfigCreate) =>
    settingsApi.post<DataSourceConfig>('/api/v1/settings/datasources', body).then(r => r.data),

  updateDataSource: (id: number, body: Partial<DataSourceConfigCreate>) =>
    settingsApi.put<DataSourceConfig>(`/api/v1/settings/datasources/${id}`, body).then(r => r.data),

  deleteDataSource: (id: number) =>
    settingsApi.delete(`/api/v1/settings/datasources/${id}`),

  getTemplates: () =>
    settingsApi.get<Record<string, unknown>>('/api/v1/settings/datasources/templates/list').then(r => r.data),

  // 采集任务
  triggerCollection: (sourceId: number) =>
    settingsApi.post<TriggerResponse>(`/api/v1/settings/collection/trigger/${sourceId}`).then(r => r.data),

  listTasks: (sourceId?: number) =>
    settingsApi.get<CollectionTask[]>('/api/v1/settings/collection/tasks', {
      params: sourceId != null ? { source_id: sourceId } : {},
    }).then(r => r.data),

  getTask: (taskId: number) =>
    settingsApi.get<CollectionTask>(`/api/v1/settings/collection/tasks/${taskId}`).then(r => r.data),

  getTaskStats: (taskId: number) =>
    settingsApi.get<CollectionTaskStats>(`/api/v1/settings/collection/tasks/${taskId}/stats`).then(r => r.data),

  // 数据连接（ODS Doris 等外部 DB）
  listDbConnections: () =>
    settingsApi.get<DbConnection[]>('/api/v1/settings/db-connections').then(r => r.data),

  createDbConnection: (body: DbConnectionCreate) =>
    settingsApi.post<DbConnection>('/api/v1/settings/db-connections', body).then(r => r.data),

  updateDbConnection: (id: number, body: Partial<DbConnectionCreate>) =>
    settingsApi.put<DbConnection>(`/api/v1/settings/db-connections/${id}`, body).then(r => r.data),

  deleteDbConnection: (id: number) =>
    settingsApi.delete(`/api/v1/settings/db-connections/${id}`),
}
