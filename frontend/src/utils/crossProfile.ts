/**
 * 跨画像跳转：共享类型与逻辑（方案 A）。
 *
 * 后端 EntityType 为大写枚举（TECH/PROJECT/ORG/PERSON），前端统一按小写
 * 做可跳判定与路由。entity_id 形如 `ORG_20260427_a1b2c3d4`，不含冒号，
 * 故 `?from=type:id` 分隔安全；仍对 id 做 encodeURIComponent 兜底。
 */
import { useLocation, useNavigate } from 'react-router-dom'

/** 可跳转的画像类型（小写）。enterprise/strategy 等暂不跳转。 */
export const NAV_TYPES = new Set(['tech', 'project', 'org', 'person'])

/** 跳转上下文：随路由 state 携带；刷新/分享后仅能由 ?from= 部分还原。 */
export interface JumpCtx {
  fromType: string
  fromId: string
  fromName: string | null
  relationType: string | null
  confidence: number | null
  evidence: string | null
}

/** RelationGraph 节点点击回调载荷。 */
export interface NodeClickItem {
  id: string
  type?: string | null
  name?: string | null
  relationType?: string | null
  confidence?: number | null
  evidence?: string | null
}

export function isNavType(type?: string | null): boolean {
  return !!type && NAV_TYPES.has(type.toLowerCase())
}

/** 解析 `?from=type:id`，刷新/分享链接的来源兜底。 */
export function parseFromQuery(search: string): { fromType: string; fromId: string } | null {
  const raw = new URLSearchParams(search).get('from')
  if (!raw) return null
  const idx = raw.indexOf(':')
  if (idx <= 0) return null
  return { fromType: raw.slice(0, idx), fromId: decodeURIComponent(raw.slice(idx + 1)) }
}

/**
 * 读取跳转上下文（state 优先，?from= 兜底），并提供节点点击 → 跳转处理。
 *
 * @param selfType 当前画像类型（小写，如 'person'）
 * @param selfId   当前实体 id（即 DetailDrawer 的 id）
 * @param selfName 当前实体名称（用于来源面包屑）
 */
export function useCrossProfileJump(
  selfType: string,
  selfId: string | null,
  selfName: string | null,
) {
  const navigate = useNavigate()
  const loc = useLocation()

  const stateCtx = (loc.state ?? null) as JumpCtx | null
  const ctx: JumpCtx | null = stateCtx
    ?? (() => {
      const q = parseFromQuery(loc.search)
      return q
        ? { ...q, fromName: null, relationType: null, confidence: null, evidence: null }
        : null
    })()

  const handleNodeClick = (n: NodeClickItem): void => {
    const type = (n.type ?? '').toLowerCase()
    if (!NAV_TYPES.has(type)) return        // 仅四类画像可跳
    if (!selfId) return
    const state: JumpCtx = {
      fromType: selfType,
      fromId: selfId,
      fromName: selfName,
      relationType: n.relationType ?? null,
      confidence: n.confidence ?? null,
      evidence: n.evidence ?? null,
    }
    navigate(
      `/${type}/${encodeURIComponent(n.id)}?from=${selfType}:${encodeURIComponent(selfId)}`,
      { state },
    )
  }

  return { ctx, handleNodeClick }
}
