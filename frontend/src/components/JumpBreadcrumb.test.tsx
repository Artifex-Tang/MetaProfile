import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import JumpBreadcrumb from './JumpBreadcrumb'
import type { JumpCtx } from '../utils/crossProfile'

const { navigate } = vi.hoisted(() => ({ navigate: vi.fn() }))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

const renderWithRouter = (ui: ReactNode) =>
  render(<MemoryRouter initialEntries={['/org/ORG_1']}>{ui}</MemoryRouter>)

const ctx = (over: Partial<JumpCtx> = {}): JumpCtx => ({
  fromType: 'person',
  fromId: 'PERSON_1',
  fromName: '张三',
  relationType: 'ORG_PARENT',
  confidence: 0.8,
  evidence: null,
  ...over,
})

beforeEach(() => navigate.mockClear())

describe('JumpBreadcrumb', () => {
  it('有 ctx 时渲染来源名与关系标注', () => {
    renderWithRouter(<JumpBreadcrumb ctx={ctx()} />)
    expect(screen.getByText('张三')).toBeInTheDocument()
    // REL_LABEL.ORG_PARENT = '隶属'
    expect(screen.getByText('经「隶属」')).toBeInTheDocument()
  })

  it('ctx 缺关系类型时只渲染来源', () => {
    renderWithRouter(<JumpBreadcrumb ctx={ctx({ relationType: null })} />)
    expect(screen.getByText('张三')).toBeInTheDocument()
    expect(screen.queryByText(/经「/)).not.toBeInTheDocument()
  })

  it('fromName 缺失时回退展示 fromId', () => {
    renderWithRouter(<JumpBreadcrumb ctx={ctx({ fromName: null })} />)
    expect(screen.getByText('PERSON_1')).toBeInTheDocument()
  })

  it('点击来源项触发 navigate 返回来源', () => {
    renderWithRouter(<JumpBreadcrumb ctx={ctx()} />)
    fireEvent.click(screen.getByText('张三'))
    expect(navigate).toHaveBeenCalledWith('/person/PERSON_1')
  })

  it('来源 id 含特殊字符时编码', () => {
    renderWithRouter(<JumpBreadcrumb ctx={ctx({ fromId: 'A B' })} />)
    fireEvent.click(screen.getByText('张三'))
    expect(navigate).toHaveBeenCalledWith('/person/A%20B')
  })

  it('ctx 为 null 时不渲染任何内容', () => {
    const { container } = renderWithRouter(<JumpBreadcrumb ctx={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('ctx 缺 fromId 时不渲染', () => {
    const { container } = renderWithRouter(
      <JumpBreadcrumb ctx={ctx({ fromId: '' })} />,
    )
    expect(container.firstChild).toBeNull()
  })
})
