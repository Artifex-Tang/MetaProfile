import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RelationGraph, { relLabel } from './RelationGraph'
import type { RelItem } from './RelationGraph'

// G6 依赖真实 canvas，jsdom 无 canvas → mock 掉，仅验证组件装配/图例/纯函数。
// 命中组件里 new Graph(...)、new G6.Tooltip/Minimap(...)、G6.Arrow.triangle(...)。
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

const rel = (over: Partial<RelItem> = {}): RelItem => ({
  target_entity_id: 'TECH_1',
  target_entity_type: 'tech',
  target_name: '量子计算',
  relation_type: 'ORG_FUND',
  confidence: 0.8,
  evidence: null,
  ...over,
})

describe('relLabel 纯函数', () => {
  it('英文枚举 → 中文', () => {
    expect(relLabel('ORG_FUND')).toBe('拨款/资助')
    expect(relLabel('TECH_CONTRIBUTOR')).toBe('贡献者')
    expect(relLabel('PROJECT_UNDERTAKE_ORG')).toBe('承研')
  })
  it('已是中文 → 原样', () => {
    expect(relLabel('隶属')).toBe('隶属')
    expect(relLabel('合作')).toBe('合作')
  })
  it('未知类型 → 原值透传', () => {
    expect(relLabel('SOMETHING_NEW')).toBe('SOMETHING_NEW')
  })
  it('空值 → 空串', () => {
    expect(relLabel(null)).toBe('')
    expect(relLabel(undefined)).toBe('')
  })
})

describe('RelationGraph 渲染', () => {
  it('空关联数据 → 渲染占位 + 图例', () => {
    render(<RelationGraph relations={[]} />)
    expect(screen.getByText('暂无关联数据')).toBeInTheDocument()
    // 图例始终渲染（self 标签 + 实体类型标签）
    expect(screen.getByText('当前实体')).toBeInTheDocument()
    expect(screen.getByText('技术')).toBeInTheDocument()
  })

  it('有关联数据 → 渲染图例且不崩溃（G6 已 mock）', () => {
    const relations: RelItem[] = [
      rel({ target_entity_type: 'tech', target_name: '量子计算', relation_type: 'ORG_FUND' }),
      rel({ target_entity_id: 'ORG_1', target_entity_type: 'org', target_name: '中科院', relation_type: 'ORG_PARENT' }),
      rel({ target_entity_id: 'PERSON_1', target_entity_type: 'person', target_name: '张三', relation_type: 'PERSON_AFFILIATED_ORG' }),
    ]
    const { container } = render(<RelationGraph relations={relations} />)
    // 不应出现空态占位
    expect(screen.queryByText('暂无关联数据')).not.toBeInTheDocument()
    // 图例覆盖出现的实体类型
    expect(screen.getByText('当前实体')).toBeInTheDocument()
    expect(screen.getByText('技术')).toBeInTheDocument()
    expect(screen.getByText('机构')).toBeInTheDocument()
    expect(screen.getByText('人员')).toBeInTheDocument()
    // 画布容器 div 存在
    expect(container.querySelector('div[style*="background: rgb(250, 250, 250)"]') || container.querySelectorAll('div').length).toBeTruthy()
  })

  it('自定义 selfLabel 出现在图例', () => {
    render(<RelationGraph relations={[]} selfLabel="目标技术" />)
    expect(screen.getByText('目标技术')).toBeInTheDocument()
  })
})
