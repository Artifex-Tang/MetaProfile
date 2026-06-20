// ── Profile Tech ─────────────────────────────────────────────────────────────

export interface TechDevMilestone {
  milestone_date?: string
  milestone_name?: string
  contributor_keywords: string[]
  milestone_content?: string
}

export interface TechFunding {
  amount?: number
  source?: string
}

export interface TechAcademicOutput {
  name?: string
  publish_date?: string
  subject_keywords: string[]
  image?: string
}

export interface TechExperiment {
  content?: string
  experiment_date?: string
  result?: string
  subject_keywords: string[]
  image?: string
}

export interface TechProfile {
  tech_id: string
  tech_name_cn: string
  tech_name_en?: string
  tech_name_other?: string
  tech_domain: string[]
  invention_date?: string
  application_date?: string
  tech_summary?: string
  dev_goal?: string
  project_layout: string[]
  key_points: string[]
  transformation_status?: string
  basic_research_status?: string
  autonomy_capability?: string
  industrial_capability?: string
  tech_advantages?: string
  current_status?: string
  trend?: string
  remark?: string
  dev_milestones: TechDevMilestone[]
  funding: TechFunding[]
  academic_outputs: TechAcademicOutput[]
  experiments: TechExperiment[]
  contributor_orgs: EntityRef[]
  contributor_persons: EntityRef[]
  contributor_enterprises: EntityRef[]
  reviewed_by_orgs: EntityRef[]
  reviewed_by_persons: EntityRef[]
  reviewed_by_enterprises: EntityRef[]
  confidence: number
  completeness?: number
  veracity_score?: number
  timeliness_score?: number
  data_as_of?: string
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

// ── Profile Person ────────────────────────────────────────────────────────────

export interface PersonEducation {
  start_date?: string
  degree_date?: string
  degree?: string
  school?: string
  major?: string
}

export interface PersonCareer {
  start_date: string
  end_date?: string
  org: string
  enterprise?: string
  position?: string
}

export interface PersonAcademicOutput {
  name?: string
  form?: string
  publish_date?: string
  rank?: string
  citations?: number
  is_representative?: boolean
  collaborators: string[]
}

export interface PersonFocus {
  content: string[]
  consistency_with_policy?: string
  potential_impact: string[]
}

export interface PersonProfile {
  person_id?: string
  name_cn: string
  name_en?: string
  gender?: string
  nationality?: string
  summary?: string
  birth_date?: string
  current_org?: string
  current_position: string[]
  professional_domains: string[]
  professional_skills: string[]
  highest_degree?: string
  person_category?: string
  educations: PersonEducation[]
  careers: PersonCareer[]
  awards: Array<{ description?: string }>
  academic_outputs: PersonAcademicOutput[]
  tech_focuses: PersonFocus[]
  affiliated_orgs: EntityRef[]
  managed_projects: EntityRef[]
  researched_projects: EntityRef[]
  confidence: number
  completeness?: number
  veracity_score?: number
  timeliness_score?: number
  data_as_of?: string
}

export interface PersonSearchItem {
  person_id: string
  name_cn: string
  professional_domains: string[]
  relevance_score?: number | null
}

// ── Profile Org ───────────────────────────────────────────────────────────────

export interface OrgHistory {
  change_date: string
  change_description: string
}

export interface OrgAward {
  name?: string
  description?: string
  award_date?: string
  level?: string
  award_type?: string
}

export interface OrgFacility {
  name?: string
  purpose?: string
  experiment_status?: string
  launch_date?: string
  construction_cost_wan_usd?: number
}

export interface OrgTeam {
  top_talents: string[]
  award_winners: string[]
  team_size?: number
  talent_type?: string
}

export interface OrgOutput {
  name?: string
  form?: string
  author?: string
  publish_date?: string
}

export interface OrgProfile {
  org_id?: string
  name_cn: string
  name_en?: string
  country?: string
  founded_date?: string
  summary?: string
  org_types: string[]
  function?: string
  scale?: number
  tech_domains: string[]
  histories: OrgHistory[]
  awards: OrgAward[]
  outputs: OrgOutput[]
  team?: OrgTeam
  facilities: OrgFacility[]
  related_techs: EntityRef[]
  employees: EntityRef[]
  parent_orgs: EntityRef[]
  child_orgs: EntityRef[]
  confidence: number
  completeness?: number
  veracity_score?: number
  timeliness_score?: number
  data_as_of?: string
}

export interface OrgSearchItem {
  org_id: string
  name_cn: string
  org_types: string[]
  relevance_score?: number | null
}

// ── Profile Project ───────────────────────────────────────────────────────────

export interface ProjectHistory {
  change_date?: string
  change_description?: string
}

export interface ProjectBudget {
  budget_date?: string
  amount: number
}

export interface ProjectOutput {
  name_history?: string
  formed_at?: string
  tech_domains: string[]
  owner_orgs: string[]
}

export interface ProjectProfile {
  project_id?: string
  name_cn: string[]
  name_en: string[]
  tech_domain: string[]
  start_date?: string
  finish_date?: string
  cancel_date?: string
  status: string[]
  project_no?: number
  main_orgs: string[]
  undertaking_orgs: string[]
  managers: string[]
  researchers: string[]
  research_goal?: string
  research_content: string[]
  progress: string[]
  keywords: string[]
  total_budget_million_usd?: number
  invested_million_usd?: number
  histories: ProjectHistory[]
  budgets: ProjectBudget[]
  outputs: ProjectOutput[]
  manager_refs: EntityRef[]
  researcher_refs: EntityRef[]
  tech_refs: EntityRef[]
  confidence: number
  completeness?: number
  veracity_score?: number
  timeliness_score?: number
  data_as_of?: string
}

export interface ProjectSearchItem {
  project_id: string
  name_cn: string[]
  tech_domain: string[]
  relevance_score?: number | null
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
  related_org_ids: string[]
  related_person_ids: string[]
  evidence_doc_ids: string[]
  strength: number
  novelty: number
  coherence: number
  diversity: number
  velocity: number
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
  related_tech_names?: string[]
  related_org_names?: string[]
  related_project_names?: string[]
}

export interface FeedbackResponse {
  topic_id: string
  status: string
}

// ── 关系探索（Spec1）─────────────────────────────────────────────────────────

export type Viewpoint = 'evolve' | 'prereq'

export interface RelationPathStep {
  from_id: string
  from_name?: string | null
  from_type?: string | null
  relation: string
  to_id: string
  to_name?: string | null
  to_type?: string | null
}

export interface RelationPathResult {
  found: boolean
  paths: RelationPathStep[][]
}

export interface TechRelationNode {
  entity_id: string
  entity_type?: string | null
  name?: string | null
}

export interface TechRelationEdge {
  source: string
  target: string
  rel_type: string
}

export interface TechRelationResult {
  nodes: TechRelationNode[]
  edges: TechRelationEdge[]
  viewpoint: Viewpoint
}
