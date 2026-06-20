import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PathGraph from './PathGraph'

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

const nodes = [
  { id: 'A', type: 'tech', name: '甲' },
  { id: 'B', type: 'tech', name: '乙' },
]
const edges = [{ source: 'A', target: 'B', label: '演进' }]

describe('PathGraph', () => {
  it('空数据 → 空态文案', () => {
    render(<PathGraph nodes={[]} edges={[]} emptyText="无路径" />)
    expect(screen.getByText('无路径')).toBeInTheDocument()
  })

  it('有数据 → 渲染图例（技术）', () => {
    render(<PathGraph nodes={nodes} edges={edges} />)
    expect(screen.queryByText('无路径')).not.toBeInTheDocument()
    expect(screen.getByText('技术')).toBeInTheDocument()
  })

  it('自定义 emptyText 生效', () => {
    render(<PathGraph nodes={[]} edges={[]} emptyText="该技术暂无演进记录" />)
    expect(screen.getByText('该技术暂无演进记录')).toBeInTheDocument()
  })
})
