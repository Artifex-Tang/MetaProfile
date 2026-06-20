import { techApi } from './client'
import type {
  RelationPathResult,
  TechRelationResult,
  Viewpoint,
} from './types'

/** 两实体间最短路径（统一走 /relation/tech/path 服务代理）。 */
export const getPath = (
  fromType: string,
  fromId: string,
  toId: string,
  maxDepth: number,
) =>
  techApi
    .post<RelationPathResult>('/api/v1/relation/tech/path', {
      from_id: fromId,
      to_id: toId,
      max_depth: maxDepth,
    })
    .then((r) => r.data)

/** 技术关系图（演进链 / 前置树）。 */
export const getTechRelation = (techId: string, viewpoint: Viewpoint, depth = 4) =>
  techApi
    .get<TechRelationResult>(
      `/api/v1/relation/tech/${techId}/tech-relation`,
      { params: { viewpoint, depth } },
    )
    .then((r) => r.data)

export const relationApi = {
  getPath,
  getTechRelation,
}
