/** 实体类型 → 颜色 + 中文标签（大小写不敏感）。RelationGraph/PathGraph/JumpBreadcrumb 共用。 */
export const TYPE_META: Record<string, { color: string; label: string }> = {
  tech: { color: '#1677ff', label: '技术' },
  org: { color: '#52c41a', label: '机构' },
  person: { color: '#fa8c16', label: '人员' },
  project: { color: '#722ed1', label: '项目' },
  enterprise: { color: '#13c2c2', label: '企业' },
  strategy: { color: '#eb2f96', label: '战略' },
  event: { color: '#faad14', label: '事件' },
  contract: { color: '#a0522d', label: '采购合同' },
  package: { color: '#2f54eb', label: '项目包' },
}

export function metaOf(type?: string | null) {
  const k = (type ?? '').toLowerCase()
  return TYPE_META[k] ?? { color: '#8c8c8c', label: type ?? '其它' }
}

/** 关系类型（英文枚举名 或 中文值）→ 中文展示 */
const REL_LABEL: Record<string, string> = {
  ORG_EMPLOY: '雇佣', ORG_PARENT: '隶属', ORG_CHILD: '下辖', ORG_SIBLING: '兄弟单位',
  ORG_COOPERATE: '合作', ORG_FUND: '拨款/资助', ORG_EVALUATE: '评价',
  ORG_FUND_PROJECT: '资助', ORG_UNDERTAKE_PROJECT: '承研', ORG_INVOLVE_TECH: '涉及',
  PROJECT_MAIN_ORG: '主管', PROJECT_UNDERTAKE_ORG: '承研', PROJECT_MANAGER: '管理',
  PROJECT_RESEARCHER: '研究', PROJECT_INVOLVE_TECH: '涉及', PROJECT_NEXT_PHASE: '转阶段',
  PERSON_AFFILIATED_ORG: '隶属', PERSON_COOPERATE: '合作', PERSON_SUPERIOR: '上级',
  TECH_CONTRIBUTOR: '贡献者', TECH_REVIEWED_BY: '被评议',
  TECH_EVOLVE: '演进', TECH_PREREQ: '前置',
  // 中文键（mock 落库类型为中文值时命中）
  隶属: '隶属', 资助: '资助', 承研: '承研', 合作: '合作', 涉及: '涉及',
  管理: '管理', 研究: '研究', 贡献者: '贡献者', 演进: '演进', 前置: '前置',
}

export const relLabel = (r?: string | null) => (r && REL_LABEL[r]) ? REL_LABEL[r] : (r ?? '')
