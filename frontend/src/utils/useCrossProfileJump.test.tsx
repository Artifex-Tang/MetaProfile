import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useCrossProfileJump } from './crossProfile'
import type { JumpCtx, NodeClickItem } from './crossProfile'

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

const node = (over: Partial<NodeClickItem> = {}): NodeClickItem => ({
  id: 'ORG_20260101_xyz',
  type: 'ORG',
  name: '某机构',
  relationType: 'ORG_PARENT',
  confidence: 0.8,
  evidence: '依据原文',
  ...over,
})

const wrapper = (initial: string | { pathname: string; state?: unknown }) =>
  ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[initial as string]}>{children}</MemoryRouter>
  )

beforeEach(() => navigate.mockClear())

describe('useCrossProfileJump · handleNodeClick', () => {
  it('可跳类型：调用 navigate，路径与 state 正确', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('person', 'PERSON_1', '张三'),
      { wrapper: wrapper('/person/PERSON_1') },
    )
    result.current.handleNodeClick(node())

    expect(navigate).toHaveBeenCalledTimes(1)
    const [path, opts] = navigate.mock.calls[0]
    // 路径：/org/<id>?from=person:PERSON_1
    expect(path).toBe('/org/ORG_20260101_xyz?from=person:PERSON_1')
    expect(opts).toEqual({
      state: {
        fromType: 'person',
        fromId: 'PERSON_1',
        fromName: '张三',
        relationType: 'ORG_PARENT',
        confidence: 0.8,
        evidence: '依据原文',
      },
    })
  })

  it('后端大写 type 归一化为小写后写入路由', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('org', 'ORG_1', null),
      { wrapper: wrapper('/org/ORG_1') },
    )
    result.current.handleNodeClick(node({ id: 'TECH_1', type: 'TECH' }))
    expect(navigate.mock.calls[0][0]).toBe('/tech/TECH_1?from=org:ORG_1')
  })

  it('id 含特殊字符做 URL 编码', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('org', 'ORG 1', '机构A'),
      { wrapper: wrapper('/org/ORG%201') },
    )
    result.current.handleNodeClick(node({ id: 'a b', type: 'PERSON' }))
    // from 段中冒号后的 id 亦编码
    expect(navigate.mock.calls[0][0]).toBe('/person/a%20b?from=org:ORG%201')
  })

  it('不可跳类型（enterprise）不触发 navigate', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('person', 'PERSON_1', '张三'),
      { wrapper: wrapper('/person/PERSON_1') },
    )
    result.current.handleNodeClick(node({ id: 'ENT_1', type: 'ENTERPRISE' }))
    expect(navigate).not.toHaveBeenCalled()
  })

  it('未知/空类型不触发 navigate', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('person', 'PERSON_1', null),
      { wrapper: wrapper('/person/PERSON_1') },
    )
    result.current.handleNodeClick(node({ type: '' }))
    expect(navigate).not.toHaveBeenCalled()
  })

  it('selfId 为空（抽屉未就绪）不触发 navigate', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('person', null, null),
      { wrapper: wrapper('/person') },
    )
    result.current.handleNodeClick(node())
    expect(navigate).not.toHaveBeenCalled()
  })
})

describe('useCrossProfileJump · ctx 读取', () => {
  it('优先取路由 state 作为完整 ctx', () => {
    const state: JumpCtx = {
      fromType: 'person', fromId: 'PERSON_1', fromName: '张三',
      relationType: 'ORG_PARENT', confidence: 0.8, evidence: '依据',
    }
    const { result } = renderHook(
      () => useCrossProfileJump('org', 'ORG_1', null),
      { wrapper: wrapper({ pathname: '/org/ORG_1', state }) },
    )
    expect(result.current.ctx).toEqual(state)
  })

  it('无 state 时由 ?from= 兜底还原来源类型与 id（关系信息为空）', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('org', 'ORG_1', null),
      { wrapper: wrapper('/org/ORG_1?from=person:PERSON_9') },
    )
    expect(result.current.ctx).toEqual({
      fromType: 'person', fromId: 'PERSON_9',
      fromName: null, relationType: null, confidence: null, evidence: null,
    })
  })

  it('既无 state 又无 ?from= 时 ctx 为 null', () => {
    const { result } = renderHook(
      () => useCrossProfileJump('org', 'ORG_1', null),
      { wrapper: wrapper('/org/ORG_1') },
    )
    expect(result.current.ctx).toBeNull()
  })
})
