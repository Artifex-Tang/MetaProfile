import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getPath, getTechRelation } from './relation'

const { techApi } = vi.hoisted(() => ({
  techApi: { post: vi.fn(), get: vi.fn() },
}))
vi.mock('./client', () => ({ techApi }))

beforeEach(() => { techApi.post.mockReset(); techApi.get.mockReset() })

describe('getPath', () => {
  it('POST /relation/tech/path 带正确 body', async () => {
    techApi.post.mockResolvedValue({ data: { found: true, paths: [] } })
    await getPath('tech', 'A', 'B', 3)
    expect(techApi.post).toHaveBeenCalledWith('/api/v1/relation/tech/path',
      { from_id: 'A', to_id: 'B', max_depth: 3 })
  })
})

describe('getTechRelation', () => {
  it('GET tech-relation 带 viewpoint + depth（axios params）', async () => {
    techApi.get.mockResolvedValue({ data: { nodes: [], edges: [], viewpoint: 'evolve' } })
    await getTechRelation('T1', 'prereq', 4)
    expect(techApi.get).toHaveBeenCalledWith(
      '/api/v1/relation/tech/T1/tech-relation',
      { params: { viewpoint: 'prereq', depth: 4 } },
    )
  })
})
