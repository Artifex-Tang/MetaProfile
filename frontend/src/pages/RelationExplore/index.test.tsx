import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RelationExplore from './index'

// PathGraph 内部使用 @antv/g6，jsdom 下无法实例化，统一 mock。
vi.mock('@antv/g6', () => {
  function Graph(this: any) {
    this.data = () => this
    this.render = () => this
    this.on = () => {}
    this.off = () => {}
    this.destroy = () => {}
    this.setItemState = () => {}
  }
  return {
    default: {
      Tooltip: function () {},
      Minimap: function () {},
      Arrow: { triangle: () => 'M0 0' },
    },
    Graph,
  }
})

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RelationExplore />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RelationExplore', () => {
  it('默认渲染模式切换 Radio + 关系路径模式(起点/终点实体占位)', () => {
    renderPage()
    expect(screen.getByText('关系路径')).toBeInTheDocument()
    expect(screen.getByText('技术关系')).toBeInTheDocument()
    // 模式1 默认：两个实体选择器占位(页面用自定义 placeholder 起点实体/终点实体)
    expect(screen.getByText('起点实体')).toBeInTheDocument()
    expect(screen.getByText('终点实体')).toBeInTheDocument()
  })

  it('切到技术关系模式 → 显示视角 Radio(演进链/前置树)', () => {
    renderPage()
    fireEvent.click(screen.getByText('技术关系'))
    expect(screen.getByText('演进链')).toBeInTheDocument()
    expect(screen.getByText('前置树')).toBeInTheDocument()
  })
})
