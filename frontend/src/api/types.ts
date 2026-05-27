// ── Profile Tech ─────────────────────────────────────────────────────────────

export interface TechProfile {
  tech_id: string
  tech_name_cn: string
  tech_name_en?: string
  tech_domain: string[]
  tech_summary?: string
  current_status?: string
  trend?: string
  confidence: number
  completeness?: number
  project_layout: unknown[]
  key_points: unknown[]
  dev_milestones?: unknown[]
  contributor_orgs?: EntityRef[]
  contributor_persons?: EntityRef[]
  contributor_enterprises?: EntityRef[]
}

export interface EntityRef {
  entity_id: string
  entity_type: string
  name?: string
}

export interface TechSearchResultItem {
  tech_id: string
  tech_name_cn: string
  tech_domain: string[]
  relevance_score: number | null
}

export interface SearchResultList<T> {
  items: T[]
  total: number
}

export interface TechStatsResponse {
  total: number
  new_this_period: number
  updated_this_period: number
  domain_distribution: Record<string, number>
  completeness_histogram: Record<string, number>
  llm_contribution_ratio: number
  updated_at: string | null
}

export interface RelationItem {
  relation_type: string
  target_entity_id: string
  target_entity_type: string
  target_name: string | null
  confidence: number
  evidence: string | null
}

export interface RelationList {
  items: RelationItem[]
  total: number
}

export interface BulkImportResult {
  task_id: string
  accepted_count: number
  submitted_at: string
}

// ── Generic profile (project / org / person share same pattern) ──────────────

export interface GenericProfile {
  [key: string]: unknown
}

export interface GenericSearchItem {
  [key: string]: unknown
}

// ── Scan Monitor ─────────────────────────────────────────────────────────────

export interface FrontierTechItem {
  id: number
  scan_task_id: string
  tech_id: string | null
  tech_name: string
  tech_domain: string[]
  period_from: string
  period_to: string
  burst_score: number
  patent_score: number
  citation_score: number
  invest_score: number
  policy_score: number
  fusion_score: number
  llm_validated: boolean
  llm_verdict: string | null
  trl_level: number | null
  status: string
}

export interface AlertItem {
  id: number
  tech_name: string
  alert_type: string
  severity: string
  message: string
  fired_at: string
  is_read: boolean
}

export interface ScanTaskResponse {
  task_id: string
  period_from: string
  period_to: string
  status: string
}

// ── New Tech Discovery ────────────────────────────────────────────────────────

export interface WeakSignalItem {
  id: number
  signal_id: string
  keywords: string[]
  related_tech_ids: string[]
  strength: number
  novelty: number
  coherence: number
  period_from: string
  period_to: string
  domain: string | null
  status: string
}

export interface SignalNetworkNode {
  entity_id: string
  entity_type: string
  name: string | null
}

export interface SignalNetworkEdge {
  source_id: string
  target_id: string
  edge_type: string
  weight: number
}

export interface SignalNetwork {
  signal_id: string
  nodes: SignalNetworkNode[]
  edges: SignalNetworkEdge[]
}

// ── Topic Selection ───────────────────────────────────────────────────────────

export interface TopicItem {
  id: number
  topic_id: string
  title: string
  summary: string
  period: string | null
  related_tech_ids: string[]
  score_hot: number
  score_policy: number
  score_impact: number
  score_dedup: number
  score_llm_gen: number
  review_novelty: number
  review_importance: number
  review_feasibility: number
  review_expression: number
  final_score: number
  status: string
}

export interface TopicDetail extends TopicItem {
  related_org_ids: string[]
  related_project_ids: string[]
  related_policy_refs: string[]
  review_evidence: string | null
}

export interface FeedbackResponse {
  topic_id: string
  status: string
}
