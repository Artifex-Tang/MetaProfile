/** 实体名兜底（#9 非中文策略）：name_cn 空 → name_en → id。 */

export interface NameLike {
  name_cn?: string | null
  name_en?: string | null
  id: string
}

const norm = (v?: string | null): string => (v && v.trim()) || ''

/** 展示名：name_cn 优先 → name_en → id。 */
export function displayName(e: NameLike): string {
  return norm(e.name_cn) || norm(e.name_en) || e.id
}

/** 未译：name_cn 空 且 name_en 有（可翻译）。 */
export function isUntranslated(e: NameLike): boolean {
  return !norm(e.name_cn) && !!norm(e.name_en)
}
